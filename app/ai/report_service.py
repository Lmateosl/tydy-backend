"""Orchestration layer for AI report generation."""

import hashlib
from datetime import timedelta

from app import models
from app.ai.guardrails import validate_report_output
from app.ai.langfuse_service import (
    create_observation_or_generation,
    create_report_trace,
    flush_langfuse,
    update_trace_failure,
    update_trace_success,
)
from app.ai.openai_client import generate_report_json
from app.ai.prompts import build_report_messages, get_report_prompt_template
from app.ai.report_queries import build_report_facts
from app.ai.scope import resolve_persisted_report_scope
from app.ai.usage_service import increment_usage_after_success
from app.database import SessionLocal
from app.datetime_utils import utc_now_naive


def queue_report_generation(*args, **kwargs):
    raise NotImplementedError("TODO: implement report queueing")


def build_report_request_fingerprint(
    *,
    company_id,
    scope_type,
    scope_entity_id,
    period_type,
    period_start,
    period_end,
    prompt_template_key,
    prompt_template_version,
):
    raw_value = "|".join(
        [
            str(company_id),
            str(scope_type),
            str(scope_entity_id) if scope_entity_id else "",
            str(period_type),
            period_start.isoformat(),
            period_end.isoformat(),
            prompt_template_key,
            prompt_template_version,
        ]
    )
    return hashlib.sha256(raw_value.encode("utf-8")).hexdigest()


def find_existing_report_for_request(db, *, company_id, request_fingerprint, dedupe_window_hours):
    existing_active = (
        db.query(models.AIReport)
        .filter(
            models.AIReport.company_id == company_id,
            models.AIReport.request_fingerprint == request_fingerprint,
            models.AIReport.status.in_(("queued", "processing")),
        )
        .order_by(models.AIReport.created_at.desc())
        .first()
    )
    if existing_active:
        return existing_active

    dedupe_cutoff = utc_now_naive() - timedelta(hours=dedupe_window_hours)
    existing_completed = (
        db.query(models.AIReport)
        .filter(
            models.AIReport.company_id == company_id,
            models.AIReport.request_fingerprint == request_fingerprint,
            models.AIReport.status == "completed",
            models.AIReport.completed_at.isnot(None),
            models.AIReport.completed_at >= dedupe_cutoff,
        )
        .order_by(models.AIReport.completed_at.desc())
        .first()
    )
    return existing_completed


def create_ai_report_job(
    db,
    *,
    current_user,
    scope_context,
    period_type,
    period_start,
    period_end,
    provider,
    model,
):
    template = get_report_prompt_template(period_type)
    request_fingerprint = build_report_request_fingerprint(
        company_id=scope_context.company_id,
        scope_type=scope_context.scope_type,
        scope_entity_id=scope_context.scope_entity_id,
        period_type=period_type,
        period_start=period_start,
        period_end=period_end,
        prompt_template_key=template["key"],
        prompt_template_version=template["version"],
    )

    report = models.AIReport(
        company_id=scope_context.company_id,
        scope_type=scope_context.scope_type,
        scope_entity_id=scope_context.scope_entity_id,
        period_type=period_type,
        period_start=period_start,
        period_end=period_end,
        status="queued",
        prompt_template_key=template["key"],
        prompt_template_version=template["version"],
        provider=provider,
        model=model,
        requested_by=current_user.id,
        request_fingerprint=request_fingerprint,
    )
    db.add(report)
    db.flush()

    run = models.AIReportRun(
        report_id=report.id,
        company_id=scope_context.company_id,
        run_number=1,
        status="queued",
        provider=provider,
        model=model,
        prompt_template_key=template["key"],
        prompt_template_version=template["version"],
        input_facts_json={},
    )
    db.add(run)
    db.flush()
    return report, run


def process_ai_report(report_id, run_id):
    db = SessionLocal()
    trace = None
    try:
        report = (
            db.query(models.AIReport)
            .filter(models.AIReport.id == report_id)
            .first()
        )
        run = (
            db.query(models.AIReportRun)
            .filter(models.AIReportRun.id == run_id)
            .first()
        )
        if not report or not run:
            return

        trace = create_report_trace(
            report_id=report.id,
            run_id=run.id,
            company_id=report.company_id,
            scope_type=report.scope_type,
            scope_entity_id=report.scope_entity_id,
            period_type=report.period_type,
            provider=report.provider,
            model=report.model,
            prompt_template_key=report.prompt_template_key,
            prompt_template_version=report.prompt_template_version,
        )
        if trace:
            trace_id = getattr(trace, "id", None)
            report.langfuse_trace_id = trace_id
            run.langfuse_trace_id = trace_id

        report.status = "processing"
        report.updated_at = utc_now_naive()
        run.status = "processing"
        run.started_at = utc_now_naive()
        db.commit()

        scope_context = resolve_persisted_report_scope(
            db,
            report.company_id,
            report.scope_type,
            report.scope_entity_id,
        )
        create_observation_or_generation(
            trace=trace,
            name="scope_resolution",
            metadata={
                "scope_type": scope_context.scope_type,
                "scope_entity_id": str(scope_context.scope_entity_id) if scope_context.scope_entity_id else None,
                "visible_empresa_ids_count": len(scope_context.visible_empresa_ids),
                "visible_locacion_ids_count": len(scope_context.visible_locacion_ids),
            },
        )
        facts_json = build_report_facts(
            db,
            scope_context=scope_context,
            period_start=report.period_start,
            period_end=report.period_end,
            period_type=report.period_type,
        )
        create_observation_or_generation(
            trace=trace,
            name="facts_query",
            metadata={
                "summary_metrics": facts_json.get("summary_metrics", {}),
                "verification_metrics": facts_json.get("verification_metrics", {}),
                "problem_locations_count": len(facts_json.get("problem_locations", [])),
                "problem_areas_count": len(facts_json.get("problem_areas", [])),
                "incident_breakdown_count": len(facts_json.get("incident_breakdown", [])),
                "feedback_breakdown_count": len(facts_json.get("feedback_breakdown", [])),
                "source_index_count": len(facts_json.get("source_index", [])),
            },
        )
        report.facts_json = facts_json
        run.input_facts_json = facts_json
        report.updated_at = utc_now_naive()
        db.commit()

        generation_result = generate_report_from_facts(db, facts_json, report.period_type)
        observation = create_observation_or_generation(
            trace=trace,
            name="openai_generation",
            metadata={
                "input_size_chars": len(str(facts_json)),
                "source_index_count": len(facts_json.get("source_index", [])),
                "problem_locations_count": len(facts_json.get("problem_locations", [])),
                "problem_areas_count": len(facts_json.get("problem_areas", [])),
                "model": generation_result["model"],
                "latency_ms": generation_result["latency_ms"],
                "estimated_cost_usd": generation_result["estimated_cost_usd"],
            },
            input_payload={
                "period_type": report.period_type,
                "summary_metrics": facts_json.get("summary_metrics", {}),
                "verification_metrics": facts_json.get("verification_metrics", {}),
            },
            output_payload={
                "title": generation_result["output_json"].get("title"),
                "citations_count": len(generation_result["output_json"].get("citations", [])),
                "recommendations_count": len(generation_result["output_json"].get("recommendations", [])),
            },
            usage={
                "input": generation_result["prompt_tokens"],
                "output": generation_result["completion_tokens"],
                "total": generation_result["total_tokens"],
            },
        )
        if observation:
            run.langfuse_observation_id = getattr(observation, "id", None)

        create_observation_or_generation(
            trace=trace,
            name="guardrails_validation",
            metadata={
                "citations_count": len(generation_result["output_json"].get("citations", [])),
                "recommendations_count": len(generation_result["output_json"].get("recommendations", [])),
            },
        )

        report.report_json = generation_result["output_json"]
        report.citations_json = generation_result["output_json"].get("citations", [])
        report.status = "completed"
        report.completed_at = utc_now_naive()
        report.updated_at = utc_now_naive()
        report.error_message = None
        report.generation_block_reason = None

        run.output_json = generation_result["output_json"]
        run.raw_response_json = generation_result["raw_response_json"]
        run.usage_prompt_tokens = generation_result["prompt_tokens"]
        run.usage_completion_tokens = generation_result["completion_tokens"]
        run.usage_total_tokens = generation_result["total_tokens"]
        run.estimated_cost_usd = generation_result["estimated_cost_usd"]
        run.latency_ms = generation_result["latency_ms"]
        run.status = "completed"
        run.completed_at = utc_now_naive()
        run.error_message = None

        create_observation_or_generation(
            trace=trace,
            name="persistence",
            metadata={
                "report_status": report.status,
                "run_status": run.status,
                "citations_count": len(report.citations_json or []),
            },
        )

        usage_settings_reset_day = 1
        settings = (
            db.query(models.CompanyAISettings)
            .filter(models.CompanyAISettings.company_id == report.company_id)
            .first()
        )
        if settings:
            usage_settings_reset_day = settings.reset_day

        from app.ai.usage_service import get_or_create_monthly_usage

        usage = get_or_create_monthly_usage(
            db,
            report.company_id,
            now=utc_now_naive(),
            reset_day=usage_settings_reset_day,
        )
        increment_usage_after_success(db, usage, run)
        create_observation_or_generation(
            trace=trace,
            name="usage_update",
            metadata={
                "reports_generated_count": usage.reports_generated_count,
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
                "total_cost_usd": float(usage.total_cost_usd or 0),
            },
        )
        db.commit()
        update_trace_success(
            trace=trace,
            output_payload={
                "status": "completed",
                "report_id": str(report.id),
                "run_id": str(run.id),
            },
            metadata={
                "report_status": report.status,
                "run_status": run.status,
                "usage_total_tokens": run.usage_total_tokens,
                "estimated_cost_usd": float(run.estimated_cost_usd or 0),
            },
        )
    except Exception as exc:
        db.rollback()
        report = db.query(models.AIReport).filter(models.AIReport.id == report_id).first()
        run = db.query(models.AIReportRun).filter(models.AIReportRun.id == run_id).first()
        if report:
            report.status = "failed"
            report.error_message = str(exc)
            report.failed_at = utc_now_naive()
            report.updated_at = utc_now_naive()
        if run:
            run.status = "failed"
            run.error_message = str(exc)
            run.failed_at = utc_now_naive()
        db.commit()
        update_trace_failure(
            trace=trace,
            error_message=str(exc),
            metadata={
                "report_id": str(report_id),
                "run_id": str(run_id),
            },
        )
    finally:
        flush_langfuse()
        db.close()


def generate_report_from_facts(db, facts_json, period_type):
    prompt_payload = build_report_messages(facts_json, period_type)
    result = generate_report_json(messages=prompt_payload["messages"])
    normalized_output = validate_report_output(result.output_json, facts_json)
    return {
        "prompt_template_key": prompt_payload["template_key"],
        "prompt_template_version": prompt_payload["template_version"],
        "output_json": normalized_output,
        "raw_response_json": result.raw_response_json,
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
        "total_tokens": result.total_tokens,
        "latency_ms": result.latency_ms,
        "model": result.model,
        "estimated_cost_usd": result.estimated_cost_usd,
    }

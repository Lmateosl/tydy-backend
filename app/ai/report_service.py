"""Orchestration layer for AI report generation."""

import hashlib
from datetime import timedelta

from app import models
from app.ai.guardrails import validate_report_output
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
        facts_json = build_report_facts(
            db,
            scope_context=scope_context,
            period_start=report.period_start,
            period_end=report.period_end,
            period_type=report.period_type,
        )
        report.facts_json = facts_json
        run.input_facts_json = facts_json
        report.updated_at = utc_now_naive()
        db.commit()

        generation_result = generate_report_from_facts(db, facts_json, report.period_type)

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
        db.commit()
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
    finally:
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

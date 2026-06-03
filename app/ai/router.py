import os
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Security
from sqlalchemy.orm import Session

from app import models, schemas
from app.ai.prompts import get_report_prompt_template
from app.ai.report_queries import validate_report_period
from app.ai.report_service import (
    build_report_request_fingerprint,
    create_ai_report_job,
    find_existing_report_for_request,
    process_ai_report,
)
from app.ai.scope import resolve_report_scope
from app.ai.settings_service import ensure_company_ai_settings, get_company_ai_settings_or_403
from app.ai.usage_service import get_or_create_monthly_usage, validate_usage_limits
from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import Usuario

router = APIRouter(prefix="/ai", tags=["AI"])


@router.get("/health")
def ai_health():
    return {
        "status": "ok",
        "feature": "ai_reports_v1_infra",
    }


def _require_admin(current_user: Usuario):
    if current_user.rol != "admin":
        raise HTTPException(status_code=403, detail="No tienes permisos para usar AI Reports")

    if not current_user.company_id:
        raise HTTPException(status_code=404, detail="Usuario no pertenece a ninguna compañía")


def _serialize_report_list_item(report):
    return {
        "id": report.id,
        "scope_type": report.scope_type,
        "scope_entity_id": report.scope_entity_id,
        "period_type": report.period_type,
        "period_start": report.period_start,
        "period_end": report.period_end,
        "status": report.status,
        "provider": report.provider,
        "model": report.model,
        "requested_by": report.requested_by,
        "created_at": report.created_at,
        "completed_at": report.completed_at,
    }


def _serialize_report_detail(report):
    return {
        "id": report.id,
        "company_id": report.company_id,
        "scope_type": report.scope_type,
        "scope_entity_id": report.scope_entity_id,
        "period_type": report.period_type,
        "period_start": report.period_start,
        "period_end": report.period_end,
        "status": report.status,
        "prompt_template_key": report.prompt_template_key,
        "prompt_template_version": report.prompt_template_version,
        "provider": report.provider,
        "model": report.model,
        "requested_by": report.requested_by,
        "request_fingerprint": report.request_fingerprint,
        "report_json": report.report_json,
        "citations_json": report.citations_json,
        "langfuse_trace_id": report.langfuse_trace_id,
        "error_message": report.error_message,
        "generation_block_reason": report.generation_block_reason,
        "created_at": report.created_at,
        "updated_at": report.updated_at,
        "completed_at": report.completed_at,
        "failed_at": report.failed_at,
    }


@router.get("/settings", response_model=schemas.AISettingsResponse)
def get_ai_settings(
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    _require_admin(current_user)
    settings = ensure_company_ai_settings(db, current_user.company_id)
    return settings


@router.get("/usage/current", response_model=schemas.AIUsageCurrentResponse)
def get_ai_usage_current(
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    _require_admin(current_user)
    settings = ensure_company_ai_settings(db, current_user.company_id)
    usage = get_or_create_monthly_usage(
        db,
        current_user.company_id,
        reset_day=settings.reset_day,
    )

    current_cost = float(usage.total_cost_usd or 0)
    current_token_limit = int(settings.monthly_token_limit or 0)
    current_report_limit = int(settings.reports_monthly_limit or 0)
    current_cost_limit = float(settings.monthly_cost_limit_usd or 0)

    return {
        "company_id": current_user.company_id,
        "month_label": f"{usage.usage_year:04d}-{usage.usage_month:02d}",
        "usage_year": usage.usage_year,
        "usage_month": usage.usage_month,
        "settings": settings,
        "usage": usage,
        "remaining": {
            "reports_remaining": max(current_report_limit - usage.reports_generated_count, 0),
            "tokens_remaining": max(current_token_limit - usage.total_tokens, 0),
            "cost_remaining_usd": max(round(current_cost_limit - current_cost, 6), 0.0),
        },
    }


@router.post("/reports/generate", response_model=schemas.AIReportGenerateResponse, status_code=202)
def generate_ai_report(
    payload: schemas.AIReportGenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    _require_admin(current_user)
    scope_context = resolve_report_scope(
        db,
        current_user,
        payload.scope_type,
        payload.scope_entity_id,
    )
    settings = get_company_ai_settings_or_403(db, current_user.company_id)
    usage = get_or_create_monthly_usage(
        db,
        current_user.company_id,
        reset_day=settings.reset_day,
    )
    validate_usage_limits(settings, usage)
    validate_report_period(payload.period_type, payload.period_start, payload.period_end)

    template = get_report_prompt_template(payload.period_type)
    request_fingerprint = build_report_request_fingerprint(
        company_id=scope_context.company_id,
        scope_type=scope_context.scope_type,
        scope_entity_id=scope_context.scope_entity_id,
        period_type=payload.period_type,
        period_start=payload.period_start,
        period_end=payload.period_end,
        prompt_template_key=template["key"],
        prompt_template_version=template["version"],
    )
    existing = find_existing_report_for_request(
        db,
        company_id=current_user.company_id,
        request_fingerprint=request_fingerprint,
        dedupe_window_hours=settings.dedupe_window_hours,
    )
    if existing:
        return {"id": existing.id, "status": existing.status}

    provider = "openai"
    model = os.getenv("OPENAI_MODEL_REPORTS", "gpt-4.1-mini")
    report, run = create_ai_report_job(
        db,
        current_user=current_user,
        scope_context=scope_context,
        period_type=payload.period_type,
        period_start=payload.period_start,
        period_end=payload.period_end,
        provider=provider,
        model=model,
    )
    db.commit()

    background_tasks.add_task(process_ai_report, report.id, run.id)
    return {"id": report.id, "status": report.status}


@router.get("/reports", response_model=schemas.AIReportsListResponse)
def list_ai_reports(
    scope_type: str | None = Query(None),
    scope_entity_id: UUID | None = Query(None),
    period_type: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    _require_admin(current_user)

    query = db.query(models.AIReport).filter(
        models.AIReport.company_id == current_user.company_id
    )
    if scope_type:
        query = query.filter(models.AIReport.scope_type == scope_type)
    if scope_entity_id:
        query = query.filter(models.AIReport.scope_entity_id == scope_entity_id)
    if period_type:
        query = query.filter(models.AIReport.period_type == period_type)
    if status:
        query = query.filter(models.AIReport.status == status)

    total = query.count()
    reports = query.order_by(models.AIReport.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "items": [_serialize_report_list_item(report) for report in reports],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/reports/{report_id}", response_model=schemas.AIReportDetailResponse)
def get_ai_report_detail(
    report_id: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    _require_admin(current_user)

    report = db.query(models.AIReport).filter(
        models.AIReport.id == report_id,
        models.AIReport.company_id == current_user.company_id,
    ).first()
    if not report:
        raise HTTPException(status_code=404, detail="Reporte AI no encontrado")
    return _serialize_report_detail(report)


@router.get("/reports/{report_id}/status", response_model=schemas.AIReportStatusResponse)
def get_ai_report_status(
    report_id: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    _require_admin(current_user)

    report = db.query(models.AIReport).filter(
        models.AIReport.id == report_id,
        models.AIReport.company_id == current_user.company_id,
    ).first()
    if not report:
        raise HTTPException(status_code=404, detail="Reporte AI no encontrado")
    return {
        "id": report.id,
        "status": report.status,
        "created_at": report.created_at,
        "updated_at": report.updated_at,
        "completed_at": report.completed_at,
        "failed_at": report.failed_at,
        "error_message": report.error_message,
    }

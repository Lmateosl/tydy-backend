from fastapi import APIRouter, Depends, HTTPException, Security
from sqlalchemy.orm import Session

from app import schemas
from app.ai.settings_service import ensure_company_ai_settings
from app.ai.usage_service import get_or_create_monthly_usage
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

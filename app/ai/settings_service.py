"""Helpers for company AI settings."""

import uuid
from fastapi import HTTPException
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.datetime_utils import utc_now_naive
from app.models import Company, CompanyAISettings


PRODUCTION_DEFAULTS = {
    "ai_enabled": False,
    "plan_name": "AI_DISABLED",
    "reports_monthly_limit": 0,
    "monthly_token_limit": 0,
    "monthly_cost_limit_usd": 0,
    "reset_day": 1,
    "hard_block_on_limit": True,
    "dedupe_window_hours": 24,
}

DEV_DEFAULTS = {
    "ai_enabled": True,
    "plan_name": "DEV_AI_TEST",
    "reports_monthly_limit": 50,
    "monthly_token_limit": 500000,
    "monthly_cost_limit_usd": 50,
    "reset_day": 1,
    "hard_block_on_limit": True,
    "dedupe_window_hours": 6,
}


def _build_settings_payload(company_id, defaults=None):
    payload = dict(PRODUCTION_DEFAULTS)
    if defaults:
        payload.update(defaults)
    payload.update(
        {
            "company_id": company_id,
            "created_at": utc_now_naive(),
            "updated_at": utc_now_naive(),
        }
    )
    return payload


def get_company_ai_settings(db, company_id):
    return (
        db.query(CompanyAISettings)
        .filter(CompanyAISettings.company_id == company_id)
        .first()
    )


def get_company_ai_settings_or_403(db, company_id):
    settings = get_company_ai_settings(db, company_id)
    if not settings:
        settings = ensure_company_ai_settings(db, company_id)
    return validate_ai_reports_enabled(settings)


def create_default_company_ai_settings(db, company_id):
    settings = CompanyAISettings(**_build_settings_payload(company_id))
    db.add(settings)
    return settings


def ensure_company_ai_settings(db, company_id, defaults=None):
    settings = get_company_ai_settings(db, company_id)
    if settings:
        return settings

    settings = CompanyAISettings(**_build_settings_payload(company_id, defaults=defaults))
    db.add(settings)
    db.flush()
    return settings


def enable_dev_ai_settings(db, company_id):
    settings = get_company_ai_settings(db, company_id)
    if not settings:
        settings = CompanyAISettings(**_build_settings_payload(company_id, defaults=DEV_DEFAULTS))
        db.add(settings)
        db.flush()
        return settings

    for key, value in DEV_DEFAULTS.items():
        setattr(settings, key, value)
    settings.updated_at = utc_now_naive()
    db.flush()
    return settings


def validate_ai_reports_enabled(settings):
    if not settings.ai_enabled:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "AI_DISABLED",
                "message": "AI Reports está deshabilitado para esta compañía",
            },
        )

    if settings.reports_monthly_limit <= 0:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "AI_DISABLED",
                "message": "AI Reports no tiene cupo mensual habilitado para esta compañía",
            },
        )

    return settings


@event.listens_for(Session, "before_flush")
def _ensure_ai_settings_for_new_companies(session, flush_context, instances):
    for instance in session.new:
        if not isinstance(instance, Company):
            continue

        if getattr(instance, "ai_settings", None) is not None:
            continue

        if instance.id is None:
            instance.id = uuid.uuid4()

        session.add(
            CompanyAISettings(
                **_build_settings_payload(instance.id)
            )
        )

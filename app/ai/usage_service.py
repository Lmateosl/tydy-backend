"""Helpers for AI commercial metering."""

from calendar import monthrange
from datetime import datetime

from fastapi import HTTPException

from app.datetime_utils import utc_now_naive
from app.models import CompanyAIUsageMonthly


def _period_anchor(year, month, reset_day):
    safe_day = min(reset_day, monthrange(year, month)[1])
    return datetime(year, month, safe_day)


def get_usage_period(now=None, reset_day=1):
    current = now or utc_now_naive()

    if current.day >= reset_day:
        start_year = current.year
        start_month = current.month
    else:
        if current.month == 1:
            start_year = current.year - 1
            start_month = 12
        else:
            start_year = current.year
            start_month = current.month - 1

    if start_month == 12:
        next_year = start_year + 1
        next_month = 1
    else:
        next_year = start_year
        next_month = start_month + 1

    period_start = _period_anchor(start_year, start_month, reset_day)
    period_end = _period_anchor(next_year, next_month, reset_day)
    return {
        "usage_year": start_year,
        "usage_month": start_month,
        "period_start": period_start,
        "period_end": period_end,
    }


def get_or_create_monthly_usage(db, company_id, now=None, reset_day=1):
    period = get_usage_period(now=now, reset_day=reset_day)
    usage = (
        db.query(CompanyAIUsageMonthly)
        .filter(
            CompanyAIUsageMonthly.company_id == company_id,
            CompanyAIUsageMonthly.usage_year == period["usage_year"],
            CompanyAIUsageMonthly.usage_month == period["usage_month"],
        )
        .first()
    )
    if usage:
        return usage

    usage = CompanyAIUsageMonthly(
        company_id=company_id,
        usage_year=period["usage_year"],
        usage_month=period["usage_month"],
        period_start=period["period_start"],
        period_end=period["period_end"],
    )
    db.add(usage)
    db.flush()
    return usage


def validate_usage_limits(settings, usage):
    if usage.reports_generated_count >= settings.reports_monthly_limit:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "AI_USAGE_LIMIT_EXCEEDED",
                "limit_type": "reports_monthly_limit",
                "message": "Se excedió el límite mensual de reportes AI",
            },
        )

    if usage.total_tokens >= settings.monthly_token_limit:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "AI_USAGE_LIMIT_EXCEEDED",
                "limit_type": "monthly_token_limit",
                "message": "Se excedió el límite mensual de tokens AI",
            },
        )

    current_cost = float(usage.total_cost_usd or 0)
    configured_cost_limit = float(settings.monthly_cost_limit_usd or 0)
    if current_cost >= configured_cost_limit:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "AI_USAGE_LIMIT_EXCEEDED",
                "limit_type": "monthly_cost_limit_usd",
                "message": "Se excedió el límite mensual de costo AI",
            },
        )

    return usage


def increment_usage_after_success(db, usage, run):
    if run.billing_counted:
        return usage

    usage.reports_generated_count += 1
    usage.prompt_tokens += int(run.usage_prompt_tokens or 0)
    usage.completion_tokens += int(run.usage_completion_tokens or 0)
    usage.total_tokens += int(run.usage_total_tokens or 0)
    usage.total_cost_usd = float(usage.total_cost_usd or 0) + float(run.estimated_cost_usd or 0)
    usage.last_report_at = utc_now_naive()
    usage.updated_at = utc_now_naive()
    run.billing_counted = True
    db.flush()
    return usage

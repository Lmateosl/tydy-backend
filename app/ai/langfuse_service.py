"""Optional Langfuse instrumentation for AI reports."""

import os
from typing import Any, Optional

try:
    from langfuse import Langfuse
except Exception:  # pragma: no cover - optional dependency at runtime
    Langfuse = None


_langfuse_client = None


def is_langfuse_enabled():
    return bool(
        Langfuse
        and os.getenv("LANGFUSE_PUBLIC_KEY")
        and os.getenv("LANGFUSE_SECRET_KEY")
        and (os.getenv("LANGFUSE_HOST") or os.getenv("LANGFUSE_BASE_URL"))
    )


def _get_client():
    global _langfuse_client
    if not is_langfuse_enabled():
        return None
    if _langfuse_client is None:
        host = os.getenv("LANGFUSE_HOST")
        base_url = os.getenv("LANGFUSE_BASE_URL")
        kwargs = {
            "public_key": os.getenv("LANGFUSE_PUBLIC_KEY"),
            "secret_key": os.getenv("LANGFUSE_SECRET_KEY"),
        }
        if host:
            kwargs["host"] = host
        elif base_url:
            kwargs["base_url"] = base_url
        _langfuse_client = Langfuse(**kwargs)
    return _langfuse_client


def _safe_report_metadata(metadata: Optional[dict[str, Any]] = None):
    if not metadata:
        return {}

    safe_metadata = {}
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            safe_metadata[key] = value
            continue
        if isinstance(value, dict):
            summarized = {}
            for nested_key, nested_value in value.items():
                if isinstance(nested_value, (str, int, float, bool)) or nested_value is None:
                    summarized[str(nested_key)] = nested_value
                else:
                    summarized[str(nested_key)] = str(nested_value)[:200]
            safe_metadata[key] = summarized
            continue
        if isinstance(value, (list, tuple, set)):
            safe_metadata[key] = [str(item)[:120] for item in list(value)[:20]]
            continue
        safe_metadata[key] = str(value)[:200]
    return safe_metadata


def _usage_details(usage: Optional[dict[str, Any]] = None):
    if not usage:
        return None
    safe_usage = {}
    for key, value in usage.items():
        if value is None:
            continue
        try:
            safe_usage[str(key)] = int(value)
        except (TypeError, ValueError):
            continue
    return safe_usage or None


def _cost_details(metadata: Optional[dict[str, Any]] = None):
    if not metadata:
        return None
    estimated_cost = metadata.get("estimated_cost_usd")
    if estimated_cost is None:
        return None
    try:
        return {"total_usd": float(estimated_cost)}
    except (TypeError, ValueError):
        return None


def create_report_trace(*, report_id, run_id, company_id, scope_type, scope_entity_id, period_type, provider, model, prompt_template_key, prompt_template_version):
    client = _get_client()
    if not client:
        return None

    try:
        return client.start_observation(
            name="ai_report_generation",
            as_type="span",
            metadata=_safe_report_metadata(
                {
                    "company_id": str(company_id),
                    "report_id": str(report_id),
                    "run_id": str(run_id),
                    "scope_type": scope_type,
                    "scope_entity_id": str(scope_entity_id) if scope_entity_id else None,
                    "period_type": period_type,
                    "provider": provider,
                    "model": model,
                    "prompt_template_key": prompt_template_key,
                    "prompt_template_version": prompt_template_version,
                }
            ),
        )
    except Exception:
        return None


def create_observation_or_generation(*, trace, name, metadata=None, input_payload=None, output_payload=None, usage=None, level="DEFAULT"):
    if not trace:
        return None

    try:
        observation_type = "generation" if name == "openai_generation" else "span"
        observation = trace.start_observation(
            name=name,
            as_type=observation_type,
            metadata=_safe_report_metadata(metadata),
            input=input_payload,
            output=output_payload,
            usage_details=_usage_details(usage),
            cost_details=_cost_details(metadata),
            level=level,
            model=(metadata or {}).get("model") if observation_type == "generation" else None,
        )
        observation.end()
        return observation
    except Exception:
        return None


def update_trace_success(*, trace, output_payload=None, metadata=None):
    if not trace:
        return
    try:
        trace.update(
            output=output_payload,
            metadata=_safe_report_metadata(metadata),
        )
        trace.end()
    except Exception:
        return


def update_trace_failure(*, trace, error_message, metadata=None):
    if not trace:
        return
    try:
        trace.update(
            output={"status": "failed", "error": error_message},
            metadata=_safe_report_metadata(metadata),
            level="ERROR",
            status_message=str(error_message)[:500],
        )
        trace.end()
    except Exception:
        return


def flush_langfuse():
    client = _get_client()
    if not client:
        return
    try:
        client.flush()
    except Exception:
        return

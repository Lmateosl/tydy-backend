"""Optional Langfuse instrumentation for AI reports."""

import os

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
    )


def _get_client():
    global _langfuse_client
    if not is_langfuse_enabled():
        return None
    if _langfuse_client is None:
        host = os.getenv("LANGFUSE_HOST")
        kwargs = {
            "public_key": os.getenv("LANGFUSE_PUBLIC_KEY"),
            "secret_key": os.getenv("LANGFUSE_SECRET_KEY"),
        }
        if host:
            kwargs["host"] = host
        _langfuse_client = Langfuse(**kwargs)
    return _langfuse_client


def create_report_trace(*, report_id, run_id, company_id, scope_type, scope_entity_id, period_type, provider, model, prompt_template_key, prompt_template_version):
    client = _get_client()
    if not client:
        return None

    return client.trace(
        name="ai_report_generation",
        metadata={
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
        },
    )


def create_observation_or_generation(*, trace, name, metadata=None, input_payload=None, output_payload=None, usage=None, level="DEFAULT"):
    if not trace:
        return None

    try:
        return trace.generation(
            name=name,
            metadata=metadata or {},
            input=input_payload,
            output=output_payload,
            usage=usage,
            level=level,
        )
    except Exception:
        return None


def update_trace_success(*, trace, output_payload=None, metadata=None):
    if not trace:
        return
    try:
        trace.update(
            output=output_payload,
            metadata=metadata or {},
        )
    except Exception:
        return


def update_trace_failure(*, trace, error_message, metadata=None):
    if not trace:
        return
    try:
        trace.update(
            output={"status": "failed", "error": error_message},
            metadata=metadata or {},
        )
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

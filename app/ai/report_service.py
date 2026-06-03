"""Orchestration layer for AI report generation."""

from app.ai.guardrails import validate_report_output
from app.ai.openai_client import generate_report_json
from app.ai.prompts import build_report_messages


def queue_report_generation(*args, **kwargs):
    raise NotImplementedError("TODO: implement report queueing")


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

"""OpenAI wrapper for structured AI reports."""

import json
import os
import time
from dataclasses import dataclass

from openai import APIError, APITimeoutError, AuthenticationError, OpenAI, RateLimitError


DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_MAX_OUTPUT_TOKENS = 1600
DEFAULT_TEMPERATURE = 0.1

MODEL_PRICING_USD_PER_1M = {
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    "gpt-4.1": {"input": 2.00, "output": 8.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
}


@dataclass
class OpenAIReportResult:
    output_json: dict
    raw_response_json: dict
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: int
    model: str
    estimated_cost_usd: float | None


def estimate_openai_cost_usd(model, prompt_tokens, completion_tokens):
    pricing = MODEL_PRICING_USD_PER_1M.get(model)
    if not pricing:
        return None

    input_cost = (int(prompt_tokens or 0) / 1_000_000) * pricing["input"]
    output_cost = (int(completion_tokens or 0) / 1_000_000) * pricing["output"]
    return round(input_cost + output_cost, 6)


def _build_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY")

    timeout_seconds = int(os.getenv("OPENAI_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS))
    return OpenAI(api_key=api_key, timeout=timeout_seconds)


def _extract_content(response):
    choices = getattr(response, "choices", None) or []
    if not choices:
        raise RuntimeError("OpenAI returned no choices")

    message = getattr(choices[0], "message", None)
    if message is None:
        raise RuntimeError("OpenAI returned no message content")

    content = getattr(message, "content", None)
    if not content:
        raise RuntimeError("OpenAI returned empty content")
    return content


def generate_report_json(*, messages, model=None, timeout_seconds=None, max_output_tokens=None, temperature=DEFAULT_TEMPERATURE):
    client = _build_client()
    selected_model = model or os.getenv("OPENAI_MODEL_REPORTS", DEFAULT_OPENAI_MODEL)
    request_timeout = timeout_seconds or int(os.getenv("OPENAI_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS))
    output_tokens = max_output_tokens or int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", DEFAULT_MAX_OUTPUT_TOKENS))

    start = time.perf_counter()
    try:
        response = client.chat.completions.create(
            model=selected_model,
            messages=messages,
            temperature=temperature,
            max_tokens=output_tokens,
            response_format={"type": "json_object"},
            timeout=request_timeout,
        )
    except APITimeoutError as exc:
        raise RuntimeError("OpenAI request timed out") from exc
    except RateLimitError as exc:
        raise RuntimeError("OpenAI rate limit exceeded") from exc
    except AuthenticationError as exc:
        raise RuntimeError("OpenAI authentication failed") from exc
    except APIError as exc:
        raise RuntimeError("OpenAI API error") from exc
    except Exception as exc:
        raise RuntimeError("Unexpected OpenAI client error") from exc

    latency_ms = int((time.perf_counter() - start) * 1000)
    raw_content = _extract_content(response)

    try:
        output_json = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        raise RuntimeError("OpenAI returned invalid JSON") from exc

    usage = getattr(response, "usage", None)
    prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
    completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
    total_tokens = int(getattr(usage, "total_tokens", prompt_tokens + completion_tokens) or 0)
    estimated_cost_usd = estimate_openai_cost_usd(selected_model, prompt_tokens, completion_tokens)

    return OpenAIReportResult(
        output_json=output_json,
        raw_response_json=response.model_dump() if hasattr(response, "model_dump") else {},
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        latency_ms=latency_ms,
        model=selected_model,
        estimated_cost_usd=estimated_cost_usd,
    )

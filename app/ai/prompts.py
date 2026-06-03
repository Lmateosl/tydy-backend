"""Prompt template registry for AI reports."""

import json


REPORT_WEEKLY_TEMPLATE_KEY = "report_weekly_v1"
REPORT_MONTHLY_TEMPLATE_KEY = "report_monthly_v1"
TEMPLATE_VERSION = "1.0.0"


PROMPT_TEMPLATES = {
    "weekly": REPORT_WEEKLY_TEMPLATE_KEY,
    "monthly": REPORT_MONTHLY_TEMPLATE_KEY,
}


def get_report_prompt_template(period_type):
    if period_type not in PROMPT_TEMPLATES:
        raise ValueError(f"Unsupported period_type: {period_type}")
    return {
        "key": PROMPT_TEMPLATES[period_type],
        "version": TEMPLATE_VERSION,
    }


def build_report_messages(facts_json, period_type):
    template = get_report_prompt_template(period_type)
    system_prompt = (
        "Eres TYDY AI Operations Intelligence. "
        "Solo usa los facts entregados por el backend. "
        "Nunca inventes datos. "
        "Si falta un dato, escribe \"no disponible\". "
        "Toda métrica, hallazgo o recomendación importante debe incluir source_ids válidos. "
        "Responde únicamente con JSON válido. "
        "No incluyas markdown. "
        "No incluyas texto fuera del JSON."
    )

    output_contract = {
        "title": "string",
        "period_label": "string",
        "executive_summary": "string",
        "key_metrics": {
            "metric_key": {
                "value": "number|string",
                "label": "string",
                "source_ids": ["source_id"],
            }
        },
        "problem_areas": [
            {
                "name": "string",
                "reason": "string",
                "source_ids": ["source_id"],
            }
        ],
        "recommendations": [
            {
                "text": "string",
                "priority": "low|medium|high",
                "source_ids": ["source_id"],
            }
        ],
        "caveats": ["string"],
        "citations": [
            {
                "source_type": "metric|locacion|area|incident_group|feedback_group",
                "source_id": "string",
                "label": "string",
            }
        ],
    }

    user_payload = {
        "template_key": template["key"],
        "template_version": template["version"],
        "instructions": {
            "language": "es",
            "format": "json_only",
            "missing_data_policy": "use_no_disponible",
        },
        "facts": facts_json,
        "output_contract": output_contract,
    }

    return {
        "template_key": template["key"],
        "template_version": template["version"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=True)},
        ],
    }

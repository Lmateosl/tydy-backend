"""Guardrails for AI report validation."""


REQUIRED_FIELDS = {
    "title",
    "period_label",
    "executive_summary",
    "key_metrics",
    "problem_areas",
    "recommendations",
    "caveats",
    "citations",
}


def normalize_report_output(output_json):
    normalized = dict(output_json or {})
    normalized.setdefault("key_metrics", {})
    normalized.setdefault("problem_areas", [])
    normalized.setdefault("recommendations", [])
    normalized.setdefault("caveats", [])
    normalized.setdefault("citations", [])
    return normalized


def _collect_source_ids(value):
    source_ids = set()
    if isinstance(value, dict):
        if isinstance(value.get("source_ids"), list):
            for item in value["source_ids"]:
                if item:
                    source_ids.add(str(item))
        if value.get("source_id"):
            source_ids.add(str(value["source_id"]))
        for nested in value.values():
            source_ids.update(_collect_source_ids(nested))
    elif isinstance(value, list):
        for item in value:
            source_ids.update(_collect_source_ids(item))
    return source_ids


def validate_source_ids_exist(output_json, facts_json):
    available_source_ids = {
        str(item.get("source_id"))
        for item in facts_json.get("source_index", [])
        if item.get("source_id")
    }
    used_source_ids = _collect_source_ids(output_json)
    invalid_source_ids = sorted(source_id for source_id in used_source_ids if source_id not in available_source_ids)
    if invalid_source_ids:
        raise ValueError(f"Invalid source_ids in report output: {', '.join(invalid_source_ids)}")


def validate_report_output(output_json, facts_json):
    normalized = normalize_report_output(output_json)

    missing_fields = sorted(field for field in REQUIRED_FIELDS if field not in normalized)
    if missing_fields:
        raise ValueError(f"Missing required report fields: {', '.join(missing_fields)}")

    if not isinstance(normalized["citations"], list):
        raise ValueError("Report citations must be a list")
    if not isinstance(normalized["problem_areas"], list):
        raise ValueError("Report problem_areas must be a list")
    if not isinstance(normalized["recommendations"], list):
        raise ValueError("Report recommendations must be a list")
    if not isinstance(normalized["caveats"], list):
        raise ValueError("Report caveats must be a list")
    if not isinstance(normalized["key_metrics"], dict):
        raise ValueError("Report key_metrics must be an object")

    validate_source_ids_exist(normalized, facts_json)
    return normalized

"""SQL-first facts queries for AI reports."""

from datetime import datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, case, func, or_

from app import models
from app.services.incidentes_metrics import ESTADOS_ABIERTOS


MAX_TOP_ITEMS = 5
MAX_INCIDENT_BREAKDOWN_ITEMS = 10


def safe_int(value):
    return int(value or 0)


def serialize_datetime(value):
    if value is None:
        return None
    return value.isoformat() + "Z"


def validate_report_period(period_type, period_start, period_end):
    if period_end < period_start:
        raise HTTPException(status_code=400, detail="period_end no puede ser menor a period_start")

    total_days = (period_end - period_start).days + 1
    if period_type == "weekly" and not (6 <= total_days <= 8):
        raise HTTPException(status_code=400, detail="Periodo weekly inválido; debe cubrir entre 6 y 8 días")
    if period_type == "monthly" and not (28 <= total_days <= 31):
        raise HTTPException(status_code=400, detail="Periodo monthly inválido; debe cubrir entre 28 y 31 días")
    if period_type not in {"weekly", "monthly"}:
        raise HTTPException(status_code=400, detail="period_type no válido")


def _apply_activity_scope_filters(query, scope_context):
    query = query.filter(models.ActividadUsuario.company_id == scope_context.company_id)

    if scope_context.scope_type == "empresa":
        query = query.filter(models.Empresa.id == scope_context.scope_entity_id)
    elif scope_context.scope_type == "locacion":
        query = query.filter(models.Locacion.id == scope_context.scope_entity_id)

    return query


def _apply_incident_scope_filters(query, scope_context):
    query = query.filter(models.Incidente.company_id == scope_context.company_id)

    if scope_context.scope_type == "empresa":
        # Fallback seguro: si no hay locacion pero si empresa, se usa empresa_id.
        query = query.filter(
            or_(
                models.Incidente.empresa_id == scope_context.scope_entity_id,
                models.Incidente.locacion_id.in_(scope_context.visible_locacion_ids or []),
            )
        )
    elif scope_context.scope_type == "locacion":
        query = query.filter(models.Incidente.locacion_id == scope_context.scope_entity_id)

    return query


def _apply_feedback_scope_filters(query, scope_context):
    query = query.filter(models.Feedback.company_id == scope_context.company_id)

    if scope_context.scope_type == "empresa":
        query = query.filter(models.Feedback.empresa_id == scope_context.scope_entity_id)
    elif scope_context.scope_type == "locacion":
        query = query.filter(models.Feedback.locacion_id == scope_context.scope_entity_id)

    return query


def _activity_context_query(db, scope_context):
    # Para empresa/locacion solo contamos actividades atribuibles con seguridad via Usuario -> Area -> Locacion -> Empresa.
    return _apply_activity_scope_filters(
        db.query(models.ActividadUsuario)
        .select_from(models.ActividadUsuario)
        .join(models.Usuario, models.ActividadUsuario.usuario_id == models.Usuario.id)
        .join(models.Area, models.Usuario.area_id == models.Area.id, isouter=True)
        .join(models.Locacion, models.Area.locacion_id == models.Locacion.id, isouter=True)
        .join(models.Empresa, models.Locacion.empresa_id == models.Empresa.id, isouter=True),
        scope_context,
    )


def _source(source_id, source_type, label):
    return {
        "source_id": source_id,
        "source_type": source_type,
        "label": label,
    }


def _severity_from_ratio(count, total, *, low_threshold=0.1, high_threshold=0.25):
    if total <= 0 or count <= 0:
        return None
    ratio = count / total
    if ratio >= high_threshold:
        return "high"
    if ratio >= low_threshold:
        return "medium"
    return "low"


def _build_summary_metrics(db, scope_context, period_start, period_end):
    activity_query = _activity_context_query(db, scope_context).filter(
        models.ActividadUsuario.hora_inicio >= period_start,
        models.ActividadUsuario.hora_inicio <= period_end,
    )

    activities_started = activity_query.count()
    activities_completed = activity_query.filter(models.ActividadUsuario.finalizada.is_(True)).count()
    activities_not_finished = activity_query.filter(
        or_(
            models.ActividadUsuario.finalizada.is_(False),
            models.ActividadUsuario.finalizada.is_(None),
        )
    ).count()
    missing_evidence_count = activity_query.filter(
        models.ActividadUsuario.evidencia_obligatoria.is_(True),
        or_(
            models.ActividadUsuario.evidencia_entregada.is_(False),
            models.ActividadUsuario.evidencia_entregada.is_(None),
        ),
    ).count()

    incident_query = _apply_incident_scope_filters(
        db.query(models.Incidente).filter(
            models.Incidente.creado_en >= period_start,
            models.Incidente.creado_en <= period_end,
        ),
        scope_context,
    )
    incidents_open = incident_query.filter(models.Incidente.estado.in_(ESTADOS_ABIERTOS)).count()
    incidents_resolved = incident_query.filter(models.Incidente.estado == "resuelto").count()
    incidents_closed = incident_query.filter(models.Incidente.estado == "cerrado").count()

    feedback_query = _apply_feedback_scope_filters(
        db.query(models.Feedback).filter(
            models.Feedback.creado_en >= period_start,
            models.Feedback.creado_en <= period_end,
        ),
        scope_context,
    )
    negative_feedback_count = feedback_query.filter(models.Feedback.calificacion < 3).count()

    return {
        "activities_started": safe_int(activities_started),
        "activities_completed": safe_int(activities_completed),
        "activities_not_finished": safe_int(activities_not_finished),
        "incidents_open": safe_int(incidents_open),
        "incidents_resolved": safe_int(incidents_resolved),
        "incidents_closed": safe_int(incidents_closed),
        "negative_feedback_count": safe_int(negative_feedback_count),
        "missing_evidence_count": safe_int(missing_evidence_count),
    }


def _build_verification_metrics(db, scope_context, period_start, period_end):
    activity_query = _activity_context_query(db, scope_context).filter(
        models.ActividadUsuario.hora_inicio >= period_start,
        models.ActividadUsuario.hora_inicio <= period_end,
    )

    verified_count = activity_query.filter(
        func.lower(func.coalesce(models.ActividadUsuario.estado_verificacion, "")) == "verificada"
    ).count()
    requires_review_count = activity_query.filter(
        func.lower(func.coalesce(models.ActividadUsuario.estado_verificacion, "")) == "requiere_revision"
    ).count()
    low_precision_count = activity_query.filter(
        func.lower(func.coalesce(models.ActividadUsuario.estado_verificacion, "")) == "verificada_con_baja_precision"
    ).count()

    return {
        "verified_count": safe_int(verified_count),
        "requires_review_count": safe_int(requires_review_count),
        "low_precision_count": safe_int(low_precision_count),
    }


def _build_incident_breakdown(db, scope_context, period_start, period_end):
    rows = (
        _apply_incident_scope_filters(
            db.query(
                models.Incidente.tipo,
                models.Incidente.prioridad,
                models.Incidente.estado,
                func.count(models.Incidente.id).label("total"),
            ).filter(
                models.Incidente.creado_en >= period_start,
                models.Incidente.creado_en <= period_end,
            ),
            scope_context,
        )
        .group_by(models.Incidente.tipo, models.Incidente.prioridad, models.Incidente.estado)
        .order_by(func.count(models.Incidente.id).desc(), models.Incidente.tipo.asc())
        .limit(MAX_INCIDENT_BREAKDOWN_ITEMS)
        .all()
    )

    return [
        {
            "tipo": row.tipo,
            "prioridad": row.prioridad,
            "estado": row.estado,
            "count": safe_int(row.total),
            "source_id": f"incident_group:{row.tipo}:{row.estado}",
        }
        for row in rows
    ]


def _build_feedback_breakdown(db, scope_context, period_start, period_end):
    rows = (
        _apply_feedback_scope_filters(
            db.query(
                models.Feedback.calificacion.label("rating"),
                func.count(models.Feedback.id).label("total"),
            ).filter(
                models.Feedback.creado_en >= period_start,
                models.Feedback.creado_en <= period_end,
            ),
            scope_context,
        )
        .group_by(models.Feedback.calificacion)
        .order_by(func.count(models.Feedback.id).desc(), models.Feedback.calificacion.asc())
        .limit(MAX_TOP_ITEMS)
        .all()
    )

    return [
        {
            "rating": float(row.rating) if row.rating is not None else None,
            "count": safe_int(row.total),
            "source_id": f"feedback_group:{float(row.rating) if row.rating is not None else 'unknown'}",
        }
        for row in rows
    ]


def _build_problem_locations(db, scope_context, period_start, period_end):
    activity_rows = (
        _activity_context_query(db, scope_context)
        .filter(
            models.ActividadUsuario.hora_inicio >= period_start,
            models.ActividadUsuario.hora_inicio <= period_end,
        )
        .with_entities(
            models.Locacion.id.label("locacion_id"),
            models.Locacion.nombre.label("locacion_nombre"),
            func.sum(
                case(
                    (
                        or_(
                            models.ActividadUsuario.finalizada.is_(False),
                            models.ActividadUsuario.finalizada.is_(None),
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("unfinished_count"),
        )
        .filter(models.Locacion.id.isnot(None))
        .group_by(models.Locacion.id, models.Locacion.nombre)
        .all()
    )

    incident_rows = (
        _apply_incident_scope_filters(
            db.query(
                models.Locacion.id.label("locacion_id"),
                models.Locacion.nombre.label("locacion_nombre"),
                func.count(models.Incidente.id).label("incident_count"),
            )
            .select_from(models.Incidente)
            .join(models.Locacion, models.Incidente.locacion_id == models.Locacion.id)
            .filter(
                models.Incidente.creado_en >= period_start,
                models.Incidente.creado_en <= period_end,
            ),
            scope_context,
        )
        .group_by(models.Locacion.id, models.Locacion.nombre)
        .all()
    )

    feedback_rows = (
        _apply_feedback_scope_filters(
            db.query(
                models.Locacion.id.label("locacion_id"),
                models.Locacion.nombre.label("locacion_nombre"),
                func.count(models.Feedback.id).label("negative_feedback_count"),
            )
            .select_from(models.Feedback)
            .join(models.Locacion, models.Feedback.locacion_id == models.Locacion.id)
            .filter(
                models.Feedback.creado_en >= period_start,
                models.Feedback.creado_en <= period_end,
                models.Feedback.calificacion < 3,
            ),
            scope_context,
        )
        .group_by(models.Locacion.id, models.Locacion.nombre)
        .all()
    )

    merged = {}
    for row in activity_rows:
        if row.locacion_id is None:
            continue
        merged.setdefault(
            row.locacion_id,
            {
                "id": str(row.locacion_id),
                "name": row.locacion_nombre or "Sin locación",
                "unfinished_count": 0,
                "incident_count": 0,
                "negative_feedback_count": 0,
                "source_id": f"locacion:{row.locacion_id}",
            },
        )["unfinished_count"] = safe_int(row.unfinished_count)

    for row in incident_rows:
        if row.locacion_id is None:
            continue
        merged.setdefault(
            row.locacion_id,
            {
                "id": str(row.locacion_id),
                "name": row.locacion_nombre or "Sin locación",
                "unfinished_count": 0,
                "incident_count": 0,
                "negative_feedback_count": 0,
                "source_id": f"locacion:{row.locacion_id}",
            },
        )["incident_count"] = safe_int(row.incident_count)

    for row in feedback_rows:
        if row.locacion_id is None:
            continue
        merged.setdefault(
            row.locacion_id,
            {
                "id": str(row.locacion_id),
                "name": row.locacion_nombre or "Sin locación",
                "unfinished_count": 0,
                "incident_count": 0,
                "negative_feedback_count": 0,
                "source_id": f"locacion:{row.locacion_id}",
            },
        )["negative_feedback_count"] = safe_int(row.negative_feedback_count)

    items = list(merged.values())
    for item in items:
        item["problem_score"] = item["unfinished_count"] + item["incident_count"] + item["negative_feedback_count"]

    items.sort(key=lambda item: (-item["problem_score"], item["name"]))
    return items[:MAX_TOP_ITEMS]


def _build_problem_areas(db, scope_context, period_start, period_end):
    activity_rows = (
        _activity_context_query(db, scope_context)
        .filter(
            models.ActividadUsuario.hora_inicio >= period_start,
            models.ActividadUsuario.hora_inicio <= period_end,
        )
        .with_entities(
            models.Area.id.label("area_id"),
            models.Area.nombre.label("area_nombre"),
            func.sum(
                case(
                    (
                        or_(
                            models.ActividadUsuario.finalizada.is_(False),
                            models.ActividadUsuario.finalizada.is_(None),
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("unfinished_count"),
            func.sum(
                case(
                    (
                        and_(
                            models.ActividadUsuario.evidencia_obligatoria.is_(True),
                            or_(
                                models.ActividadUsuario.evidencia_entregada.is_(False),
                                models.ActividadUsuario.evidencia_entregada.is_(None),
                            ),
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("missing_evidence_count"),
        )
        .filter(models.Area.id.isnot(None))
        .group_by(models.Area.id, models.Area.nombre)
        .all()
    )

    incident_rows = (
        _apply_incident_scope_filters(
            db.query(
                models.Area.id.label("area_id"),
                models.Area.nombre.label("area_nombre"),
                func.count(models.Incidente.id).label("incident_count"),
            )
            .select_from(models.Incidente)
            .join(models.Area, models.Incidente.area_id == models.Area.id)
            .filter(
                models.Incidente.creado_en >= period_start,
                models.Incidente.creado_en <= period_end,
            ),
            scope_context,
        )
        .group_by(models.Area.id, models.Area.nombre)
        .all()
    )

    merged = {}
    for row in activity_rows:
        if row.area_id is None:
            continue
        merged.setdefault(
            row.area_id,
            {
                "id": str(row.area_id),
                "name": row.area_nombre or "Sin área",
                "unfinished_count": 0,
                "incident_count": 0,
                "missing_evidence_count": 0,
                "source_id": f"area:{row.area_id}",
            },
        )["unfinished_count"] = safe_int(row.unfinished_count)
        merged[row.area_id]["missing_evidence_count"] = safe_int(row.missing_evidence_count)

    for row in incident_rows:
        if row.area_id is None:
            continue
        merged.setdefault(
            row.area_id,
            {
                "id": str(row.area_id),
                "name": row.area_nombre or "Sin área",
                "unfinished_count": 0,
                "incident_count": 0,
                "missing_evidence_count": 0,
                "source_id": f"area:{row.area_id}",
            },
        )["incident_count"] = safe_int(row.incident_count)

    items = list(merged.values())
    for item in items:
        item["problem_score"] = item["unfinished_count"] + item["incident_count"] + item["missing_evidence_count"]

    items.sort(key=lambda item: (-item["problem_score"], item["name"]))
    return items[:MAX_TOP_ITEMS]


def _build_recommendation_inputs(summary_metrics, verification_metrics, problem_locations, problem_areas):
    signals = []
    started = summary_metrics["activities_started"]

    unfinished_severity = _severity_from_ratio(summary_metrics["activities_not_finished"], started)
    if unfinished_severity:
        signals.append(
            {
                "type": "high_unfinished_activities",
                "severity": unfinished_severity,
                "description": "Hay un volumen relevante de actividades no finalizadas en el periodo.",
                "source_ids": ["metric:activities_not_finished", "metric:activities_started"],
            }
        )

    missing_evidence_severity = _severity_from_ratio(summary_metrics["missing_evidence_count"], started)
    if missing_evidence_severity:
        signals.append(
            {
                "type": "high_missing_evidence",
                "severity": missing_evidence_severity,
                "description": "Se detectó una proporción relevante de actividades con evidencia faltante.",
                "source_ids": ["metric:missing_evidence_count", "metric:activities_started"],
            }
        )

    if summary_metrics["incidents_open"] > 0:
        signals.append(
            {
                "type": "high_open_incidents",
                "severity": "high" if summary_metrics["incidents_open"] >= 5 else "medium",
                "description": "Existen incidentes abiertos que requieren seguimiento operativo.",
                "source_ids": ["metric:incidents_open"],
            }
        )

    if summary_metrics["negative_feedback_count"] > 0:
        source_ids = ["metric:negative_feedback_count"]
        if problem_locations:
            source_ids.append(problem_locations[0]["source_id"])
        signals.append(
            {
                "type": "negative_feedback_cluster",
                "severity": "high" if summary_metrics["negative_feedback_count"] >= 3 else "medium",
                "description": "Se registró feedback negativo en el periodo.",
                "source_ids": source_ids,
            }
        )

    low_quality_count = verification_metrics["requires_review_count"] + verification_metrics["low_precision_count"]
    verification_severity = _severity_from_ratio(low_quality_count, started, low_threshold=0.08, high_threshold=0.2)
    if verification_severity:
        source_ids = ["metric:requires_review_count", "metric:low_precision_count", "metric:activities_started"]
        if problem_areas:
            source_ids.append(problem_areas[0]["source_id"])
        signals.append(
            {
                "type": "low_verification_quality",
                "severity": verification_severity,
                "description": "La calidad de verificación de actividades requiere atención.",
                "source_ids": source_ids,
            }
        )

    return signals


def _build_source_index(summary_metrics, verification_metrics, problem_locations, problem_areas, incident_breakdown, feedback_breakdown):
    sources = [
        _source("metric:activities_started", "metric", "Actividades iniciadas"),
        _source("metric:activities_completed", "metric", "Actividades completadas"),
        _source("metric:activities_not_finished", "metric", "Actividades no finalizadas"),
        _source("metric:incidents_open", "metric", "Incidentes abiertos"),
        _source("metric:incidents_resolved", "metric", "Incidentes resueltos"),
        _source("metric:incidents_closed", "metric", "Incidentes cerrados"),
        _source("metric:negative_feedback_count", "metric", "Feedback negativo"),
        _source("metric:missing_evidence_count", "metric", "Evidencia faltante"),
        _source("metric:verified_count", "metric", "Actividades verificadas"),
        _source("metric:requires_review_count", "metric", "Actividades con revisión requerida"),
        _source("metric:low_precision_count", "metric", "Actividades verificadas con baja precisión"),
    ]

    for item in problem_locations:
        sources.append(_source(item["source_id"], "locacion", item["name"]))
    for item in problem_areas:
        sources.append(_source(item["source_id"], "area", item["name"]))
    for item in incident_breakdown:
        sources.append(
            _source(
                item["source_id"],
                "incident_group",
                f"Incidentes {item['tipo']} / {item['estado']}",
            )
        )
    for item in feedback_breakdown:
        sources.append(
            _source(
                item["source_id"],
                "feedback_group",
                f"Feedback calificación {item['rating']}",
            )
        )

    deduped = {}
    for source in sources:
        deduped[source["source_id"]] = source
    return list(deduped.values())


def build_report_facts(
    db,
    *,
    scope_context,
    period_start,
    period_end,
    period_type,
):
    validate_report_period(period_type, period_start, period_end)

    summary_metrics = _build_summary_metrics(db, scope_context, period_start, period_end)
    verification_metrics = _build_verification_metrics(db, scope_context, period_start, period_end)
    problem_locations = _build_problem_locations(db, scope_context, period_start, period_end)
    problem_areas = _build_problem_areas(db, scope_context, period_start, period_end)
    incident_breakdown = _build_incident_breakdown(db, scope_context, period_start, period_end)
    feedback_breakdown = _build_feedback_breakdown(db, scope_context, period_start, period_end)
    recommendation_inputs = _build_recommendation_inputs(
        summary_metrics,
        verification_metrics,
        problem_locations,
        problem_areas,
    )
    source_index = _build_source_index(
        summary_metrics,
        verification_metrics,
        problem_locations,
        problem_areas,
        incident_breakdown,
        feedback_breakdown,
    )

    return {
        "scope": {
            "scope_type": scope_context.scope_type,
            "scope_entity_id": str(scope_context.scope_entity_id) if scope_context.scope_entity_id else None,
            "scope_label": scope_context.scope_label,
        },
        "period": {
            "period_type": period_type,
            "period_start": serialize_datetime(period_start),
            "period_end": serialize_datetime(period_end),
        },
        "summary_metrics": summary_metrics,
        "verification_metrics": verification_metrics,
        "problem_locations": problem_locations,
        "problem_areas": problem_areas,
        "incident_breakdown": incident_breakdown,
        "feedback_breakdown": feedback_breakdown,
        "recommendation_inputs": recommendation_inputs,
        "source_index": source_index,
    }

from typing import Optional
from uuid import UUID

from sqlalchemy import case, func
from sqlalchemy.orm import Query, Session

from .. import models


ESTADOS_ABIERTOS = ("abierto", "asignado", "en_proceso")
ESTADOS_RESUELTOS = ("resuelto", "cerrado")

TIPO_PUBLICO_MAP = {
    "feedback_negativo": "Seguimiento por feedback",
    "actividad_no_finalizada": "Actividad con seguimiento",
    "comentario_empleado": "Observacion operativa",
    "evidencia_faltante": "Evidencia pendiente",
    "geolocalizacion_fallida": "Verificacion de ubicacion",
    "manual": "Incidencia de servicio",
}


def build_company_incidentes_query(db: Session, company_id: UUID) -> Query:
    return db.query(models.Incidente).filter(
        models.Incidente.company_id == company_id,
    )


def build_cliente_incidentes_query(
    db: Session,
    company_id: UUID,
    empresa_ids: list[UUID],
) -> Query:
    return db.query(models.Incidente).filter(
        models.Incidente.company_id == company_id,
        models.Incidente.empresa_id.isnot(None),
        models.Incidente.empresa_id.in_(empresa_ids),
    )


def aplicar_filtro_fecha_incidentes(
    query: Query,
    desde,
    hasta,
    columna=models.Incidente.creado_en,
) -> Query:
    if desde:
        query = query.filter(columna >= desde)
    if hasta:
        query = query.filter(columna <= hasta)
    return query


def promedio_resolucion_horas(query: Query) -> float:
    incidentes = query.filter(models.Incidente.resuelto_en.isnot(None)).all()
    if not incidentes:
        return 0.0

    total_horas = 0.0
    for incidente in incidentes:
        total_horas += (incidente.resuelto_en - incidente.creado_en).total_seconds() / 3600

    return round(total_horas / len(incidentes), 2)


def serialize_incidente_dashboard(
    incidente: models.Incidente,
    locacion_nombre: Optional[str],
    area_nombre: Optional[str],
    empresa_nombre: Optional[str],
):
    return {
        "id": incidente.id,
        "estado": incidente.estado,
        "tipo": incidente.tipo,
        "prioridad": incidente.prioridad,
        "locacion_id": incidente.locacion_id,
        "locacion_nombre": locacion_nombre,
        "area_id": incidente.area_id,
        "area_nombre": area_nombre,
        "empresa_id": incidente.empresa_id,
        "empresa_nombre": empresa_nombre,
        "creado_en": incidente.creado_en,
        "resuelto_en": incidente.resuelto_en,
    }


def serialize_incidente_cliente(
    incidente: models.Incidente,
    locacion_nombre: Optional[str],
    area_nombre: Optional[str],
):
    tiempo_respuesta_horas = None
    if incidente.resuelto_en is not None:
        tiempo_respuesta_horas = round(
            (incidente.resuelto_en - incidente.creado_en).total_seconds() / 3600,
            2,
        )

    return {
        "id": incidente.id,
        "estado": incidente.estado,
        "tipo_publico": TIPO_PUBLICO_MAP.get(incidente.tipo, "Incidencia de servicio"),
        "locacion_nombre": locacion_nombre,
        "area_nombre": area_nombre,
        "creado_en": incidente.creado_en,
        "resuelto_en": incidente.resuelto_en,
        "evidencia_resolucion": incidente.evidencia_resolucion,
        "foto_resolucion": incidente.foto_resolucion,
        "tiempo_respuesta_horas": tiempo_respuesta_horas,
    }


def query_incidentes_con_contexto(query: Query) -> Query:
    return (
        query
        .outerjoin(models.Locacion, models.Incidente.locacion_id == models.Locacion.id)
        .outerjoin(models.Area, models.Incidente.area_id == models.Area.id)
        .outerjoin(models.Empresa, models.Incidente.empresa_id == models.Empresa.id)
        .add_columns(
            models.Locacion.nombre.label("locacion_nombre"),
            models.Area.nombre.label("area_nombre"),
            models.Empresa.nombre.label("empresa_nombre"),
        )
    )


def top_locaciones_con_incidentes(query: Query, limit: int = 5):
    return (
        query
        .outerjoin(models.Locacion, models.Incidente.locacion_id == models.Locacion.id)
        .outerjoin(models.Empresa, models.Incidente.empresa_id == models.Empresa.id)
        .filter(models.Incidente.locacion_id.isnot(None))
        .with_entities(
            models.Incidente.locacion_id.label("locacion_id"),
            models.Locacion.nombre.label("locacion_nombre"),
            models.Empresa.nombre.label("empresa_nombre"),
            func.count(models.Incidente.id).label("total_incidentes"),
            func.sum(
                case(
                    (models.Incidente.estado.in_(ESTADOS_ABIERTOS), 1),
                    else_=0,
                )
            ).label("incidentes_abiertos"),
        )
        .group_by(
            models.Incidente.locacion_id,
            models.Locacion.nombre,
            models.Empresa.nombre,
        )
        .order_by(func.count(models.Incidente.id).desc(), models.Locacion.nombre.asc())
        .limit(limit)
        .all()
    )


def top_areas_con_seguimiento(query: Query, limit: int = 5):
    return (
        query
        .outerjoin(models.Locacion, models.Incidente.locacion_id == models.Locacion.id)
        .outerjoin(models.Area, models.Incidente.area_id == models.Area.id)
        .with_entities(
            models.Incidente.locacion_id.label("locacion_id"),
            models.Locacion.nombre.label("locacion_nombre"),
            models.Incidente.area_id.label("area_id"),
            models.Area.nombre.label("area_nombre"),
            func.count(models.Incidente.id).label("total_seguimientos"),
            func.sum(
                case(
                    (models.Incidente.estado.in_(ESTADOS_ABIERTOS), 1),
                    else_=0,
                )
            ).label("seguimientos_abiertos"),
        )
        .group_by(
            models.Incidente.locacion_id,
            models.Locacion.nombre,
            models.Incidente.area_id,
            models.Area.nombre,
        )
        .order_by(func.count(models.Incidente.id).desc(), models.Locacion.nombre.asc())
        .limit(limit)
        .all()
    )

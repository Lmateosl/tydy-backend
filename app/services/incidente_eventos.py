from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session, joinedload

from .. import models
from ..datetime_utils import utc_now_naive


TIPOS_EVENTO_INCIDENTE = {
    "creado",
    "comentario",
    "actualizado",
    "estado_cambiado",
    "asignacion_cambiada",
    "resuelto",
    "cerrado",
}


def _clean_metadata(metadata: Optional[dict[str, Any]]) -> dict[str, Any]:
    if not metadata:
        return {}
    return {key: value for key, value in metadata.items() if value is not None}


def registrar_evento_incidente(
    db: Session,
    *,
    incidente: models.Incidente,
    tipo_evento: str,
    actor: Optional[models.Usuario],
    mensaje: Optional[str] = None,
    foto_url: Optional[str] = None,
    foto_public_id: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
    created_at=None,
) -> models.IncidenteEvento:
    if tipo_evento not in TIPOS_EVENTO_INCIDENTE:
        raise ValueError(f"tipo_evento inválido: {tipo_evento}")

    timestamp = created_at or utc_now_naive()
    evento = models.IncidenteEvento(
        incidente_id=incidente.id,
        company_id=incidente.company_id,
        tipo_evento=tipo_evento,
        actor_id=actor.id if actor else None,
        actor_rol=(actor.rol if actor and actor.rol else None),
        mensaje=mensaje,
        foto_url=foto_url,
        foto_public_id=foto_public_id,
        metadata_json=_clean_metadata(metadata),
        creado_en=timestamp,
    )
    db.add(evento)
    incidente.ultimo_evento_en = timestamp
    return evento


def registrar_evento_creado(
    db: Session,
    *,
    incidente: models.Incidente,
    actor: Optional[models.Usuario],
    origen: str,
    mensaje: Optional[str] = "Incidente creado",
) -> models.IncidenteEvento:
    return registrar_evento_incidente(
        db,
        incidente=incidente,
        tipo_evento="creado",
        actor=actor,
        mensaje=mensaje,
        metadata={
            "origen": origen,
            "tipo_incidente": incidente.tipo,
            "estado": incidente.estado,
            "prioridad": incidente.prioridad,
            "descripcion": incidente.descripcion,
            "empresa_id": str(incidente.empresa_id) if incidente.empresa_id else None,
            "locacion_id": str(incidente.locacion_id) if incidente.locacion_id else None,
            "area_id": str(incidente.area_id) if incidente.area_id else None,
            "empleado_id": str(incidente.empleado_id) if incidente.empleado_id else None,
            "supervisor_id": str(incidente.supervisor_id) if incidente.supervisor_id else None,
            "asignado_a_id": str(incidente.asignado_a_id) if incidente.asignado_a_id else None,
            "actividad_usuario_id": (
                str(incidente.actividad_usuario_id) if incidente.actividad_usuario_id else None
            ),
            "feedback_id": str(incidente.feedback_id) if incidente.feedback_id else None,
        },
        created_at=incidente.creado_en or utc_now_naive(),
    )


def registrar_evento_actualizado(
    db: Session,
    *,
    incidente: models.Incidente,
    actor: Optional[models.Usuario],
    cambios: dict[str, dict[str, Any]],
    tipo_evento: str = "actualizado",
    mensaje: Optional[str] = None,
) -> Optional[models.IncidenteEvento]:
    cambios_limpios = _clean_metadata(cambios)
    if not cambios_limpios:
        return None

    return registrar_evento_incidente(
        db,
        incidente=incidente,
        tipo_evento=tipo_evento,
        actor=actor,
        mensaje=mensaje,
        metadata={"cambios": cambios_limpios},
    )


def registrar_evento_resuelto(
    db: Session,
    *,
    incidente: models.Incidente,
    actor: Optional[models.Usuario],
    evidencia_resolucion: Optional[str],
    foto_url: Optional[str],
    foto_public_id: Optional[str] = None,
    estado_anterior: Optional[str] = None,
) -> models.IncidenteEvento:
    return registrar_evento_incidente(
        db,
        incidente=incidente,
        tipo_evento="resuelto",
        actor=actor,
        mensaje=evidencia_resolucion or "Incidente resuelto",
        foto_url=foto_url,
        foto_public_id=foto_public_id,
        metadata={
            "estado_anterior": estado_anterior,
            "estado_nuevo": incidente.estado,
            "evidencia_resolucion": evidencia_resolucion,
        },
    )


def registrar_evento_cerrado(
    db: Session,
    *,
    incidente: models.Incidente,
    actor: Optional[models.Usuario],
    estado_anterior: Optional[str] = None,
) -> models.IncidenteEvento:
    return registrar_evento_incidente(
        db,
        incidente=incidente,
        tipo_evento="cerrado",
        actor=actor,
        mensaje="Incidente cerrado",
        metadata={
            "estado_anterior": estado_anterior,
            "estado_nuevo": incidente.estado,
        },
    )


def registrar_evento_comentario(
    db: Session,
    *,
    incidente: models.Incidente,
    actor: Optional[models.Usuario],
    mensaje: Optional[str],
    foto_url: Optional[str] = None,
    foto_public_id: Optional[str] = None,
) -> models.IncidenteEvento:
    return registrar_evento_incidente(
        db,
        incidente=incidente,
        tipo_evento="comentario",
        actor=actor,
        mensaje=mensaje,
        foto_url=foto_url,
        foto_public_id=foto_public_id,
    )


def build_incidente_timeline_query(db: Session, incidente_id, company_id):
    return (
        db.query(models.IncidenteEvento)
        .options(joinedload(models.IncidenteEvento.actor))
        .filter(
            models.IncidenteEvento.incidente_id == incidente_id,
            models.IncidenteEvento.company_id == company_id,
        )
        .order_by(models.IncidenteEvento.creado_en.desc(), models.IncidenteEvento.id.desc())
    )

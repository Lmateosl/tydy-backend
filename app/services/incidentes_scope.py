from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Query, Session

from .. import models
from ..models import Usuario


def apply_incidente_visibility_scope(query: Query, current_user: Usuario) -> Query:
    rol = (current_user.rol or "").lower()

    query = query.filter(
        models.Incidente.company_id == current_user.company_id,
    )

    if rol == "admin":
        return query

    if rol == "supervisor":
        locaciones_supervisadas = (
            query.session.query(models.Locacion.id)
            .filter(
                models.Locacion.company_id == current_user.company_id,
                models.Locacion.supervisor_id == current_user.id,
            )
            .subquery()
        )
        areas_de_locaciones_supervisadas = (
            query.session.query(models.Area.id)
            .join(models.Locacion, models.Area.locacion_id == models.Locacion.id)
            .filter(
                models.Area.company_id == current_user.company_id,
                models.Locacion.company_id == current_user.company_id,
                models.Locacion.supervisor_id == current_user.id,
            )
            .subquery()
        )

        return query.filter(
            or_(
                models.Incidente.locacion_id.in_(locaciones_supervisadas),
                models.Incidente.area_id.in_(areas_de_locaciones_supervisadas),
                models.Incidente.asignado_a_id == current_user.id,
            )
        )

    if rol == "empleado":
        return query.filter(
            models.Incidente.asignado_a_id == current_user.id
        )

    raise HTTPException(status_code=403, detail="No tienes permisos")


def obtener_incidente_visible_o_404(
    db: Session,
    incidente_id: UUID,
    current_user: Usuario,
):
    incidente = (
        apply_incidente_visibility_scope(
            db.query(models.Incidente),
            current_user,
        )
        .filter(models.Incidente.id == incidente_id)
        .first()
    )
    if not incidente:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")
    return incidente

from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .. import models


def _validar_usuario_company(
    db: Session,
    usuario_id: Optional[UUID],
    company_id: UUID,
    campo: str,
    roles_permitidos: Optional[list[str]] = None,
):
    if usuario_id is None:
        return None

    usuario = db.query(models.Usuario).filter(
        models.Usuario.id == usuario_id,
        models.Usuario.company_id == company_id,
    ).first()
    if not usuario:
        raise HTTPException(status_code=400, detail=f"{campo} no pertenece a la compañía")

    if roles_permitidos and usuario.rol.lower() not in roles_permitidos:
        raise HTTPException(status_code=400, detail=f"{campo} tiene un rol no válido")

    return usuario


def resolve_incidente_context(
    db: Session,
    *,
    company_id: UUID,
    empresa_id: Optional[UUID],
    locacion_id: Optional[UUID],
    area_id: Optional[UUID],
    empleado_id: Optional[UUID],
    asignado_a_id: Optional[UUID],
    actividad_usuario_id: Optional[UUID],
    feedback_id: Optional[UUID],
):
    empresa = None
    locacion = None
    area = None
    actividad = None
    feedback = None

    if empresa_id is not None:
        empresa = db.query(models.Empresa).filter(
            models.Empresa.id == empresa_id,
            models.Empresa.company_id == company_id,
        ).first()
        if not empresa:
            raise HTTPException(status_code=400, detail="empresa_id no pertenece a la compañía")

    if locacion_id is not None:
        locacion = db.query(models.Locacion).filter(
            models.Locacion.id == locacion_id,
            models.Locacion.company_id == company_id,
        ).first()
        if not locacion:
            raise HTTPException(status_code=400, detail="locacion_id no pertenece a la compañía")

    if area_id is not None:
        area = db.query(models.Area).filter(
            models.Area.id == area_id,
            models.Area.company_id == company_id,
        ).first()
        if not area:
            raise HTTPException(status_code=400, detail="area_id no pertenece a la compañía")

    if locacion and area and area.locacion_id != locacion.id:
        raise HTTPException(status_code=400, detail="El área no pertenece a la locación indicada")

    locacion_efectiva = locacion or (area.locacion if area else None)
    if locacion_efectiva and locacion_efectiva.company_id != company_id:
        raise HTTPException(status_code=400, detail="locacion_id no pertenece a la compañía")

    if empresa and locacion_efectiva and locacion_efectiva.empresa_id != empresa.id:
        raise HTTPException(status_code=400, detail="La locación no pertenece a la empresa indicada")

    empleado = _validar_usuario_company(
        db,
        empleado_id,
        company_id,
        "empleado_id",
        roles_permitidos=["empleado"],
    )
    asignado_a = _validar_usuario_company(
        db,
        asignado_a_id,
        company_id,
        "asignado_a_id",
        roles_permitidos=["admin", "supervisor", "empleado"],
    )

    if actividad_usuario_id is not None:
        actividad = db.query(models.ActividadUsuario).filter(
            models.ActividadUsuario.id == actividad_usuario_id,
            models.ActividadUsuario.company_id == company_id,
        ).first()
        if not actividad:
            raise HTTPException(status_code=400, detail="actividad_usuario_id no pertenece a la compañía")

        if empleado and actividad.usuario_id and actividad.usuario_id != empleado.id:
            raise HTTPException(status_code=400, detail="La actividad no corresponde al empleado indicado")

        if area:
            usuario_actividad = db.query(models.Usuario).filter(
                models.Usuario.id == actividad.usuario_id
            ).first()
            if usuario_actividad and usuario_actividad.area_id and usuario_actividad.area_id != area.id:
                raise HTTPException(status_code=400, detail="La actividad no corresponde al área indicada")

    if feedback_id is not None:
        feedback = db.query(models.Feedback).filter(
            models.Feedback.id == feedback_id,
            models.Feedback.company_id == company_id,
        ).first()
        if not feedback:
            raise HTTPException(status_code=400, detail="feedback_id no pertenece a la compañía")
        if empresa and feedback.empresa_id and feedback.empresa_id != empresa.id:
            raise HTTPException(status_code=400, detail="El feedback no corresponde a la empresa indicada")

    supervisor_efectivo = None
    if locacion_efectiva and locacion_efectiva.supervisor_id is not None:
        supervisor_efectivo = _validar_usuario_company(
            db,
            locacion_efectiva.supervisor_id,
            company_id,
            "supervisor_efectivo",
            roles_permitidos=["supervisor", "admin"],
        )

    return {
        "empresa": empresa,
        "locacion": locacion,
        "area": area,
        "locacion_efectiva": locacion_efectiva,
        "supervisor_efectivo": supervisor_efectivo,
        "empleado": empleado,
        "asignado_a": asignado_a,
        "actividad": actividad,
        "feedback": feedback,
    }

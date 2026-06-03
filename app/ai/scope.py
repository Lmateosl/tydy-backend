"""Scope helpers for future AI report authorization."""

from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID

from fastapi import HTTPException

from app import models


@dataclass
class ReportScopeContext:
    company_id: UUID
    scope_type: str
    scope_entity_id: Optional[UUID]
    scope_label: str
    visible_empresa_ids: list[UUID] = field(default_factory=list)
    visible_locacion_ids: list[UUID] = field(default_factory=list)


def resolve_report_scope(db, current_user, scope_type, scope_entity_id):
    if current_user.rol != "admin":
        raise HTTPException(status_code=403, detail="No tienes permisos para usar AI Reports")

    if not current_user.company_id:
        raise HTTPException(status_code=404, detail="Usuario no pertenece a ninguna compañía")

    if scope_type == "company":
        if scope_entity_id is not None:
            raise HTTPException(status_code=400, detail="scope_entity_id debe ser null para scope company")
        return ReportScopeContext(
            company_id=current_user.company_id,
            scope_type=scope_type,
            scope_entity_id=None,
            scope_label="Compañía",
        )

    if scope_type == "empresa":
        if scope_entity_id is None:
            raise HTTPException(status_code=400, detail="scope_entity_id es requerido para scope empresa")

        empresa = (
            db.query(models.Empresa)
            .filter(
                models.Empresa.id == scope_entity_id,
                models.Empresa.company_id == current_user.company_id,
            )
            .first()
        )
        if not empresa:
            raise HTTPException(status_code=404, detail="Empresa no encontrada")

        locacion_ids = [
            row[0]
            for row in db.query(models.Locacion.id).filter(
                models.Locacion.empresa_id == empresa.id,
                models.Locacion.company_id == current_user.company_id,
            ).all()
        ]

        return ReportScopeContext(
            company_id=current_user.company_id,
            scope_type=scope_type,
            scope_entity_id=empresa.id,
            scope_label=empresa.nombre,
            visible_empresa_ids=[empresa.id],
            visible_locacion_ids=locacion_ids,
        )

    if scope_type == "locacion":
        if scope_entity_id is None:
            raise HTTPException(status_code=400, detail="scope_entity_id es requerido para scope locacion")

        locacion = (
            db.query(models.Locacion)
            .filter(
                models.Locacion.id == scope_entity_id,
                models.Locacion.company_id == current_user.company_id,
            )
            .first()
        )
        if not locacion:
            raise HTTPException(status_code=404, detail="Locación no encontrada")

        visible_empresa_ids = [locacion.empresa_id] if locacion.empresa_id else []

        return ReportScopeContext(
            company_id=current_user.company_id,
            scope_type=scope_type,
            scope_entity_id=locacion.id,
            scope_label=locacion.nombre,
            visible_empresa_ids=visible_empresa_ids,
            visible_locacion_ids=[locacion.id],
        )

    raise HTTPException(status_code=400, detail="scope_type no válido")

from __future__ import annotations

from collections.abc import Iterable
from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..datetime_utils import utc_now_naive


def crear_notificacion(
    db: Session,
    *,
    company_id: UUID,
    tipo: str,
    categoria: str,
    evento: str,
    titulo: str,
    mensaje: str,
    severity: str = "info",
    actor_id: UUID | None = None,
    source_type: str | None = None,
    source_id: UUID | None = None,
    source_event_id: UUID | None = None,
    deep_link: str | None = None,
    metadata: Optional[dict] = None,
    dedupe_key: str | None = None,
) -> models.Notificacion:
    if actor_id is not None:
        actor = db.query(models.Usuario).filter(
            models.Usuario.id == actor_id,
            models.Usuario.company_id == company_id,
        ).first()
        if actor is None:
            raise HTTPException(status_code=400, detail="actor_id no pertenece a la compañía")

    notificacion = models.Notificacion(
        company_id=company_id,
        actor_id=actor_id,
        tipo=tipo,
        categoria=categoria,
        evento=evento,
        severity=severity,
        titulo=titulo.strip(),
        mensaje=mensaje.strip(),
        source_type=source_type,
        source_id=source_id,
        source_event_id=source_event_id,
        deep_link=deep_link.strip() if isinstance(deep_link, str) and deep_link.strip() else None,
        metadata_json=metadata or {},
        dedupe_key=dedupe_key.strip() if isinstance(dedupe_key, str) and dedupe_key.strip() else None,
        creado_en=utc_now_naive(),
    )
    db.add(notificacion)
    db.flush()
    return notificacion


def crear_notificacion_para_usuarios(
    db: Session,
    *,
    notificacion: models.Notificacion,
    usuarios: Iterable[models.Usuario],
) -> list[models.NotificacionDestinatario]:
    usuarios_unicos: dict[UUID, models.Usuario] = {}
    for usuario in usuarios:
        if usuario is None or usuario.id is None:
            continue
        if usuario.company_id != notificacion.company_id:
            raise HTTPException(status_code=400, detail="Usuario destinatario fuera de la compañía")
        usuarios_unicos[usuario.id] = usuario

    if not usuarios_unicos:
        return []

    ahora = utc_now_naive()
    destinatarios: list[models.NotificacionDestinatario] = []
    for usuario in usuarios_unicos.values():
        destinatario = models.NotificacionDestinatario(
            notification_id=notificacion.id,
            user_id=usuario.id,
            company_id=notificacion.company_id,
            delivered_at=ahora,
            creado_en=ahora,
        )
        db.add(destinatario)
        destinatarios.append(destinatario)

    db.flush()
    return destinatarios


def marcar_leida(
    db: Session,
    *,
    destinatario_id: UUID,
    current_user: models.Usuario,
) -> models.NotificacionDestinatario:
    destinatario = db.query(models.NotificacionDestinatario).filter(
        models.NotificacionDestinatario.id == destinatario_id,
        models.NotificacionDestinatario.user_id == current_user.id,
        models.NotificacionDestinatario.company_id == current_user.company_id,
        models.NotificacionDestinatario.hidden_at.is_(None),
    ).first()
    if destinatario is None:
        raise HTTPException(status_code=404, detail="Notificación no encontrada")

    if destinatario.read_at is None:
        destinatario.read_at = utc_now_naive()
        db.flush()

    return destinatario


def marcar_todas_leidas(
    db: Session,
    *,
    current_user: models.Usuario,
) -> int:
    ahora = utc_now_naive()
    updated = db.query(models.NotificacionDestinatario).filter(
        models.NotificacionDestinatario.user_id == current_user.id,
        models.NotificacionDestinatario.company_id == current_user.company_id,
        models.NotificacionDestinatario.read_at.is_(None),
        models.NotificacionDestinatario.hidden_at.is_(None),
    ).update(
        {models.NotificacionDestinatario.read_at: ahora},
        synchronize_session=False,
    )
    db.flush()
    return updated


def resolver_destinatarios(*args, **kwargs):
    raise NotImplementedError("resolver_destinatarios se implementará en una fase posterior")


def crear_desde_incidente_evento(*args, **kwargs):
    raise NotImplementedError("crear_desde_incidente_evento se implementará en una fase posterior")

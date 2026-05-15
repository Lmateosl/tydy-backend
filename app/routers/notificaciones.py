from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..auth.dependencies import get_current_user
from ..database import get_db
from ..models import Usuario
from ..services.notificaciones_service import marcar_leida, marcar_todas_leidas


router = APIRouter(prefix="/notificaciones", tags=["Notificaciones"])


def _validar_permisos(current_user: Usuario):
    if (current_user.rol or "").lower() not in ["admin", "supervisor", "empleado"]:
        raise HTTPException(status_code=403, detail="No tienes permisos")


def _serialize_destinatario(destinatario: models.NotificacionDestinatario) -> schemas.NotificacionItemResponse:
    notificacion = destinatario.notificacion
    actor = notificacion.actor
    return schemas.NotificacionItemResponse(
        id=destinatario.id,
        notification_id=notificacion.id,
        user_id=destinatario.user_id,
        tipo=notificacion.tipo,
        categoria=notificacion.categoria,
        evento=notificacion.evento,
        severity=notificacion.severity,
        titulo=notificacion.titulo,
        mensaje=notificacion.mensaje,
        source_type=notificacion.source_type,
        source_id=notificacion.source_id,
        source_event_id=notificacion.source_event_id,
        deep_link=notificacion.deep_link,
        metadata=notificacion.metadata_json or {},
        actor=schemas.NotificacionActorResponse(
            id=actor.id if actor else None,
            nombre=actor.nombre if actor else None,
            rol=actor.rol if actor else None,
        ) if actor else None,
        read_at=destinatario.read_at,
        delivered_at=destinatario.delivered_at,
        created_at=notificacion.creado_en,
    )


@router.get("/", response_model=schemas.NotificacionesListResponse)
def listar_notificaciones(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    solo_no_leidas: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    _validar_permisos(current_user)

    query = db.query(models.NotificacionDestinatario).options(
        joinedload(models.NotificacionDestinatario.notificacion).joinedload(models.Notificacion.actor)
    ).filter(
        models.NotificacionDestinatario.user_id == current_user.id,
        models.NotificacionDestinatario.company_id == current_user.company_id,
        models.NotificacionDestinatario.hidden_at.is_(None),
    )

    if solo_no_leidas:
        query = query.filter(models.NotificacionDestinatario.read_at.is_(None))

    total = query.count()
    items = query.order_by(
        models.NotificacionDestinatario.delivered_at.desc(),
        models.NotificacionDestinatario.id.desc(),
    ).offset(offset).limit(limit).all()

    return schemas.NotificacionesListResponse(
        items=[_serialize_destinatario(item) for item in items],
        total=total,
    )


@router.get("/unread-count", response_model=schemas.NotificacionesUnreadCountResponse)
def obtener_unread_count(
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    _validar_permisos(current_user)

    unread_count = db.query(models.NotificacionDestinatario).filter(
        models.NotificacionDestinatario.user_id == current_user.id,
        models.NotificacionDestinatario.company_id == current_user.company_id,
        models.NotificacionDestinatario.read_at.is_(None),
        models.NotificacionDestinatario.hidden_at.is_(None),
    ).count()

    return schemas.NotificacionesUnreadCountResponse(unread_count=unread_count)


@router.post("/{destinatario_id}/leer", response_model=schemas.NotificacionMarcarLeidaResponse)
def leer_notificacion(
    destinatario_id: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    _validar_permisos(current_user)
    destinatario = marcar_leida(
        db,
        destinatario_id=destinatario_id,
        current_user=current_user,
    )
    db.commit()
    db.refresh(destinatario)

    return schemas.NotificacionMarcarLeidaResponse(
        detail="Notificación marcada como leída",
        read_at=destinatario.read_at,
    )


@router.post("/leer-todas", response_model=schemas.NotificacionMarcarTodasLeidasResponse)
def leer_todas_notificaciones(
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    _validar_permisos(current_user)
    updated = marcar_todas_leidas(
        db,
        current_user=current_user,
    )
    db.commit()

    return schemas.NotificacionMarcarTodasLeidasResponse(
        detail="Notificaciones marcadas como leídas",
        updated=updated,
    )

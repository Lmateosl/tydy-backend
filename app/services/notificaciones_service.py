from __future__ import annotations

from collections.abc import Iterable
from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models, schemas
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


def _asegurar_destinatarios_faltantes(
    db: Session,
    *,
    notificacion: models.Notificacion,
    usuarios: Iterable[models.Usuario],
) -> list[models.NotificacionDestinatario]:
    usuarios = [usuario for usuario in usuarios if usuario is not None and usuario.id is not None]
    if not usuarios:
        return []

    existentes = {
        user_id for (user_id,) in db.query(models.NotificacionDestinatario.user_id).filter(
            models.NotificacionDestinatario.notification_id == notificacion.id,
            models.NotificacionDestinatario.user_id.in_([usuario.id for usuario in usuarios]),
        ).all()
    }
    faltantes = [usuario for usuario in usuarios if usuario.id not in existentes]
    if not faltantes:
        return []

    return crear_notificacion_para_usuarios(
        db,
        notificacion=notificacion,
        usuarios=faltantes,
    )


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
    db: Session = kwargs["db"]
    company_id: UUID = kwargs["company_id"]
    audiencia_tipo: str = kwargs["audiencia_tipo"]
    actor_id: UUID | None = kwargs.get("actor_id")
    rol: str | None = kwargs.get("rol")
    user_ids: list[UUID] | None = kwargs.get("user_ids")
    excluir_cliente: bool = kwargs.get("excluir_cliente", True)
    excluir_actor: bool = kwargs.get("excluir_actor", True)

    if audiencia_tipo == "users":
        if not user_ids:
            return []
        query = db.query(models.Usuario).filter(
            models.Usuario.company_id == company_id,
            models.Usuario.id.in_(user_ids),
        )
        if excluir_cliente:
            query = query.filter(models.Usuario.rol != "cliente")
        usuarios = query.all()
    elif audiencia_tipo == "role":
        if not rol:
            return []
        query = db.query(models.Usuario).filter(
            models.Usuario.company_id == company_id,
            models.Usuario.rol == rol,
        )
        if excluir_cliente:
            query = query.filter(models.Usuario.rol != "cliente")
        usuarios = query.all()
    else:
        raise ValueError(f"audiencia_tipo no soportada: {audiencia_tipo}")

    usuarios_unicos: dict[UUID, models.Usuario] = {}
    for usuario in usuarios:
        if usuario.id is None:
            continue
        if excluir_actor and actor_id is not None and usuario.id == actor_id:
            continue
        if excluir_cliente and (usuario.rol or "").lower() == "cliente":
            continue
        usuarios_unicos[usuario.id] = usuario

    return list(usuarios_unicos.values())


def _normalizar_rol(valor: str | None) -> str:
    return (valor or "").strip().lower()


def _obtener_empresa_company_o_400(db: Session, *, empresa_id: UUID, company_id: UUID) -> models.Empresa:
    empresa = db.query(models.Empresa).filter(
        models.Empresa.id == empresa_id,
        models.Empresa.company_id == company_id,
    ).first()
    if empresa is None:
        raise HTTPException(status_code=400, detail="empresa_id no pertenece a la compañía")
    return empresa


def _obtener_locacion_company_o_400(db: Session, *, locacion_id: UUID, company_id: UUID) -> models.Locacion:
    locacion = db.query(models.Locacion).filter(
        models.Locacion.id == locacion_id,
        models.Locacion.company_id == company_id,
    ).first()
    if locacion is None:
        raise HTTPException(status_code=400, detail="locacion_id no pertenece a la compañía")
    return locacion


def _usuarios_de_locacion(
    db: Session,
    *,
    company_id: UUID,
    locacion_id: UUID,
) -> list[models.Usuario]:
    usuarios_area = (
        db.query(models.Usuario)
        .join(models.Area, models.Usuario.area_id == models.Area.id)
        .filter(
            models.Usuario.company_id == company_id,
            models.Area.company_id == company_id,
            models.Area.locacion_id == locacion_id,
        )
        .all()
    )
    supervisores = (
        db.query(models.Usuario)
        .join(models.Locacion, models.Locacion.supervisor_id == models.Usuario.id)
        .filter(
            models.Usuario.company_id == company_id,
            models.Locacion.company_id == company_id,
            models.Locacion.id == locacion_id,
        )
        .all()
    )

    usuarios_unicos: dict[UUID, models.Usuario] = {}
    for usuario in [*usuarios_area, *supervisores]:
        if usuario.id is not None:
            usuarios_unicos[usuario.id] = usuario
    return list(usuarios_unicos.values())


def _usuarios_de_empresa(
    db: Session,
    *,
    company_id: UUID,
    empresa_id: UUID,
) -> list[models.Usuario]:
    usuarios_area = (
        db.query(models.Usuario)
        .join(models.Area, models.Usuario.area_id == models.Area.id)
        .join(models.Locacion, models.Area.locacion_id == models.Locacion.id)
        .filter(
            models.Usuario.company_id == company_id,
            models.Area.company_id == company_id,
            models.Locacion.company_id == company_id,
            models.Locacion.empresa_id == empresa_id,
        )
        .all()
    )
    supervisores = (
        db.query(models.Usuario)
        .join(models.Locacion, models.Locacion.supervisor_id == models.Usuario.id)
        .filter(
            models.Usuario.company_id == company_id,
            models.Locacion.company_id == company_id,
            models.Locacion.empresa_id == empresa_id,
        )
        .all()
    )

    usuarios_unicos: dict[UUID, models.Usuario] = {}
    for usuario in [*usuarios_area, *supervisores]:
        if usuario.id is not None:
            usuarios_unicos[usuario.id] = usuario
    return list(usuarios_unicos.values())


def _locaciones_supervisadas_ids(db: Session, *, current_user: models.Usuario) -> set[UUID]:
    return {
        locacion_id
        for (locacion_id,) in db.query(models.Locacion.id).filter(
            models.Locacion.company_id == current_user.company_id,
            models.Locacion.supervisor_id == current_user.id,
        ).all()
        if locacion_id is not None
    }


def _usuarios_scope_supervisor(
    db: Session,
    *,
    current_user: models.Usuario,
) -> dict[UUID, models.Usuario]:
    locaciones_ids = _locaciones_supervisadas_ids(db, current_user=current_user)
    if not locaciones_ids:
        return {}

    usuarios = (
        db.query(models.Usuario)
        .outerjoin(models.Area, models.Usuario.area_id == models.Area.id)
        .outerjoin(
            models.Locacion,
            or_(
                models.Area.locacion_id == models.Locacion.id,
                models.Locacion.supervisor_id == models.Usuario.id,
            ),
        )
        .filter(
            models.Usuario.company_id == current_user.company_id,
            models.Locacion.company_id == current_user.company_id,
            models.Locacion.id.in_(locaciones_ids),
        )
        .all()
    )

    return {
        usuario.id: usuario
        for usuario in usuarios
        if usuario.id is not None
    }


def resolver_destinatarios_alerta_manual(
    db: Session,
    *,
    payload: schemas.AlertaManualCreate,
    current_user: models.Usuario,
) -> list[models.Usuario]:
    rol_actor = _normalizar_rol(current_user.rol)
    company_id = current_user.company_id
    actor_id = current_user.id

    if company_id is None or actor_id is None:
        raise HTTPException(status_code=400, detail="El usuario actual no tiene company válida")

    audiencia_tipo = payload.audiencia_tipo
    usuarios: list[models.Usuario]

    if audiencia_tipo == "all":
        usuarios = db.query(models.Usuario).filter(
            models.Usuario.company_id == company_id,
        ).all()
    elif audiencia_tipo == "role":
        if payload.rol is None:
            raise HTTPException(status_code=400, detail="rol es requerido para audiencia_tipo=role")
        usuarios = db.query(models.Usuario).filter(
            models.Usuario.company_id == company_id,
            models.Usuario.rol == payload.rol,
        ).all()
    elif audiencia_tipo == "empresa":
        if payload.empresa_id is None:
            raise HTTPException(status_code=400, detail="empresa_id es requerido para audiencia_tipo=empresa")
        _obtener_empresa_company_o_400(
            db,
            empresa_id=payload.empresa_id,
            company_id=company_id,
        )
        usuarios = _usuarios_de_empresa(
            db,
            company_id=company_id,
            empresa_id=payload.empresa_id,
        )
    elif audiencia_tipo == "locacion":
        if payload.locacion_id is None:
            raise HTTPException(status_code=400, detail="locacion_id es requerido para audiencia_tipo=locacion")
        locacion = _obtener_locacion_company_o_400(
            db,
            locacion_id=payload.locacion_id,
            company_id=company_id,
        )
        if rol_actor == "supervisor" and locacion.supervisor_id != actor_id:
            raise HTTPException(status_code=403, detail="No puedes enviar alertas fuera de tus locaciones")
        usuarios = _usuarios_de_locacion(
            db,
            company_id=company_id,
            locacion_id=locacion.id,
        )
    elif audiencia_tipo == "user":
        if not payload.user_ids:
            raise HTTPException(status_code=400, detail="user_ids es requerido para audiencia_tipo=user")
        usuarios = db.query(models.Usuario).filter(
            models.Usuario.company_id == company_id,
            models.Usuario.id.in_(payload.user_ids),
        ).all()
        encontrados = {
            usuario.id
            for usuario in usuarios
            if usuario.id is not None
        }
        solicitados = {user_id for user_id in payload.user_ids if user_id is not None}
        faltantes = solicitados - encontrados
        if faltantes:
            raise HTTPException(status_code=400, detail="Hay usuarios que no pertenecen a la compañía")

        if rol_actor == "supervisor":
            usuarios_en_scope = _usuarios_scope_supervisor(
                db,
                current_user=current_user,
            )
            fuera_de_scope = [
                usuario.id
                for usuario in usuarios
                if usuario.id is not None and usuario.id not in usuarios_en_scope
            ]
            if fuera_de_scope:
                raise HTTPException(
                    status_code=403,
                    detail="No puedes enviar alertas a usuarios fuera de tus locaciones",
                )
    else:
        raise HTTPException(status_code=400, detail="audiencia_tipo no soportada")

    usuarios_unicos: dict[UUID, models.Usuario] = {}
    for usuario in usuarios:
        if usuario is None or usuario.id is None:
            continue
        if usuario.company_id != company_id:
            continue
        if usuario.id == actor_id:
            continue
        if _normalizar_rol(usuario.rol) == "cliente":
            continue
        usuarios_unicos[usuario.id] = usuario

    destinatarios = list(usuarios_unicos.values())
    if not destinatarios:
        raise HTTPException(status_code=400, detail="No hay destinatarios válidos para la alerta")

    return destinatarios


def crear_alerta_manual(
    db: Session,
    *,
    payload: schemas.AlertaManualCreate,
    current_user: models.Usuario,
) -> tuple[models.Notificacion, int]:
    destinatarios = resolver_destinatarios_alerta_manual(
        db,
        payload=payload,
        current_user=current_user,
    )

    metadata = {
        "audiencia_tipo": payload.audiencia_tipo,
        "rol": payload.rol,
        "empresa_id": str(payload.empresa_id) if payload.empresa_id else None,
        "locacion_id": str(payload.locacion_id) if payload.locacion_id else None,
        "user_ids": [str(user_id) for user_id in payload.user_ids],
    }

    with db.begin_nested():
        notificacion = crear_notificacion(
            db,
            company_id=current_user.company_id,
            tipo="manual",
            categoria="operativa",
            evento="alerta_manual",
            titulo=payload.titulo,
            mensaje=payload.mensaje,
            severity=payload.severity,
            actor_id=current_user.id,
            source_type="alerta_manual",
            source_id=None,
            source_event_id=None,
            deep_link=None,
            metadata=metadata,
            dedupe_key=None,
        )
        crear_notificacion_para_usuarios(
            db,
            notificacion=notificacion,
            usuarios=destinatarios,
        )

    return notificacion, len(destinatarios)


def crear_desde_incidente_evento(
    db: Session,
    *,
    incidente: models.Incidente,
    evento: models.IncidenteEvento,
    actor: models.Usuario | None,
) -> models.Notificacion | None:
    if evento.id is None:
        db.flush()

    origen_evento = (evento.metadata_json or {}).get("origen")
    excluir_actor = origen_evento != "automatico"
    actor_id = actor.id if actor else None
    dedupe_key = f"incident-event:{evento.id}"

    evento_nombre = None
    titulo = None
    severity = "info"
    user_ids: list[UUID] = []

    if evento.tipo_evento == "creado":
        evento_nombre = "incidente_creado"
        titulo = "Nuevo incidente abierto"
        user_ids.extend([
            incidente.asignado_a_id,
            incidente.supervisor_id,
        ])
    elif evento.tipo_evento == "asignacion_cambiada":
        evento_nombre = "incidente_asignado"
        titulo = "Te asignaron un incidente"
        user_ids.extend([
            incidente.asignado_a_id,
            incidente.supervisor_id,
        ])
    elif evento.tipo_evento == "comentario":
        evento_nombre = "incidente_comentado"
        titulo = "Nuevo comentario en incidente"
        user_ids.extend([
            incidente.asignado_a_id,
            incidente.supervisor_id,
            incidente.creado_por,
        ])
    elif evento.tipo_evento == "resuelto":
        evento_nombre = "incidente_resuelto"
        titulo = "Incidente resuelto"
        user_ids.extend([
            incidente.supervisor_id,
            incidente.asignado_a_id,
            incidente.creado_por,
        ])
    elif evento.tipo_evento == "cerrado":
        evento_nombre = "incidente_cerrado"
        titulo = "Incidente cerrado"
        user_ids.extend([
            incidente.supervisor_id,
            incidente.asignado_a_id,
            incidente.creado_por,
        ])
    else:
        return None

    admins = resolver_destinatarios(
        db=db,
        company_id=incidente.company_id,
        audiencia_tipo="role",
        rol="admin",
        actor_id=actor_id,
        excluir_cliente=True,
        excluir_actor=excluir_actor,
    )
    usuarios_directos = resolver_destinatarios(
        db=db,
        company_id=incidente.company_id,
        audiencia_tipo="users",
        user_ids=[user_id for user_id in user_ids if user_id is not None],
        actor_id=actor_id,
        excluir_cliente=True,
        excluir_actor=excluir_actor,
    )

    destinatarios = {usuario.id: usuario for usuario in admins + usuarios_directos if usuario.id is not None}
    if not destinatarios:
        return None

    existente = db.query(models.Notificacion).filter(
        models.Notificacion.company_id == incidente.company_id,
        models.Notificacion.dedupe_key == dedupe_key,
    ).first()
    if existente is not None:
        _asegurar_destinatarios_faltantes(
            db,
            notificacion=existente,
            usuarios=destinatarios.values(),
        )
        return existente

    if evento_nombre in {"incidente_creado", "incidente_asignado"}:
        mensaje = incidente.descripcion
    elif evento_nombre == "incidente_comentado":
        mensaje = evento.mensaje or "Hay un nuevo comentario en el incidente."
    else:
        mensaje = incidente.descripcion

    metadata = {
        "incidente_id": str(incidente.id),
        "incidente_estado": incidente.estado,
        "incidente_tipo": incidente.tipo,
        "evento_id": str(evento.id),
        "evento_tipo": evento.tipo_evento,
    }

    try:
        with db.begin_nested():
            notificacion = crear_notificacion(
                db,
                company_id=incidente.company_id,
                tipo="automatica",
                categoria="incidente",
                evento=evento_nombre,
                titulo=titulo,
                mensaje=mensaje,
                severity=severity,
                actor_id=actor_id,
                source_type="incidente",
                source_id=incidente.id,
                source_event_id=evento.id,
                deep_link=f"/incidentes/{incidente.id}",
                metadata=metadata,
                dedupe_key=dedupe_key,
            )
            crear_notificacion_para_usuarios(
                db,
                notificacion=notificacion,
                usuarios=destinatarios.values(),
            )
        return notificacion
    except IntegrityError:
        existente = db.query(models.Notificacion).filter(
            models.Notificacion.company_id == incidente.company_id,
            models.Notificacion.dedupe_key == dedupe_key,
        ).first()
        if existente is not None:
            _asegurar_destinatarios_faltantes(
                db,
                notificacion=existente,
                usuarios=destinatarios.values(),
            )
        return existente

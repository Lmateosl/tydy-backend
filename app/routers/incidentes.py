from datetime import datetime
from typing import Optional
from uuid import UUID

import cloudinary.uploader
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Security
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth.dependencies import get_current_user
from ..database import get_db
from ..datetime_utils import utc_now_naive
from ..image_utils import compress_image
from ..models import Usuario
from ..services.incidentes_context import resolve_incidente_context
from ..services.incidente_eventos import (
    build_incidente_timeline_query,
    registrar_evento_actualizado,
    registrar_evento_cerrado,
    registrar_evento_comentario,
    registrar_evento_creado,
    registrar_evento_resuelto,
)
from ..services.notificaciones_service import crear_desde_incidente_evento
from ..services.incidentes_scope import (
    apply_incidente_visibility_scope,
    obtener_incidente_visible_o_404,
)


router = APIRouter(prefix="/incidentes", tags=["Incidentes"])


def _validar_permisos_lectura(current_user: Usuario):
    if current_user.rol.lower() not in ["admin", "supervisor", "empleado"]:
        raise HTTPException(status_code=403, detail="No tienes permisos")


def _validar_permisos_creacion_edicion(current_user: Usuario):
    if current_user.rol.lower() not in ["admin", "supervisor"]:
        raise HTTPException(status_code=403, detail="No tienes permisos")


def _validar_permisos_eliminacion(current_user: Usuario):
    if current_user.rol.lower() != "admin":
        raise HTTPException(status_code=403, detail="No tienes permisos")


def _obtener_incidente_o_404(db: Session, incidente_id: UUID, company_id: UUID):
    incidente = db.query(models.Incidente).filter(
        models.Incidente.id == incidente_id,
        models.Incidente.company_id == company_id,
    ).first()
    if not incidente:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")
    return incidente


def _supervisor_tiene_locacion(current_user: Usuario, locacion: Optional[models.Locacion]) -> bool:
    return locacion is not None and locacion.supervisor_id == current_user.id


def _obtener_incidente_para_accion(
    db: Session,
    incidente_id: UUID,
    current_user: Usuario,
):
    if current_user.rol.lower() == "admin":
        return _obtener_incidente_o_404(db, incidente_id, current_user.company_id)
    if current_user.rol.lower() == "supervisor":
        return obtener_incidente_visible_o_404(db, incidente_id, current_user)
    raise HTTPException(status_code=403, detail="No tienes permisos")


def _build_context_payload(
    *,
    empresa_id: Optional[UUID],
    locacion_id: Optional[UUID],
    area_id: Optional[UUID],
    empleado_id: Optional[UUID],
    asignado_a_id: Optional[UUID],
    actividad_usuario_id: Optional[UUID],
    feedback_id: Optional[UUID],
):
    return {
        "empresa_id": empresa_id,
        "locacion_id": locacion_id,
        "area_id": area_id,
        "empleado_id": empleado_id,
        "asignado_a_id": asignado_a_id,
        "actividad_usuario_id": actividad_usuario_id,
        "feedback_id": feedback_id,
    }


def _build_context_payload_from_incidente_update(update_data: dict, incidente: models.Incidente):
    return _build_context_payload(
        empresa_id=update_data["empresa_id"] if "empresa_id" in update_data else incidente.empresa_id,
        locacion_id=update_data["locacion_id"] if "locacion_id" in update_data else incidente.locacion_id,
        area_id=update_data["area_id"] if "area_id" in update_data else incidente.area_id,
        empleado_id=update_data["empleado_id"] if "empleado_id" in update_data else incidente.empleado_id,
        asignado_a_id=update_data["asignado_a_id"] if "asignado_a_id" in update_data else incidente.asignado_a_id,
        actividad_usuario_id=(
            update_data["actividad_usuario_id"]
            if "actividad_usuario_id" in update_data
            else incidente.actividad_usuario_id
        ),
        feedback_id=update_data["feedback_id"] if "feedback_id" in update_data else incidente.feedback_id,
    )


def _normalize_context_fields(data: dict, contexto: dict) -> dict:
    normalized = dict(data)
    locacion_efectiva = contexto["locacion_efectiva"]
    supervisor_efectivo = contexto["supervisor_efectivo"]
    normalized["locacion_id"] = locacion_efectiva.id if locacion_efectiva else None
    normalized["supervisor_id"] = supervisor_efectivo.id if supervisor_efectivo else None
    return normalized


def _validar_creacion_según_rol(current_user: Usuario, contexto: dict):
    if current_user.rol.lower() == "admin":
        return
    if current_user.rol.lower() != "supervisor":
        raise HTTPException(status_code=403, detail="No tienes permisos")
    if not _supervisor_tiene_locacion(current_user, contexto["locacion_efectiva"]):
        raise HTTPException(status_code=403, detail="No puedes crear incidentes fuera de tus locaciones")


def _validar_actualizacion_según_rol(current_user: Usuario, contexto_resultante: dict):
    if current_user.rol.lower() == "admin":
        return
    if current_user.rol.lower() != "supervisor":
        raise HTTPException(status_code=403, detail="No tienes permisos")
    if (
        not _supervisor_tiene_locacion(current_user, contexto_resultante["locacion_efectiva"])
        and not (
            contexto_resultante["asignado_a"] is not None
            and contexto_resultante["asignado_a"].id == current_user.id
        )
    ):
        raise HTTPException(status_code=403, detail="No puedes mover el incidente fuera de tu scope")


def _sincronizar_estado_y_fechas(incidente: models.Incidente):
    if incidente.estado != "resuelto":
        incidente.resuelto_en = None
    if incidente.estado != "cerrado":
        incidente.cerrado_en = None


def _strip_optional_text(value):
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def _serialize_event_value(value):
    if isinstance(value, UUID):
        return str(value)
    return value


def _build_incidente_snapshot(incidente: models.Incidente) -> dict:
    return {
        "tipo": incidente.tipo,
        "prioridad": incidente.prioridad,
        "descripcion": incidente.descripcion,
        "estado": incidente.estado,
        "empresa_id": incidente.empresa_id,
        "locacion_id": incidente.locacion_id,
        "area_id": incidente.area_id,
        "empleado_id": incidente.empleado_id,
        "supervisor_id": incidente.supervisor_id,
        "asignado_a_id": incidente.asignado_a_id,
        "actividad_usuario_id": incidente.actividad_usuario_id,
        "feedback_id": incidente.feedback_id,
        "evidencia_inicial": incidente.evidencia_inicial,
        "evidencia_resolucion": incidente.evidencia_resolucion,
    }


def _build_changes(original: dict, current: models.Incidente, fields: list[str]) -> dict:
    cambios = {}
    for field in fields:
        previous = _serialize_event_value(original.get(field))
        current_value = _serialize_event_value(getattr(current, field))
        if previous != current_value:
            cambios[field] = {
                "anterior": previous,
                "nuevo": current_value,
            }
    return cambios


def _upload_incidente_image(file_obj, *, folder: str):
    imagen_comprimida = compress_image(file_obj.file, quality=70)
    upload_result = cloudinary.uploader.upload(
        imagen_comprimida,
        folder=folder,
    )
    return (
        upload_result.get("secure_url"),
        upload_result.get("public_id"),
    )


@router.get("/", response_model=list[schemas.IncidenteResponse])
def listar_incidentes(
    estado: Optional[str] = Query(None),
    tipo: Optional[str] = Query(None),
    prioridad: Optional[str] = Query(None),
    empresa_id: Optional[UUID] = Query(None),
    locacion_id: Optional[UUID] = Query(None),
    area_id: Optional[UUID] = Query(None),
    empleado_id: Optional[UUID] = Query(None),
    supervisor_id: Optional[UUID] = Query(None),
    asignado_a_id: Optional[UUID] = Query(None),
    actividad_usuario_id: Optional[UUID] = Query(None),
    feedback_id: Optional[UUID] = Query(None),
    desde: Optional[datetime] = Query(None),
    hasta: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    _validar_permisos_lectura(current_user)

    query = apply_incidente_visibility_scope(
        db.query(models.Incidente),
        current_user,
    )

    if estado:
        query = query.filter(models.Incidente.estado == estado)
    if tipo:
        query = query.filter(models.Incidente.tipo == tipo)
    if prioridad:
        query = query.filter(models.Incidente.prioridad == prioridad)
    if empresa_id:
        query = query.filter(models.Incidente.empresa_id == empresa_id)
    if locacion_id:
        query = query.filter(models.Incidente.locacion_id == locacion_id)
    if area_id:
        query = query.filter(models.Incidente.area_id == area_id)
    if empleado_id:
        query = query.filter(models.Incidente.empleado_id == empleado_id)
    if supervisor_id:
        query = query.filter(models.Incidente.supervisor_id == supervisor_id)
    if asignado_a_id:
        query = query.filter(models.Incidente.asignado_a_id == asignado_a_id)
    if actividad_usuario_id:
        query = query.filter(models.Incidente.actividad_usuario_id == actividad_usuario_id)
    if feedback_id:
        query = query.filter(models.Incidente.feedback_id == feedback_id)
    if desde:
        query = query.filter(models.Incidente.ultimo_evento_en >= desde)
    if hasta:
        query = query.filter(models.Incidente.ultimo_evento_en <= hasta)

    return query.order_by(models.Incidente.ultimo_evento_en.desc()).all()


@router.get("/{incidente_id}", response_model=schemas.IncidenteResponse)
def obtener_incidente(
    incidente_id: UUID = Path(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    _validar_permisos_lectura(current_user)
    return obtener_incidente_visible_o_404(db, incidente_id, current_user)


@router.get("/{incidente_id}/timeline", response_model=schemas.IncidenteTimelineResponse)
def obtener_timeline_incidente(
    incidente_id: UUID = Path(...),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    _validar_permisos_lectura(current_user)
    incidente = obtener_incidente_visible_o_404(db, incidente_id, current_user)

    query = build_incidente_timeline_query(db, incidente.id, incidente.company_id)
    total = query.count()
    items = query.offset(offset).limit(limit).all()
    return {
        "items": items,
        "total": total,
    }


@router.post("/", response_model=schemas.IncidenteResponse)
def crear_incidente(
    payload: schemas.IncidenteCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    _validar_permisos_creacion_edicion(current_user)

    contexto = resolve_incidente_context(
        db=db,
        company_id=current_user.company_id,
        empresa_id=payload.empresa_id,
        locacion_id=payload.locacion_id,
        area_id=payload.area_id,
        empleado_id=payload.empleado_id,
        asignado_a_id=payload.asignado_a_id,
        actividad_usuario_id=payload.actividad_usuario_id,
        feedback_id=payload.feedback_id,
    )
    _validar_creacion_según_rol(current_user, contexto)

    payload_data = _normalize_context_fields(
        payload.dict(exclude_unset=True, exclude={"supervisor_id"}),
        contexto,
    )

    nuevo_incidente = models.Incidente(
        **payload_data,
        company_id=current_user.company_id,
        creado_por=current_user.id,
        estado="abierto",
        creado_en=utc_now_naive(),
        actualizado_en=utc_now_naive(),
    )
    db.add(nuevo_incidente)
    db.flush()
    evento = registrar_evento_creado(
        db,
        incidente=nuevo_incidente,
        actor=current_user,
        origen="manual",
    )
    crear_desde_incidente_evento(
        db,
        incidente=nuevo_incidente,
        evento=evento,
        actor=current_user,
    )
    db.commit()
    db.refresh(nuevo_incidente)
    return nuevo_incidente


@router.put("/{incidente_id}", response_model=schemas.IncidenteResponse)
def actualizar_incidente(
    payload: schemas.IncidenteUpdate,
    incidente_id: UUID = Path(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    _validar_permisos_creacion_edicion(current_user)
    incidente = _obtener_incidente_para_accion(db, incidente_id, current_user)
    incidente_original = _build_incidente_snapshot(incidente)

    update_data = payload.dict(exclude_unset=True, exclude={"supervisor_id"})

    contexto_resultante = resolve_incidente_context(
        db=db,
        company_id=current_user.company_id,
        **_build_context_payload_from_incidente_update(update_data, incidente),
    )
    _validar_actualizacion_según_rol(current_user, contexto_resultante)

    normalized_update_data = _normalize_context_fields(update_data, contexto_resultante)

    for key, value in normalized_update_data.items():
        setattr(incidente, key, value)

    if incidente.estado == "resuelto" and incidente.resuelto_en is None:
        incidente.resuelto_en = utc_now_naive()
    if incidente.estado == "cerrado" and incidente.cerrado_en is None:
        incidente.cerrado_en = utc_now_naive()

    _sincronizar_estado_y_fechas(incidente)
    incidente.actualizado_en = utc_now_naive()

    cambio_estado = _build_changes(incidente_original, incidente, ["estado"])
    cambio_asignacion = _build_changes(incidente_original, incidente, ["asignado_a_id"])
    cambios_generales = _build_changes(
        incidente_original,
        incidente,
        [
            "tipo",
            "prioridad",
            "descripcion",
            "empresa_id",
            "locacion_id",
            "area_id",
            "empleado_id",
            "supervisor_id",
            "actividad_usuario_id",
            "feedback_id",
            "evidencia_inicial",
            "evidencia_resolucion",
        ],
    )

    if cambio_estado:
        registrar_evento_actualizado(
            db,
            incidente=incidente,
            actor=current_user,
            cambios=cambio_estado,
            tipo_evento="estado_cambiado",
            mensaje="Estado del incidente actualizado",
        )
    if cambio_asignacion:
        evento_asignacion = registrar_evento_actualizado(
            db,
            incidente=incidente,
            actor=current_user,
            cambios=cambio_asignacion,
            tipo_evento="asignacion_cambiada",
            mensaje="Asignación del incidente actualizada",
        )
        if evento_asignacion is not None:
            crear_desde_incidente_evento(
                db,
                incidente=incidente,
                evento=evento_asignacion,
                actor=current_user,
            )
    if cambios_generales:
        registrar_evento_actualizado(
            db,
            incidente=incidente,
            actor=current_user,
            cambios=cambios_generales,
            tipo_evento="actualizado",
            mensaje="Incidente actualizado",
        )

    db.commit()
    db.refresh(incidente)
    return incidente


@router.delete("/{incidente_id}")
def eliminar_incidente(
    incidente_id: UUID = Path(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    _validar_permisos_eliminacion(current_user)
    incidente = _obtener_incidente_o_404(db, incidente_id, current_user.company_id)

    # TODO: Migrar a soft delete cuando este módulo pase a ser fuente formal de trazabilidad.
    db.delete(incidente)
    db.commit()
    return {"detail": "Incidente eliminado correctamente"}


@router.post("/{incidente_id}/resolver", response_model=schemas.IncidenteResponse)
async def resolver_incidente(
    request: Request,
    incidente_id: UUID = Path(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    if current_user.rol.lower() not in ["admin", "supervisor", "empleado"]:
        raise HTTPException(status_code=403, detail="No tienes permisos")

    if current_user.rol.lower() == "empleado":
        incidente = obtener_incidente_visible_o_404(db, incidente_id, current_user)
    else:
        incidente = _obtener_incidente_para_accion(db, incidente_id, current_user)

    if incidente.estado == "cerrado":
        raise HTTPException(status_code=400, detail="No se puede resolver un incidente cerrado")

    estado_anterior = incidente.estado
    evidencia_resolucion = None
    foto_resolucion_url = incidente.foto_resolucion
    foto_resolucion_public_id = None
    content_type = (request.headers.get("content-type") or "").lower()

    if "multipart/form-data" in content_type:
        form_data = await request.form()
        evidencia_resolucion = _strip_optional_text(form_data.get("evidencia_resolucion"))
        foto_resolucion = form_data.get("foto_resolucion")

        if foto_resolucion is not None and getattr(foto_resolucion, "filename", None):
            (
                foto_resolucion_url,
                foto_resolucion_public_id,
            ) = _upload_incidente_image(
                foto_resolucion,
                folder="incidentes_resolucion",
            )
    else:
        payload = schemas.IncidenteResolver(**(await request.json()))
        evidencia_resolucion = _strip_optional_text(payload.evidencia_resolucion)

    incidente.estado = "resuelto"
    incidente.evidencia_resolucion = evidencia_resolucion
    incidente.foto_resolucion = foto_resolucion_url
    incidente.resuelto_en = utc_now_naive()
    incidente.cerrado_en = None
    incidente.actualizado_en = utc_now_naive()
    evento = registrar_evento_resuelto(
        db,
        incidente=incidente,
        actor=current_user,
        evidencia_resolucion=evidencia_resolucion,
        foto_url=foto_resolucion_url,
        foto_public_id=foto_resolucion_public_id,
        estado_anterior=estado_anterior,
    )
    crear_desde_incidente_evento(
        db,
        incidente=incidente,
        evento=evento,
        actor=current_user,
    )

    db.commit()
    db.refresh(incidente)
    return incidente


@router.post("/{incidente_id}/en-proceso", response_model=schemas.IncidenteResponse)
def marcar_incidente_en_proceso(
    incidente_id: UUID = Path(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    if current_user.rol.lower() not in ["admin", "supervisor", "empleado"]:
        raise HTTPException(status_code=403, detail="No tienes permisos")

    if current_user.rol.lower() == "empleado":
        incidente = obtener_incidente_visible_o_404(db, incidente_id, current_user)
    else:
        incidente = _obtener_incidente_para_accion(db, incidente_id, current_user)

    if incidente.estado == "cerrado":
        raise HTTPException(status_code=400, detail="No se puede marcar en proceso un incidente cerrado")
    if incidente.estado == "resuelto":
        raise HTTPException(status_code=400, detail="No se puede marcar en proceso un incidente resuelto")
    if incidente.estado == "en_proceso":
        raise HTTPException(status_code=400, detail="El incidente ya está en proceso")

    estado_anterior = incidente.estado
    incidente.estado = "en_proceso"
    incidente.actualizado_en = utc_now_naive()
    _sincronizar_estado_y_fechas(incidente)

    registrar_evento_actualizado(
        db,
        incidente=incidente,
        actor=current_user,
        cambios={
            "estado": {
                "anterior": estado_anterior,
                "nuevo": incidente.estado,
            }
        },
        tipo_evento="estado_cambiado",
        mensaje="Estado del incidente actualizado a en proceso",
    )

    db.commit()
    db.refresh(incidente)
    return incidente


@router.post("/{incidente_id}/cerrar", response_model=schemas.IncidenteResponse)
def cerrar_incidente(
    incidente_id: UUID = Path(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    if current_user.rol.lower() not in ["admin", "supervisor"]:
        raise HTTPException(status_code=403, detail="No tienes permisos")
    incidente = _obtener_incidente_para_accion(db, incidente_id, current_user)

    if incidente.estado != "resuelto":
        raise HTTPException(status_code=400, detail="Solo se pueden cerrar incidentes resueltos")

    estado_anterior = incidente.estado
    incidente.estado = "cerrado"
    if incidente.resuelto_en is None:
        incidente.resuelto_en = utc_now_naive()
    incidente.cerrado_en = utc_now_naive()
    incidente.actualizado_en = utc_now_naive()
    evento = registrar_evento_cerrado(
        db,
        incidente=incidente,
        actor=current_user,
        estado_anterior=estado_anterior,
    )
    crear_desde_incidente_evento(
        db,
        incidente=incidente,
        evento=evento,
        actor=current_user,
    )

    db.commit()
    db.refresh(incidente)
    return incidente


@router.post("/{incidente_id}/comentarios", response_model=schemas.IncidenteEventoResponse)
async def comentar_incidente(
    request: Request,
    incidente_id: UUID = Path(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    _validar_permisos_lectura(current_user)
    incidente = obtener_incidente_visible_o_404(db, incidente_id, current_user)

    mensaje = None
    foto = None
    content_type = (request.headers.get("content-type") or "").lower()

    if "multipart/form-data" in content_type:
        form_data = await request.form()
        mensaje = _strip_optional_text(form_data.get("mensaje"))
        foto = form_data.get("foto")
    else:
        payload = schemas.IncidenteComentarioCreate(**(await request.json()))
        mensaje = _strip_optional_text(payload.mensaje)

    if foto is None or not getattr(foto, "filename", None):
        foto = None

    if not mensaje and foto is None:
        raise HTTPException(status_code=400, detail="Debes enviar un mensaje, una foto o ambos")

    foto_url = None
    foto_public_id = None
    if foto is not None:
        foto_url, foto_public_id = _upload_incidente_image(
            foto,
            folder="incidentes_comentarios",
        )

    evento = registrar_evento_comentario(
        db,
        incidente=incidente,
        actor=current_user,
        mensaje=mensaje,
        foto_url=foto_url,
        foto_public_id=foto_public_id,
    )
    crear_desde_incidente_evento(
        db,
        incidente=incidente,
        evento=evento,
        actor=current_user,
    )

    db.commit()
    db.refresh(evento)
    return evento

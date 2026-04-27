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


router = APIRouter(prefix="/incidentes", tags=["Incidentes"])


def _validar_permisos(current_user: Usuario):
    if current_user.rol.lower() not in ["admin", "supervisor"]:
        raise HTTPException(status_code=403, detail="No tienes permisos")


def _obtener_incidente_o_404(db: Session, incidente_id: UUID, company_id: UUID):
    incidente = db.query(models.Incidente).filter(
        models.Incidente.id == incidente_id,
        models.Incidente.company_id == company_id,
    ).first()
    if not incidente:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")
    return incidente


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


def _validar_contexto_relacionado(
    db: Session,
    company_id: UUID,
    empresa_id: Optional[UUID],
    locacion_id: Optional[UUID],
    area_id: Optional[UUID],
    empleado_id: Optional[UUID],
    supervisor_id: Optional[UUID],
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
        if empresa and locacion.empresa_id != empresa.id:
            raise HTTPException(status_code=400, detail="La locación no pertenece a la empresa indicada")

    if area_id is not None:
        area = db.query(models.Area).filter(
            models.Area.id == area_id,
            models.Area.company_id == company_id,
        ).first()
        if not area:
            raise HTTPException(status_code=400, detail="area_id no pertenece a la compañía")
        if locacion and area.locacion_id != locacion.id:
            raise HTTPException(status_code=400, detail="El área no pertenece a la locación indicada")
        if empresa and not locacion:
            locacion_area = db.query(models.Locacion).filter(
                models.Locacion.id == area.locacion_id
            ).first()
            if locacion_area and locacion_area.empresa_id != empresa.id:
                raise HTTPException(status_code=400, detail="El área no pertenece a la empresa indicada")

    empleado = _validar_usuario_company(
        db,
        empleado_id,
        company_id,
        "empleado_id",
        roles_permitidos=["empleado"],
    )
    supervisor = _validar_usuario_company(
        db,
        supervisor_id,
        company_id,
        "supervisor_id",
        roles_permitidos=["supervisor", "admin"],
    )
    _validar_usuario_company(
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
        if supervisor and actividad.supervisor_id and actividad.supervisor_id != supervisor.id:
            raise HTTPException(status_code=400, detail="La actividad no corresponde al supervisor indicado")

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

    return {
        "empresa": empresa,
        "locacion": locacion,
        "area": area,
        "empleado": empleado,
        "supervisor": supervisor,
        "actividad": actividad,
        "feedback": feedback,
    }


def _sincronizar_estado_y_fechas(incidente: models.Incidente):
    if incidente.estado != "resuelto":
        incidente.resuelto_en = None
    if incidente.estado != "cerrado":
        incidente.cerrado_en = None


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
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    _validar_permisos(current_user)

    query = db.query(models.Incidente).filter(
        models.Incidente.company_id == current_user.company_id
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

    return query.order_by(models.Incidente.creado_en.desc()).all()


@router.get("/{incidente_id}", response_model=schemas.IncidenteResponse)
def obtener_incidente(
    incidente_id: UUID = Path(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    _validar_permisos(current_user)
    return _obtener_incidente_o_404(db, incidente_id, current_user.company_id)


@router.post("/", response_model=schemas.IncidenteResponse)
def crear_incidente(
    payload: schemas.IncidenteCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    _validar_permisos(current_user)

    _validar_contexto_relacionado(
        db=db,
        company_id=current_user.company_id,
        empresa_id=payload.empresa_id,
        locacion_id=payload.locacion_id,
        area_id=payload.area_id,
        empleado_id=payload.empleado_id,
        supervisor_id=payload.supervisor_id,
        asignado_a_id=payload.asignado_a_id,
        actividad_usuario_id=payload.actividad_usuario_id,
        feedback_id=payload.feedback_id,
    )

    nuevo_incidente = models.Incidente(
        **payload.dict(exclude_unset=True),
        company_id=current_user.company_id,
        creado_por=current_user.id,
        estado="abierto",
        creado_en=utc_now_naive(),
        actualizado_en=utc_now_naive(),
    )
    db.add(nuevo_incidente)
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
    _validar_permisos(current_user)
    incidente = _obtener_incidente_o_404(db, incidente_id, current_user.company_id)

    update_data = payload.dict(exclude_unset=True)

    empresa_id = update_data.get("empresa_id", incidente.empresa_id)
    locacion_id = update_data.get("locacion_id", incidente.locacion_id)
    area_id = update_data.get("area_id", incidente.area_id)
    empleado_id = update_data.get("empleado_id", incidente.empleado_id)
    supervisor_id = update_data.get("supervisor_id", incidente.supervisor_id)
    asignado_a_id = update_data.get("asignado_a_id", incidente.asignado_a_id)
    actividad_usuario_id = update_data.get("actividad_usuario_id", incidente.actividad_usuario_id)
    feedback_id = update_data.get("feedback_id", incidente.feedback_id)

    _validar_contexto_relacionado(
        db=db,
        company_id=current_user.company_id,
        empresa_id=empresa_id,
        locacion_id=locacion_id,
        area_id=area_id,
        empleado_id=empleado_id,
        supervisor_id=supervisor_id,
        asignado_a_id=asignado_a_id,
        actividad_usuario_id=actividad_usuario_id,
        feedback_id=feedback_id,
    )

    for key, value in update_data.items():
        setattr(incidente, key, value)

    if incidente.estado == "resuelto" and incidente.resuelto_en is None:
        incidente.resuelto_en = utc_now_naive()
    if incidente.estado == "cerrado" and incidente.cerrado_en is None:
        incidente.cerrado_en = utc_now_naive()

    _sincronizar_estado_y_fechas(incidente)
    incidente.actualizado_en = utc_now_naive()

    db.commit()
    db.refresh(incidente)
    return incidente


@router.delete("/{incidente_id}")
def eliminar_incidente(
    incidente_id: UUID = Path(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    _validar_permisos(current_user)
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
    _validar_permisos(current_user)
    incidente = _obtener_incidente_o_404(db, incidente_id, current_user.company_id)

    if incidente.estado == "cerrado":
        raise HTTPException(status_code=400, detail="No se puede resolver un incidente cerrado")

    evidencia_resolucion = None
    foto_resolucion_url = incidente.foto_resolucion
    content_type = (request.headers.get("content-type") or "").lower()

    if "multipart/form-data" in content_type:
        form_data = await request.form()
        evidencia_resolucion = form_data.get("evidencia_resolucion")
        foto_resolucion = form_data.get("foto_resolucion")

        if foto_resolucion is not None and getattr(foto_resolucion, "filename", None):
            imagen_comprimida = compress_image(foto_resolucion.file, quality=70)
            upload_result = cloudinary.uploader.upload(
                imagen_comprimida,
                folder="incidentes_resolucion",
            )
            foto_resolucion_url = upload_result.get("secure_url")
    else:
        payload = schemas.IncidenteResolver(**(await request.json()))
        evidencia_resolucion = payload.evidencia_resolucion

    incidente.estado = "resuelto"
    incidente.evidencia_resolucion = evidencia_resolucion
    incidente.foto_resolucion = foto_resolucion_url
    incidente.resuelto_en = utc_now_naive()
    incidente.cerrado_en = None
    incidente.actualizado_en = utc_now_naive()

    db.commit()
    db.refresh(incidente)
    return incidente


@router.post("/{incidente_id}/cerrar", response_model=schemas.IncidenteResponse)
def cerrar_incidente(
    incidente_id: UUID = Path(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    _validar_permisos(current_user)
    incidente = _obtener_incidente_o_404(db, incidente_id, current_user.company_id)

    if incidente.estado != "resuelto":
        raise HTTPException(status_code=400, detail="Solo se pueden cerrar incidentes resueltos")

    incidente.estado = "cerrado"
    if incidente.resuelto_en is None:
        incidente.resuelto_en = utc_now_naive()
    incidente.cerrado_en = utc_now_naive()
    incidente.actualizado_en = utc_now_naive()

    db.commit()
    db.refresh(incidente)
    return incidente

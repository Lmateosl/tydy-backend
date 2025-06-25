from fastapi import APIRouter, Depends, HTTPException, Security, Query, BackgroundTasks, File, UploadFile, Form
from fastapi_mail import FastMail, MessageSchema, MessageType
from app.config import conf
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime
from fastapi.responses import StreamingResponse
from app.database import get_db
from app.models import ActividadUsuario, Usuario, ListaActividad, Area, Empresa, Locacion
from app.schemas import ActividadUsuarioCreate, ActividadUsuarioResponse, ActividadUsuarioUpdate, ActividadUsuarioResponseExtendido, ActividadFinalizar
from app.auth.dependencies import get_current_user
import io
from typing import List, Optional
from sqlalchemy.orm import joinedload
import pandas as pd
import os
from PIL import Image
from uuid import uuid4

router = APIRouter(prefix="/actividades-usuario", tags=["Actividades por usuario"])
UPLOAD_DIR = "uploads/evidencias"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def comprimir_imagen(imagen_path: str, calidad: int = 75, max_ancho: int = 800):
    try:
        img = Image.open(imagen_path)
        img = img.convert("RGB")
        if img.width > max_ancho:
            proporcion = max_ancho / img.width
            nuevo_alto = int(img.height * proporcion)
            img = img.resize((max_ancho, nuevo_alto))

        img.save(imagen_path, "JPEG", quality=calidad)
    except Exception as e:
        print("Error al comprimir imagen:", e)

@router.post("/", response_model=ActividadUsuarioResponse)
def crear_actividad(
    actividad: ActividadUsuarioCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    
    if current_user.rol not in ["admin", "empleado"]:
        raise HTTPException(status_code=403, detail="No tienes permisos")
    
    nueva = ActividadUsuario(
        **actividad.dict(exclude_unset=True),
        hora_inicio=datetime.utcnow(),
        company_id=current_user.company_id,
        usuario_id=current_user.id
    )
    db.add(nueva)
    db.commit()
    db.refresh(nueva)
    return nueva

@router.get("/exportar")
def exportar_actividades(
    usuario_id: Optional[UUID] = Query(None),
    finalizada: Optional[bool] = Query(None),
    desde: Optional[datetime] = Query(None),
    hasta: Optional[datetime] = Query(None),
    formato: str = Query("excel"),
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    query = db.query(ActividadUsuario).filter(
        ActividadUsuario.company_id == current_user.company_id
    ).options(
        joinedload(ActividadUsuario.usuario)
            .joinedload(Usuario.area)
            .joinedload(Area.locacion)
            .joinedload(Locacion.empresa),
        joinedload(ActividadUsuario.lista).joinedload(ListaActividad.actividades)
    )

    if usuario_id:
        query = query.filter(ActividadUsuario.usuario_id == usuario_id)
    if finalizada is not None:
        query = query.filter(ActividadUsuario.finalizada == finalizada)
    if desde:
        query = query.filter(ActividadUsuario.hora_inicio >= desde)
    if hasta:
        query = query.filter(ActividadUsuario.hora_inicio <= hasta)

    actividades = query.order_by(ActividadUsuario.hora_inicio.desc()).all()

    data = []
    for act in actividades:
        area = act.usuario.area if act.usuario and act.usuario.area else None
        locacion = area.locacion if area and area.locacion else None
        empresa = locacion.empresa if locacion and locacion.empresa else None

        data.append({
            "ID Actividad": str(act.id),
            "Usuario": act.usuario.nombre if act.usuario else None,
            "Identificación": act.usuario.identificacion if act.usuario else None,
            "Área": area.nombre if area else None,
            "Locación": locacion.nombre if locacion else None,
            "Empresa": empresa.nombre if empresa else None,
            "Hora Inicio": act.hora_inicio,
            "Hora Fin": act.hora_fin,
            "Finalizada": act.finalizada,
            "Comentario": act.comentario,
            "Lista Actividad": act.lista.nombre if act.lista else None,
            "Actividades en Lista": ", ".join([a.nombre for a in act.lista.actividades]) if act.lista else None
        })

    df = pd.DataFrame(data)

    if formato == "csv":
        stream = io.StringIO()
        df.to_csv(stream, index=False)
        stream.seek(0)
        return StreamingResponse(
            iter([stream.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=actividades.csv"}
        )
    else:
        stream = io.BytesIO()
        with pd.ExcelWriter(stream, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name="Actividades")
        stream.seek(0)
        return StreamingResponse(
            stream,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=actividades.xlsx"}
        )

@router.get("/{actividad_id}", response_model=ActividadUsuarioResponse)
def obtener_actividad(
    actividad_id: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    actividad = db.query(ActividadUsuario).filter(
        ActividadUsuario.id == actividad_id,
        ActividadUsuario.company_id == current_user.company_id
    ).first()

    if not actividad:
        raise HTTPException(status_code=404, detail="Actividad no encontrada")
    
    return actividad

@router.put("/{actividad_id}", response_model=ActividadUsuarioResponse)
def actualizar_actividad(
    actividad_id: UUID,
    actualizacion: ActividadUsuarioUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    actividad = db.query(ActividadUsuario).filter(
        ActividadUsuario.id == actividad_id,
        ActividadUsuario.company_id == current_user.company_id
    ).first()

    if current_user.rol not in ["admin", "empleado"]:
        raise HTTPException(status_code=403, detail="No tienes permisos")

    if not actividad:
        raise HTTPException(status_code=404, detail="Actividad no encontrada")

    for key, value in actualizacion.dict(exclude_unset=True).items():
        setattr(actividad, key, value)

    db.commit()
    db.refresh(actividad)
    return actividad


@router.put("/{actividad_id}/finalizar", response_model=ActividadUsuarioResponse)
def finalizar_actividad(
    actividad_id: UUID,
    background_tasks: BackgroundTasks,
    comentario: Optional[str] = Form(None),
    imagen: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    actividad = db.query(ActividadUsuario).filter(
        ActividadUsuario.id == actividad_id,
        ActividadUsuario.company_id == current_user.company_id
    ).first()

    if not actividad:
        raise HTTPException(status_code=404, detail="Actividad no encontrada")

    if actividad.finalizada:
        raise HTTPException(status_code=400, detail="Ya está finalizada")

    ruta_imagen = None
    if imagen:
        if imagen.content_type not in ["image/jpeg", "image/png"]:
            raise HTTPException(status_code=400, detail="Formato de imagen no válido")

        import cloudinary.uploader
        try:
            upload_result = cloudinary.uploader.upload(imagen.file, folder="finalizadas")
            ruta_imagen = upload_result.get("secure_url")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error al subir imagen: {e}")

    actividad.finalizada = True
    actividad.comentario = comentario or None
    actividad.hora_fin = datetime.utcnow()
    if ruta_imagen:
        actividad.imagen = ruta_imagen
    db.commit()
    db.refresh(actividad)

    if actividad.comentario:
        message = MessageSchema(
            subject="Alerta al finalizar actividad",
            recipients=["mateosan67@gmail.com"],
            body=f"El usuario {current_user.nombre} con número de identificación: {current_user.identificacion} finalizó una actividad y dejó un comentario:\n\n{actividad.comentario}.\n\n Entra en la plataforma para mis información",
            subtype=MessageType.plain
        )
        fm = FastMail(conf)
        background_tasks.add_task(fm.send_message, message)
    return actividad

@router.get("/", response_model=List[ActividadUsuarioResponseExtendido])
def listar_actividades(
    usuario_id: Optional[UUID] = Query(None),
    finalizada: Optional[bool] = Query(None),
    desde: Optional[datetime] = Query(None),
    hasta: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    query = db.query(ActividadUsuario).filter(
        ActividadUsuario.company_id == current_user.company_id
    ).options(
        joinedload(ActividadUsuario.usuario),
        joinedload(ActividadUsuario.lista).joinedload(ListaActividad.actividades),
        joinedload(ActividadUsuario.usuario)
            .joinedload(Usuario.area)
            .joinedload(Area.locacion)
            .joinedload(Locacion.empresa),
        joinedload(ActividadUsuario.lista)
            .joinedload(ListaActividad.actividades)
    )

    if usuario_id:
        query = query.filter(ActividadUsuario.usuario_id == usuario_id)
    if finalizada is not None:
        query = query.filter(ActividadUsuario.finalizada == finalizada)
    if desde:
        query = query.filter(ActividadUsuario.hora_inicio >= desde)
    if hasta:
        query = query.filter(ActividadUsuario.hora_inicio <= hasta)

    resultados = query.order_by(ActividadUsuario.hora_inicio.desc()).all()
    return resultados

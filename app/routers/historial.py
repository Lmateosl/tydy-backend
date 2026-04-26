from fastapi import APIRouter, Depends, HTTPException, Security, Query, BackgroundTasks, File, UploadFile, Form
from fastapi_mail import FastMail, MessageSchema, MessageType
from app.config import conf
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime
from fastapi.responses import StreamingResponse
from app.database import get_db
from app.models import ActividadUsuario, Usuario, ListaActividad, Area, Empresa, Locacion, Company
from app.schemas import ActividadUsuarioCreate, ActividadUsuarioResponse, ActividadUsuarioUpdate, ActividadUsuarioResponseExtendido, ActividadFinalizar
from app.auth.dependencies import get_current_user
from app.services.incidentes_automaticos import crear_incidentes_automaticos_por_finalizacion
import io
from typing import List, Optional
from sqlalchemy.orm import joinedload
from sqlalchemy import func
import pandas as pd
import os
from PIL import Image
from uuid import uuid4
import math
from pydantic import EmailStr, TypeAdapter, ValidationError

router = APIRouter(prefix="/actividades-usuario", tags=["Actividades por usuario"])
UPLOAD_DIR = "uploads/evidencias"
os.makedirs(UPLOAD_DIR, exist_ok=True)
email_adapter = TypeAdapter(EmailStr)

def calcular_distancia_metros(lat1, lon1, lat2, lon2):
    if None in [lat1, lon1, lat2, lon2]:
        return None

    lat1 = float(lat1)
    lon1 = float(lon1)
    lat2 = float(lat2)
    lon2 = float(lon2)
    radio_tierra = 6371e3
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) * math.sin(d_lat / 2)
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2)
        * math.sin(d_lon / 2)
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(radio_tierra * c, 2)

def resolver_estado_verificacion(actividad: ActividadUsuario, locacion: Optional[Locacion]):
    radio_verificacion = float(locacion.radio_verificacion_metros) if locacion and locacion.radio_verificacion_metros else 1000.0
    umbral_precision_baja = 100.0

    tiene_inicio = actividad.latitud_inicio is not None and actividad.longitud_inicio is not None
    tiene_cierre = actividad.latitud_fin is not None and actividad.longitud_fin is not None
    tiene_metodos = bool(actividad.metodo_inicio) and bool(actividad.metodo_fin)

    if not (tiene_inicio and tiene_cierre and tiene_metodos):
        return "requiere_revision"

    distancia_inicio = actividad.distancia_validacion
    distancia_fin = actividad.distancia_fin
    if distancia_inicio is None or distancia_fin is None:
        return "requiere_revision"

    # Fuera del radio se permite operativamente, pero queda marcado para revisión.
    if distancia_inicio > radio_verificacion or distancia_fin > radio_verificacion:
        return "requiere_revision"

    precision_inicio = float(actividad.precision_inicio) if actividad.precision_inicio is not None else None
    precision_fin = float(actividad.precision_fin) if actividad.precision_fin is not None else None
    if (
        (precision_inicio is not None and precision_inicio > umbral_precision_baja)
        or (precision_fin is not None and precision_fin > umbral_precision_baja)
    ):
        return "verificada_con_baja_precision"

    return "verificada"

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
        usuario_id=current_user.id,
        supervisor_id=current_user.supervisor_id,
        estado_verificacion="iniciada"
    )
    db.add(nueva)
    db.commit()
    db.refresh(nueva)
    return nueva

@router.get("/exportar")
def exportar_actividades(
    usuario_id: Optional[UUID] = Query(None),
    finalizada: Optional[bool] = Query(None),
    empresa: Optional[str] = Query(None),
    estado_verificacion: Optional[str] = Query(None),
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
    if empresa:
        query = (
            query.join(ActividadUsuario.usuario)
            .join(Usuario.area)
            .join(Area.locacion)
            .join(Locacion.empresa)
            .filter(func.lower(Empresa.nombre) == empresa.strip().lower())
        )
    if estado_verificacion:
        query = query.filter(
            func.lower(ActividadUsuario.estado_verificacion) == estado_verificacion.strip().lower()
        )
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
    latitud_fin: Optional[float] = Form(None),
    longitud_fin: Optional[float] = Form(None),
    precision_fin: Optional[float] = Form(None),
    distancia_fin: Optional[float] = Form(None),
    metodo_fin: Optional[str] = Form(None),
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
    evidencia_obligatoria = bool(actividad.lista.imagen) if actividad.lista else False
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
    actividad.latitud_fin = latitud_fin
    actividad.longitud_fin = longitud_fin
    actividad.precision_fin = precision_fin
    locacion = actividad.usuario.area.locacion if actividad.usuario and actividad.usuario.area and actividad.usuario.area.locacion else None
    distancia_fin_calculada = calcular_distancia_metros(
        latitud_fin,
        longitud_fin,
        locacion.latitud if locacion else None,
        locacion.longitud if locacion else None,
    )
    actividad.distancia_fin = distancia_fin_calculada if distancia_fin_calculada is not None else distancia_fin
    actividad.metodo_fin = metodo_fin
    actividad.duracion_segundos = int((actividad.hora_fin - actividad.hora_inicio).total_seconds())
    actividad.evidencia_obligatoria = evidencia_obligatoria
    actividad.evidencia_entregada = bool(ruta_imagen)
    actividad.evidencia_subida_en = datetime.utcnow() if ruta_imagen else None
    actividad.evidencia_usuario_id = current_user.id if ruta_imagen else None
    actividad.evidencia_tipo = imagen.content_type if imagen else None
    actividad.evidencia_nombre_archivo = imagen.filename if imagen else None
    actividad.estado_verificacion = resolver_estado_verificacion(actividad, locacion)
    if ruta_imagen:
        actividad.imagen = ruta_imagen
    db.commit()
    db.refresh(actividad)
    crear_incidentes_automaticos_por_finalizacion(
        db,
        actividad,
        company_id_fallback=current_user.company_id,
    )

    if actividad.comentario:
        company = db.query(Company).filter(Company.id == current_user.company_id).first()
        if company and company.email:
            try:
                email_adapter.validate_python(company.email)
                message = MessageSchema(
                    subject="Alerta al finalizar actividad",
                    recipients=[company.email],
                    body=f"El usuario {current_user.nombre} con número de identificación: {current_user.identificacion} finalizó una actividad y dejó un comentario:\n\n{actividad.comentario}.\n\nEntra en la plataforma para más información.",
                    subtype=MessageType.plain
                )
                fm = FastMail(conf)
                background_tasks.add_task(fm.send_message, message)
            except ValidationError:
                print(f"Email de compañía inválido. No se envió alerta: {company.email}")
            except Exception as e:
                print(f"Error preparando alerta de finalización: {e}")
        else:
            print("No se envió alerta: la compañía no existe o no tiene email configurado")
    return actividad

@router.get("/", response_model=List[ActividadUsuarioResponseExtendido])
def listar_actividades(
    usuario_id: Optional[UUID] = Query(None),
    finalizada: Optional[bool] = Query(None),
    empresa: Optional[str] = Query(None),
    estado_verificacion: Optional[str] = Query(None),
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
    if empresa:
        query = (
            query.join(ActividadUsuario.usuario)
            .join(Usuario.area)
            .join(Area.locacion)
            .join(Locacion.empresa)
            .filter(func.lower(Empresa.nombre) == empresa.strip().lower())
        )
    if estado_verificacion:
        query = query.filter(
            func.lower(ActividadUsuario.estado_verificacion) == estado_verificacion.strip().lower()
        )
    if desde:
        query = query.filter(ActividadUsuario.hora_inicio >= desde)
    if hasta:
        query = query.filter(ActividadUsuario.hora_inicio <= hasta)

    resultados = query.order_by(ActividadUsuario.hora_inicio.desc()).all()
    return resultados

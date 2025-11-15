from fastapi import APIRouter, Depends, HTTPException, Security, Path, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import or_
from uuid import UUID
from ..database import get_db
from .. import models, schemas
from ..auth.dependencies import get_current_user
from ..models import Usuario
import qrcode
import base64
from io import BytesIO
import random
import string
import cloudinary.uploader
from urllib.parse import urlencode
from PIL import Image

# Función auxiliar para generar código de 6 dígitos
def generar_codigo():
    return ''.join(random.choices(string.digits, k=6))


# Función auxiliar para generar QR y subirlo a Cloudinary
def generar_qr_cloudinary(data: dict) -> str:
    qr = qrcode.make(data)
    buffer = BytesIO()
    qr.save(buffer, format="PNG")
    buffer.seek(0)
    result = cloudinary.uploader.upload(buffer, folder="listas_actividades")
    return result["secure_url"]

# Función auxiliar específica para Feedback QR
def generar_qr_cloudinary_feedback(data: str) -> str:
    qr = qrcode.make(data)  # 'data' debe ser una URL string para que el QR sea clickeable
    buffer = BytesIO()
    qr.save(buffer, format="PNG")
    buffer.seek(0)
    result = cloudinary.uploader.upload(buffer, folder="feedback_qr")
    return result["secure_url"]

def comprimir_imagen(file, quality: int = 70):
    """
    Comprime una imagen antes de subirla a Cloudinary.
    quality: 1-95 (70 recomendado)
    Retorna un buffer listo para subir.
    """
    img = Image.open(file)
    img = img.convert("RGB")
    buffer = BytesIO()
    img.save(buffer, format="JPEG", optimize=True, quality=quality)
    buffer.seek(0)
    return buffer

router = APIRouter(prefix="/listas_actividades", tags=["Listas de Actividades"])

# Crear lista
@router.post("/", response_model=schemas.ListaActividadResponse)
def crear_lista(
    lista: schemas.ListaActividadCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    if current_user.rol.lower() not in ["admin", "supervisor"]:
        raise HTTPException(status_code=403, detail="No tienes permisos para crear listas")

    actividades = []
    if lista.actividad_ids:
        actividades = db.query(models.Actividad).filter(
            models.Actividad.id.in_(lista.actividad_ids),
            models.Actividad.company_id == current_user.company_id
        ).all()
        if len(actividades) != len(lista.actividad_ids):
            raise HTTPException(status_code=404, detail="Alguna actividad no encontrada")

    nueva_lista = models.ListaActividad(
        nombre=lista.nombre,
        usuario_id=current_user.id,
        actividades=actividades,
        company_id=current_user.company_id
    )

    db.add(nueva_lista)
    db.commit()
    db.refresh(nueva_lista)

    # Agregar códigos y QRs si se requieren
    if lista.code:
        # Validar unicidad de code en la empresa
        while True:
            nuevo_codigo = generar_codigo()
            existe = db.query(models.ListaActividad).filter(
                models.ListaActividad.company_id == current_user.company_id,
                models.ListaActividad.code == nuevo_codigo
            ).first()
            if not existe:
                nueva_lista.code = nuevo_codigo
                break
    if lista.codeout:
        # Validar unicidad de codeout en la empresa
        while True:
            nuevo_codigoout = generar_codigo()
            existe = db.query(models.ListaActividad).filter(
                models.ListaActividad.company_id == current_user.company_id,
                models.ListaActividad.codeout == nuevo_codigoout
            ).first()
            if not existe:
                nueva_lista.codeout = nuevo_codigoout
                break
    if lista.qrin:
        qr_data_in = {"lista_id": str(nueva_lista.id), "finalizada": False}
        nueva_lista.qrin = generar_qr_cloudinary(qr_data_in)
    if lista.qrout:
        qr_data_out = {"lista_id": str(nueva_lista.id), "finalizada": True}
        nueva_lista.qrout = generar_qr_cloudinary(qr_data_out)

    if lista.imagen:
        nueva_lista.imagen = True
    else:
        nueva_lista.imagen = False

    db.commit()
    db.refresh(nueva_lista)

    return nueva_lista

# Listar listas del usuario
@router.get("/", response_model=list[schemas.ListaActividadResponse])
def listar_listas(
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    listas = db.query(models.ListaActividad).filter(
        models.ListaActividad.company_id == current_user.company_id
    ).all()
    return listas

# Obtener lista por código
@router.get("/por_codigo/{code}", response_model=schemas.ListaActividadResponse)
def obtener_por_codigo(
    code: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    lista = db.query(models.ListaActividad).filter(
        models.ListaActividad.code == code,
        models.ListaActividad.company_id == current_user.company_id
    ).first()
    if not lista:
        raise HTTPException(status_code=404, detail="Lista no encontrada")
    return lista

# Obtener lista por código out
@router.get("/por_codigoout/{codeout}", response_model=schemas.ListaActividadResponse)
def obtener_por_codigoout(
    codeout: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    lista = db.query(models.ListaActividad).filter(
        models.ListaActividad.codeout == codeout,
        models.ListaActividad.company_id == current_user.company_id
    ).first()
    if not lista:
        raise HTTPException(status_code=404, detail="Lista no encontrada")
    return lista

# -----------------------------
# Crear lista de feedback (QR)
# -----------------------------
@router.post("/feedback/list")
def crear_feedback_list(
    payload: schemas.FeedbackQRCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    """
    Crea un QR con nombre y direccion codificados, sube la imagen a Cloudinary,
    almacena el registro en la tabla feedback_qr y devuelve confirmación.
    """
    # 1) Construir la URL base con segmentos de ruta codificados
    from urllib.parse import quote

    base_url = "https://tydy.pro/feedback/"
    nombre_encoded = quote(payload.nombre or "", safe="")
    direccion_encoded = quote(payload.direccion or "", safe="")
    full_url = f"{base_url}{nombre_encoded}/{direccion_encoded}"

    # 2) Generar QR y subirlo a Cloudinary (carpeta dedicada)
    qr_url = generar_qr_cloudinary_feedback(full_url)

    # 3) Guardar registro mínimo en DB (solo id, url y referencias)
    dir_value = payload.direccion or ""
    feedback = models.FeedbackQR(
        url=qr_url,
        nombre=payload.nombre,
        direccion=dir_value,
        company_id=current_user.company_id,
        usuario_id=current_user.id,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    # 4) Devolver confirmación amigable
    return {
        "detail": "OK: la imagen ha sido generada",
        "id": str(feedback.id),
        "url": feedback.url,
        "nombre": feedback.nombre,
        "direccion": feedback.direccion
    }

@router.get("/feedback", response_model=list[schemas.FeedbackQRResponse])
def listar_feedback_qr(
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    """
    Lista todos los FeedbackQR de la empresa del usuario actual.
    """
    feedbacks = db.query(models.FeedbackQR).filter(
        models.FeedbackQR.company_id == current_user.company_id
    ).all()
    return feedbacks

@router.put("/feedback/{feedback_id}", response_model=schemas.FeedbackQRResponse)
def actualizar_feedback_qr(
    feedback_id: UUID,
    payload: schemas.FeedbackQRUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    """
    Actualiza nombre y/o direccion de un FeedbackQR y regenera el QR con la nueva URL.
    """
    feedback = db.query(models.FeedbackQR).filter(
        models.FeedbackQR.id == feedback_id,
        models.FeedbackQR.company_id == current_user.company_id,
    ).first()
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback QR no encontrado")

    # Usar valores nuevos si vienen en el payload, sino mantener los actuales
    nuevo_nombre = payload.nombre if payload.nombre is not None else feedback.nombre
    nueva_direccion = payload.direccion if payload.direccion is not None else feedback.direccion

    # Reconstruir la URL con los nuevos valores
    from urllib.parse import quote
    base_url = "https://tydy.pro/feedback/"
    nombre_encoded = quote(nuevo_nombre or "", safe="")
    direccion_encoded = quote(nueva_direccion or "", safe="")
    full_url = f"{base_url}{nombre_encoded}/{direccion_encoded}"

    # Regenerar QR en Cloudinary
    qr_url = generar_qr_cloudinary_feedback(full_url)

    # Actualizar registro
    feedback.nombre = nuevo_nombre
    feedback.direccion = nueva_direccion
    feedback.url = qr_url

    db.commit()
    db.refresh(feedback)

    return feedback

@router.delete("/feedback/{feedback_id}")
def eliminar_feedback_qr(
    feedback_id: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    """
    Elimina un FeedbackQR de la empresa del usuario actual.
    (No elimina la imagen de Cloudinary).
    """
    feedback = db.query(models.FeedbackQR).filter(
        models.FeedbackQR.id == feedback_id,
        models.FeedbackQR.company_id == current_user.company_id,
    ).first()
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback QR no encontrado")

    db.delete(feedback)
    db.commit()

    return {"detail": "Feedback QR eliminado correctamente"}

# -----------------------------
# Crear feedback de usuario (con foto opcional)
# -----------------------------
@router.post("/feedback-user", response_model=schemas.FeedbackResponse)
async def crear_feedback_user(
    empresa: str = Form(...),
    direccion: str = Form(...),
    calificacion: float = Form(...),
    nombre: str | None = Form(None),
    comentario: str | None = Form(None),
    foto: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    """
    Crea un registro de feedback de un usuario.
    La foto es opcional; si se envía, se sube a Cloudinary y se guarda la URL.
    Los datos se reciben como form-data (para soportar archivo de imagen).
    """
    foto_url = None
    if foto is not None:
        # Subir imagen a Cloudinary en carpeta dedicada
        imagen_comprimida = comprimir_imagen(foto.file, quality=70)
        result = cloudinary.uploader.upload(imagen_comprimida, folder="feedback_fotos")
        foto_url = result.get("secure_url")

    nuevo_feedback = models.Feedback(
        nombre=nombre,
        empresa=empresa,
        direccion=direccion,
        calificacion=calificacion,
        comentario=comentario,
        foto=foto_url,
        company_id=current_user.company_id,
        usuario_id=current_user.id,
    )

    db.add(nuevo_feedback)
    db.commit()
    db.refresh(nuevo_feedback)

    return nuevo_feedback


# -----------------------------
# Nuevos endpoints de feedback de usuario
# -----------------------------

@router.get("/feedback-user", response_model=list[schemas.FeedbackResponse])
def listar_feedback_user(
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    """
    Lista todos los feedback de la empresa del usuario actual.
    """
    feedbacks = db.query(models.Feedback).filter(
        models.Feedback.company_id == current_user.company_id
    ).order_by(models.Feedback.creado_en.desc()).all()
    return feedbacks


@router.put("/feedback-user/{feedback_id}", response_model=schemas.FeedbackResponse)
async def actualizar_feedback_user(
    feedback_id: UUID,
    empresa: str | None = Form(None),
    direccion: str | None = Form(None),
    calificacion: float | None = Form(None),
    nombre: str | None = Form(None),
    comentario: str | None = Form(None),
    foto: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    """
    Actualiza un registro de feedback.
    Todos los campos son opcionales; si se envía una nueva foto, se comprime y se reemplaza.
    """
    feedback = db.query(models.Feedback).filter(
        models.Feedback.id == feedback_id,
        models.Feedback.company_id == current_user.company_id,
    ).first()
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback no encontrado")

    # Actualizar campos si se enviaron
    if empresa is not None:
        feedback.empresa = empresa
    if direccion is not None:
        feedback.direccion = direccion
    if calificacion is not None:
        feedback.calificacion = calificacion
    if nombre is not None:
        feedback.nombre = nombre
    if comentario is not None:
        feedback.comentario = comentario

    # Procesar nueva foto si se envía
    if foto is not None:
        imagen_comprimida = comprimir_imagen(foto.file, quality=70)
        result = cloudinary.uploader.upload(imagen_comprimida, folder="feedback_fotos")
        feedback.foto = result.get("secure_url")

    db.commit()
    db.refresh(feedback)

    return feedback


@router.delete("/feedback-user/{feedback_id}")
def eliminar_feedback_user(
    feedback_id: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    """
    Elimina un registro de feedback de la empresa del usuario actual.
    (No elimina la imagen de Cloudinary).
    """
    feedback = db.query(models.Feedback).filter(
        models.Feedback.id == feedback_id,
        models.Feedback.company_id == current_user.company_id,
    ).first()
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback no encontrado")

    db.delete(feedback)
    db.commit()

    return {"detail": "Feedback eliminado correctamente"}

# Obtener lista específica
@router.get("/{lista_id}", response_model=schemas.ListaActividadResponse)
def obtener_lista(
    lista_id: UUID = Path(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    lista = db.query(models.ListaActividad).filter(
        models.ListaActividad.id == lista_id,
        models.ListaActividad.company_id == current_user.company_id
    ).first()
    if not lista:
        raise HTTPException(status_code=404, detail="Lista no encontrada")
    return lista

@router.put("/{lista_id}", response_model=schemas.ListaActividadResponse)
def actualizar_lista(
    lista_update: schemas.ListaActividadUpdate,
    lista_id: UUID = Path(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    lista = db.query(models.ListaActividad).filter(
        models.ListaActividad.id == lista_id,
        models.ListaActividad.company_id == current_user.company_id
    ).first()

    if not lista:
        raise HTTPException(status_code=404, detail="Lista no encontrada")

    if current_user.rol.lower() not in ["admin", "supervisor"]:
        raise HTTPException(status_code=403, detail="No tienes permisos")

    update_data = lista_update.dict(exclude_unset=True)

    # Actualizar actividades
    if "actividad_ids" in update_data:
        actividades = db.query(models.Actividad).filter(
            models.Actividad.id.in_(update_data["actividad_ids"]),
            models.Actividad.company_id == current_user.company_id
        ).all()
        if len(actividades) != len(update_data["actividad_ids"]):
            raise HTTPException(status_code=404, detail="Alguna actividad no encontrada")
        lista.actividades = actividades

    # Actualizar nombre
    if "nombre" in update_data:
        lista.nombre = update_data["nombre"]

    # Generar código si se solicita
    if update_data.get("code") is True:
        # Validar unicidad de code en la empresa
        while True:
            nuevo_codigo = generar_codigo()
            existe = db.query(models.ListaActividad).filter(
                models.ListaActividad.company_id == current_user.company_id,
                models.ListaActividad.code == nuevo_codigo,
                models.ListaActividad.id != lista.id
            ).first()
            if not existe:
                lista.code = nuevo_codigo
                break

    if update_data.get("codeout") is True:
        # Validar unicidad de codeout en la empresa
        while True:
            nuevo_codigoout = generar_codigo()
            existe = db.query(models.ListaActividad).filter(
                models.ListaActividad.company_id == current_user.company_id,
                models.ListaActividad.codeout == nuevo_codigoout,
                models.ListaActividad.id != lista.id
            ).first()
            if not existe:
                lista.codeout = nuevo_codigoout
                break

    # Generar QR In
    if update_data.get("qrin") is True:
        qr_data_in = {"lista_id": str(lista.id), "finalizada": False}
        lista.qrin = generar_qr_cloudinary(qr_data_in)

    # Generar QR Out
    if update_data.get("qrout") is True:
        qr_data_out = {"lista_id": str(lista.id), "finalizada": True}
        lista.qrout = generar_qr_cloudinary(qr_data_out)

    if lista.imagen:
        lista.imagen = True
    else:
        lista.imagen = False

    db.commit()
    db.refresh(lista)
    return lista

# Eliminar lista
@router.delete("/{lista_id}")
def eliminar_lista(
    lista_id: UUID = Path(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    lista = db.query(models.ListaActividad).filter(
        models.ListaActividad.id == lista_id,
    ).first()
    if not lista:
        raise HTTPException(status_code=404, detail="Lista no encontrada")
    
    if current_user.rol.lower() not in ["admin", "supervisor"]:
        raise HTTPException(status_code=403, detail="No tienes permisos")

    db.delete(lista)
    db.commit()
    return {"detalle": "Lista eliminada correctamente"}

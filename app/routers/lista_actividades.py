from fastapi import APIRouter, Depends, HTTPException, Security, Path
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

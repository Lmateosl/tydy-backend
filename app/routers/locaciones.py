from fastapi import APIRouter, HTTPException, Depends, Security
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Locacion
from app.schemas import LocacionCreate, LocacionUpdate, LocacionOut
from ..auth.dependencies import get_current_user
from ..models import Usuario
from uuid import UUID
from typing import List

router = APIRouter(prefix="/locaciones", tags=["Locaciones"])

# ✅ Crear locación asignando el usuario autenticado como creador
@router.post("/", response_model=LocacionOut)
def crear_locacion(
    data: LocacionCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    if current_user.rol != "admin":
        raise HTTPException(status_code=403, detail="No tienes permisos")
    
    if data.latitud is not None and not (-90 <= data.latitud <= 90):
        raise HTTPException(status_code=400, detail="La latitud debe estar entre -90 y 90")

    if data.longitud is not None and not (-180 <= data.longitud <= 180):
        raise HTTPException(status_code=400, detail="La longitud debe estar entre -180 y 180")
    
    locacion = Locacion(**data.dict(), usuario_id=current_user.id, company_id=current_user.company_id)
    db.add(locacion)
    db.commit()
    db.refresh(locacion)
    return locacion

# ✅ Obtener todas las locaciones creadas por el usuario autenticado
@router.get("/", response_model=List[LocacionOut])
def obtener_locaciones(
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user)
):
    return db.query(Locacion).filter(
        Locacion.usuario_id == current_user.id,
        Locacion.company_id == current_user.company_id
    ).all()

# ✅ Obtener locación específica solo si fue creada por el usuario autenticado
@router.get("/{locacion_id}", response_model=LocacionOut)
def obtener_locacion(
    locacion_id: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user)
):
    locacion = db.query(Locacion).filter(
        Locacion.id == locacion_id,
        Locacion.company_id == current_user.company_id
    ).first()
    if not locacion:
        raise HTTPException(status_code=404, detail="Locación no encontrada o sin permiso")
    return locacion

# ✅ Actualizar locación solo si fue creada por el usuario autenticado
@router.put("/{locacion_id}", response_model=LocacionOut)
def actualizar_locacion(
    locacion_id: UUID,
    data: LocacionUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user)
):
    if current_user.rol != "admin":
        raise HTTPException(status_code=403, detail="No tienes permisos")
    
    if data.latitud is not None and not (-90 <= data.latitud <= 90):
        raise HTTPException(status_code=400, detail="La latitud debe estar entre -90 y 90")

    if data.longitud is not None and not (-180 <= data.longitud <= 180):
        raise HTTPException(status_code=400, detail="La longitud debe estar entre -180 y 180")
    
    locacion = db.query(Locacion).filter(
        Locacion.id == locacion_id,
        Locacion.company_id == current_user.company_id
    ).first()
    if not locacion:
        raise HTTPException(status_code=404, detail="Locación no encontrada o sin permiso")
    for key, value in data.dict(exclude_unset=True).items():
        setattr(locacion, key, value)
    db.commit()
    db.refresh(locacion)
    return locacion

# ✅ Eliminar locación solo si fue creada por el usuario autenticado
@router.delete("/{locacion_id}")
def eliminar_locacion(
    locacion_id: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user)
):
    if current_user.rol != "admin":
        raise HTTPException(status_code=403, detail="No tienes permisos")
    
    locacion = db.query(Locacion).filter(
        Locacion.id == locacion_id,
        Locacion.company_id == current_user.company_id
    ).first()
    if not locacion:
        raise HTTPException(status_code=404, detail="Locación no encontrada o sin permiso")
    db.delete(locacion)
    db.commit()
    return {"mensaje": "Locación eliminada"}

# ✅ Obtener locaciones de una empresa, filtradas por el usuario autenticado
@router.get("/empresa/{empresa_id}", response_model=List[LocacionOut])
def obtener_locaciones_por_empresa(
    empresa_id: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user)
):
    return db.query(Locacion).filter(
        Locacion.empresa_id == empresa_id,
        Locacion.company_id == current_user.company_id
    ).all()
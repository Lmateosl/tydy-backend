import httpx
import os
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

LOCATIONIQ_API_KEY = os.getenv("LOCATIONIQ_API_KEY")  # Debes tener esta variable en tu entorno
LOCATIONIQ_REFERER = os.getenv("LOCATIONIQ_REFERER", "http://localhost:5173")

def locationiq_headers():
    return {
        "User-Agent": "qr-app/1.0",
        "Referer": LOCATIONIQ_REFERER,
    }

async def obtener_coordenadas(direccion: str):
    url = "https://us1.locationiq.com/v1/search.php"
    params = {
        "key": LOCATIONIQ_API_KEY,
        "q": direccion,
        "format": "json",
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params, headers=locationiq_headers())
        if response.status_code == 403:
            raise HTTPException(status_code=502, detail="LocationIQ rechazó el token o el referrer configurado")
        response.raise_for_status()
        data = response.json()
        if not data:
            return []
        return [
            {
                "display_name": item.get("display_name"),
                "latitud": float(item.get("lat")),
                "longitud": float(item.get("lon"))
            }
            for item in data
        ]

async def obtener_direccion_por_coordenadas(latitud: float, longitud: float):
    url = "https://us1.locationiq.com/v1/reverse"
    params = {
        "key": LOCATIONIQ_API_KEY,
        "lat": latitud,
        "lon": longitud,
        "format": "json",
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params, headers=locationiq_headers())
        if response.status_code == 403:
            raise HTTPException(status_code=502, detail="LocationIQ rechazó el token o el referrer configurado")
        response.raise_for_status()
        data = response.json()
        return {
            "display_name": data.get("display_name"),
            "latitud": float(data.get("lat", latitud)),
            "longitud": float(data.get("lon", longitud))
        }

@router.get("/coordenadas/")
async def buscar_coordenadas(direccion: str):
    """
    Devuelve un array de posibles coincidencias de dirección usando LocationIQ.
    """
    if not direccion:
        raise HTTPException(status_code=400, detail="Debes proporcionar una dirección")
    
    resultados = await obtener_coordenadas(direccion)
    if not resultados:
        raise HTTPException(status_code=404, detail="No se encontraron resultados para la dirección")

    return resultados

@router.get("/reverse/")
async def buscar_direccion_por_coordenadas(latitud: float, longitud: float):
    """
    Devuelve una dirección legible usando coordenadas seleccionadas en el mapa.
    """
    if not (-90 <= latitud <= 90):
        raise HTTPException(status_code=400, detail="La latitud debe estar entre -90 y 90")

    if not (-180 <= longitud <= 180):
        raise HTTPException(status_code=400, detail="La longitud debe estar entre -180 y 180")

    resultado = await obtener_direccion_por_coordenadas(latitud, longitud)
    if not resultado.get("display_name"):
        raise HTTPException(status_code=404, detail="No se encontró una dirección para estas coordenadas")

    return resultado

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

    if data.radio_verificacion_metros is not None and data.radio_verificacion_metros <= 0:
        raise HTTPException(status_code=400, detail="El radio de verificación debe ser mayor a 0")
    
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

    if data.radio_verificacion_metros is not None and data.radio_verificacion_metros <= 0:
        raise HTTPException(status_code=400, detail="El radio de verificación debe ser mayor a 0")
    
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

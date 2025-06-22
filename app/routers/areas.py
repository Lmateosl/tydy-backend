from fastapi import APIRouter, Depends, HTTPException, status, Security
from sqlalchemy.orm import Session
from uuid import UUID
from app.database import get_db
from app.schemas import AreaCreate, AreaOut, UsuarioResponse, AreaUpdate
from app.models import Area
from app.models import Locacion
from ..auth.dependencies import get_current_user
from ..models import Usuario

router = APIRouter(prefix="/areas", tags=["Áreas"])

# Crear área
@router.post("/", response_model=AreaOut, status_code=status.HTTP_201_CREATED)
def crear_area(
    data: AreaCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user)
):
    # Verificar si la locación existe
    locacion = db.query(Locacion).filter(
        Locacion.id == data.locacion_id,
        Locacion.company_id == current_user.company_id
    ).first()
    if not locacion:
        raise HTTPException(status_code=404, detail="Locación no encontrada")
    
    # Verificar si el usuario tiene permisos para crear áreas
    if current_user.rol not in ["admin"]:
        raise HTTPException(status_code=403, detail="No tienes permisos")
    
    # Verificar si el área ya existe
    area_existente = db.query(Area).filter(Area.nombre == data.nombre, Area.locacion_id == data.locacion_id).first()
    if area_existente:
        raise HTTPException(status_code=400, detail="El área ya existe en esta locación")
    
    # Crear el área
    area = Area(**data.dict(), usuario_id=current_user.id, company_id=current_user.company_id)
    db.add(area)
    db.commit()
    db.refresh(area)
    return area

# Obtener todas las áreas de una locación
@router.get("/{locacion_id}/", response_model=list[AreaOut])
def obtener_areas(
    locacion_id: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user)
):
    # Verificar si la locación existe
    locacion = db.query(Locacion).filter(
        Locacion.id == locacion_id,
        Locacion.company_id == current_user.company_id
    ).first()
    if not locacion:
        raise HTTPException(status_code=404, detail="Locación no encontrada")
    
    # Obtener las áreas de la locación
    areas = db.query(Area).filter(Area.locacion_id == locacion_id).all()
    return areas

# Obtener un área específica
@router.get("/{locacion_id}/{area_id}/", response_model=AreaOut)
def obtener_area(
    locacion_id: UUID,
    area_id: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user)
):
    # Verificar si la locación existe
    locacion = db.query(Locacion).filter(
        Locacion.id == locacion_id,
        Locacion.company_id == current_user.company_id
    ).first()
    if not locacion:
        raise HTTPException(status_code=404, detail="Locación no encontrada")
    
    # Obtener el área
    area = db.query(Area).filter(Area.id == area_id, Area.locacion_id == locacion_id).first()
    if not area:
        raise HTTPException(status_code=404, detail="Área no encontrada")
    
    return area

# Editar un área
@router.put("/{locacion_id}/{area_id}/", response_model=AreaOut)
def editar_area(
    locacion_id: UUID,
    area_id: UUID,
    data: AreaUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user)
):
    # Verificar si la locación existe
    locacion = db.query(Locacion).filter(
        Locacion.id == locacion_id,
        Locacion.company_id == current_user.company_id
    ).first()
    if not locacion:
        raise HTTPException(status_code=404, detail="Locación no encontrada")
    
    # Obtener el área
    area = db.query(Area).filter(Area.id == area_id, Area.locacion_id == locacion_id).first()
    if not area:
        raise HTTPException(status_code=404, detail="Área no encontrada")
    
    if current_user.rol not in ["admin"]:
        raise HTTPException(status_code=403, detail="No tienes permisos")
    
    # Actualizar el área
    for key, value in data.dict().items():
        setattr(area, key, value)
    
    db.commit()
    db.refresh(area)
    return area

# Eliminar un área
@router.delete("/{locacion_id}/{area_id}/")
def eliminar_area(
    locacion_id: UUID,
    area_id: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user)
):
    # Verificar si la locación existe
    locacion = db.query(Locacion).filter(
        Locacion.id == locacion_id,
        Locacion.company_id == current_user.company_id
    ).first()
    if not locacion:
        raise HTTPException(status_code=404, detail="Locación no encontrada")
    
    # Obtener el área
    area = db.query(Area).filter(Area.id == area_id, Area.locacion_id == locacion_id).first()
    if not area:
        raise HTTPException(status_code=404, detail="Área no encontrada")
    
    # Verifiar si el que creo el área es el mismo que lo está eliminando
    if current_user.rol not in ["admin"]:
        raise HTTPException(status_code=403, detail="No tienes permisos")
    
    db.delete(area)
    db.commit()
    return {"detail": "Área eliminada con éxito"}

# obtener todas las areas creadas por el usuario
@router.get("/usuario/", response_model=list[AreaOut])
def obtener_areas_usuario(
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user)
):
    # Obtener las áreas creadas por el usuario
    areas = db.query(Area).filter(Area.usuario_id == current_user.id).all()
    return areas

# obtener todos los usuarios de un área
@router.get("/{locacion_id}/{area_id}/usuarios/", response_model=list[UsuarioResponse])
def obtener_usuarios_area(
    locacion_id: UUID,
    area_id: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user)
):
    # Verificar si la locación existe
    locacion = db.query(Locacion).filter(
        Locacion.id == locacion_id,
        Locacion.company_id == current_user.company_id
    ).first()
    if not locacion:
        raise HTTPException(status_code=404, detail="Locación no encontrada")
    
    # Obtener el área
    area = db.query(Area).filter(Area.id == area_id, Area.locacion_id == locacion_id).first()
    if not area:
        raise HTTPException(status_code=404, detail="Área no encontrada")
    
    # Obtener los usuarios del área
    usuarios = db.query(Usuario).filter(Usuario.area_id == area.id).all()
    return usuarios
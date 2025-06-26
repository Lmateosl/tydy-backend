from fastapi import APIRouter, Depends, HTTPException, Path, Security
from sqlalchemy.orm import Session
from sqlalchemy import or_
from uuid import UUID
from ..database import get_db
from .. import models, schemas
from ..auth.dependencies import get_current_user
from ..models import Usuario

router = APIRouter(prefix="/actividades", tags=["Actividades"])

# Crear actividad
@router.post("/", response_model=schemas.ActividadResponse)
def crear_actividad(
    actividad: schemas.ActividadCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    # Verificar que la categoría existe y pertenece a la misma compania
    categoria = db.query(models.Categoria).filter(
        (models.Categoria.id == actividad.categoria_id) &
        (models.Categoria.company_id == current_user.company_id)
    ).first()
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoría no encontrada o no pertenece a tu compañia")

    # Permisos
    if current_user.rol not in ["admin", "supervisor"]:
        raise HTTPException(status_code=403, detail="No tienes permisos para crear actividades")

    nueva_actividad = models.Actividad(
        nombre=actividad.nombre,
        categoria_id=actividad.categoria_id,
        usuario_id=current_user.id,
        company_id=current_user.company_id
    )
    db.add(nueva_actividad)
    db.commit()
    db.refresh(nueva_actividad)
    return nueva_actividad

# Listar actividades de la compania
@router.get("/", response_model=list[schemas.ActividadResponse])
def listar_actividades(
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    actividades = db.query(models.Actividad).filter(
        models.Actividad.company_id == current_user.company_id
    ).all()
    return actividades

# Obtener actividad específica
@router.get("/{actividad_id}", response_model=schemas.ActividadResponse)
def obtener_actividad(
    actividad_id: UUID = Path(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    actividad = db.query(models.Actividad).filter(
        models.Actividad.id == actividad_id,
        models.Actividad.company_id == current_user.company_id
    ).first()
    if not actividad:
        raise HTTPException(status_code=404, detail="Actividad no encontrada")
    return actividad

# Editar actividad
@router.put("/{actividad_id}", response_model=schemas.ActividadResponse)
def editar_actividad(
    actividad_update: schemas.ActividadUpdate,
    actividad_id: UUID = Path(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    actividad = db.query(models.Actividad).filter(
        models.Actividad.id == actividad_id,
        models.Actividad.company_id == current_user.company_id
    ).first()
    if not actividad:
        raise HTTPException(status_code=404, detail="Actividad no encontrada")

    if current_user.rol not in ["admin", "supervisor"]:
        raise HTTPException(status_code=403, detail="No tienes permisos para editar actividades")

    update_data = actividad_update.dict(exclude_unset=True)

    # Si se quiere cambiar la categoría, verificar que existe y pertenece al usuario
    if "categoria_id" in update_data:
        categoria = db.query(models.Categoria).filter(
            models.Categoria.id == update_data["categoria_id"],
        ).first()
        if not categoria:
            raise HTTPException(status_code=404, detail="Categoría nueva no encontrada")

    for key, value in update_data.items():
        setattr(actividad, key, value)

    db.commit()
    db.refresh(actividad)
    return actividad

# Eliminar actividad
@router.delete("/{actividad_id}")
def eliminar_actividad(
    actividad_id: UUID = Path(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    actividad = db.query(models.Actividad).filter(
        models.Actividad.id == actividad_id,
        models.Actividad.company_id == current_user.company_id
    ).first()
    if not actividad:
        raise HTTPException(status_code=404, detail="Actividad no encontrada")
    
    # Validar que no esté asociada a ninguna lista
    if actividad.listas:
        raise HTTPException(status_code=400, detail="No se puede eliminar la actividad porque está asociada a una lista")


    if current_user.rol not in ["admin", "supervisor"]:
        raise HTTPException(status_code=403, detail="No tienes permisos para eliminar actividades")

    db.delete(actividad)
    db.commit()
    return {"detalle": "Actividad eliminada correctamente"}

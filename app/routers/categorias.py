from fastapi import APIRouter, Depends, HTTPException, Path, Security
from sqlalchemy.orm import Session
from sqlalchemy import or_
from uuid import UUID
from ..database import get_db
from .. import models, schemas
from ..auth.dependencies import get_current_user
from ..models import Usuario

router = APIRouter(prefix="/categorias", tags=["Categorías"])

# Crear categoría
@router.post("/", response_model=schemas.CategoriaResponse)
def crear_categoria(
    categoria: schemas.CategoriaCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    nueva_categoria = models.Categoria(
        nombre=categoria.nombre,
        usuario_id=current_user.id,
        company_id=current_user.company_id
    )
    # Verificar si la categoría ya existe
    categoria_existente = db.query(models.Categoria).filter(
        models.Categoria.nombre == categoria.nombre,
        models.Categoria.company_id == current_user.company_id,
    ).first()
    if categoria_existente:
        raise HTTPException(status_code=400, detail="La categoría ya existe")
    
    if current_user.rol not in ["admin", "supervisor"]:
        raise HTTPException(status_code=403, detail="No tienes permisos")
    
    db.add(nueva_categoria)
    db.commit()
    db.refresh(nueva_categoria)
    return nueva_categoria

# Obtener todas las categorías del usuario actual
@router.get("/", response_model=list[schemas.CategoriaResponse])
def listar_categorias(
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    categorias = db.query(models.Categoria).filter(
        models.Categoria.company_id == current_user.company_id
    ).all()
    return categorias

# Obtener una categoría específica
@router.get("/{categoria_id}", response_model=schemas.CategoriaResponse)
def obtener_categoria(
    categoria_id: UUID = Path(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    # Verificar si la categoría existe
    categoria = db.query(models.Categoria).filter(
        models.Categoria.id == categoria_id,
        models.Categoria.company_id == current_user.company_id
    ).first()
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    return categoria

# Editar categoría
@router.put("/{categoria_id}", response_model=schemas.CategoriaResponse)
def editar_categoria(
    categoria_update: schemas.CategoriaUpdate,
    categoria_id: UUID = Path(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    categoria = db.query(models.Categoria).filter(
        models.Categoria.id == categoria_id,
        models.Categoria.company_id == current_user.company_id
    ).first()
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    
    # Verificar si el usuario tiene permisos para crear categorías
    if current_user.rol not in ["admin", "supervisor"]:
        raise HTTPException(status_code=403, detail="No tienes permisos")

    update_data = categoria_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(categoria, key, value)

    db.commit()
    db.refresh(categoria)
    return categoria

# Eliminar categoría
@router.delete("/{categoria_id}")
def eliminar_categoria(
    categoria_id: UUID = Path(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    categoria = db.query(models.Categoria).filter(
        models.Categoria.id == categoria_id,
        models.Categoria.company_id == current_user.company_id
    ).first()
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    
    # Verificar si el usuario tiene permisos para crear categorías
    if current_user.rol not in ["admin", "supervisor"]:
        raise HTTPException(status_code=403, detail="No tienes permisos")

    # Verificar si la categoría tiene actividades asociadas
    actividades = db.query(models.Actividad).filter(
        models.Actividad.categoria_id == categoria_id
    ).first()
    if actividades:
        raise HTTPException(status_code=400, detail="No se puede eliminar una categoría que tiene actividades asociadas")

    db.delete(categoria)
    db.commit()
    return {"detalle": "Categoría eliminada correctamente"}

@router.get("/categoria/{categoria_id}/actividades", response_model=list[schemas.ActividadResponse])
def actividades_por_categoria(
    categoria_id: UUID = Path(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    # Verificar que la categoría exista y pertenezca al usuario actual
    categoria = db.query(models.Categoria).filter(
        models.Categoria.id == categoria_id,
        models.Categoria.company_id == current_user.company_id
    ).first()
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")

    actividades = db.query(models.Actividad).filter(
        models.Actividad.categoria_id == categoria_id,
    ).all()

    return actividades
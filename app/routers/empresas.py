from fastapi import APIRouter, Depends, HTTPException, Path, Security, File, UploadFile, Form
from sqlalchemy.orm import Session
from uuid import UUID, uuid4
from datetime import datetime
from ..database import get_db
from .. import schemas, models
from ..auth.dependencies import get_current_user
from ..models import Usuario
import cloudinary.uploader

router = APIRouter(prefix="/empresas", tags=["Empresas"])

# Crear empresa
@router.post("/", response_model=schemas.EmpresaResponse)
def crear_empresa(
    nombre: str = Form(...),
    imagen: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    if current_user.rol != "admin":
        raise HTTPException(status_code=403, detail="No tienes permisos")
    
    empresa_existente = db.query(models.Empresa).filter(
        models.Empresa.nombre == nombre,
        models.Empresa.company_id == current_user.company_id
    ).first()
    if empresa_existente:
        raise HTTPException(status_code=400, detail="Ya existe una empresa con este nombre")
    
    ruta_imagen = None
    if imagen:
        if imagen.content_type not in ["image/jpeg", "image/png"]:
            raise HTTPException(status_code=400, detail="Formato de imagen no válido")

        resultado = cloudinary.uploader.upload(imagen.file, folder="empresas")
        ruta_imagen = resultado.get("secure_url")

    nueva_empresa = models.Empresa(
        nombre=nombre,
        usuario_id=current_user.id,
        company_id=current_user.company_id,
        imagen=ruta_imagen
    )

    db.add(nueva_empresa)
    db.commit()
    db.refresh(nueva_empresa)
    return nueva_empresa

# Obtener todas las empresas del usuario actual
@router.get("/", response_model=list[schemas.EmpresaResponse])
def listar_empresas(
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    empresas = db.query(models.Empresa).filter(models.Empresa.company_id == current_user.company_id).all()
    return empresas

# Obtener una empresa específica
@router.get("/{empresa_id}", response_model=schemas.EmpresaResponse)
def obtener_empresa(
    empresa_id: UUID = Path(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    empresa = db.query(models.Empresa).filter(
        models.Empresa.id == empresa_id,
        models.Empresa.company_id == current_user.company_id
    ).first()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no encontrada o sin permiso")
    return empresa

# Editar empresa
@router.put("/{empresa_id}", response_model=schemas.EmpresaResponse)
def editar_empresa(
    empresa_id: UUID = Path(...),
    nombre: str = Form(None),
    imagen: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    if current_user.rol != "admin":
        raise HTTPException(status_code=403, detail="No tienes permisos")

    empresa = db.query(models.Empresa).filter(
        models.Empresa.id == empresa_id,
        models.Empresa.company_id == current_user.company_id
    ).first()

    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no encontrada o sin permiso")

    if nombre is not None:
        empresa.nombre = nombre

    if imagen:
        if imagen.content_type not in ["image/jpeg", "image/png"]:
            raise HTTPException(status_code=400, detail="Formato de imagen no válido")

        resultado = cloudinary.uploader.upload(imagen.file, folder="empresas")
        empresa.imagen = resultado.get("secure_url")

    db.commit()
    db.refresh(empresa)
    return empresa

# Eliminar empresa
@router.delete("/{empresa_id}")
def eliminar_empresa(
    empresa_id: UUID = Path(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    if current_user.rol != "admin":
        raise HTTPException(status_code=403, detail="No tienes permisos")
    
    empresa = db.query(models.Empresa).filter(
        models.Empresa.id == empresa_id,
        models.Empresa.company_id == current_user.company_id
    ).first()
    if not empresa or empresa.usuario_id != current_user.id:
        raise HTTPException(status_code=404, detail="Empresa no encontrada o sin permiso")

    db.delete(empresa)
    db.commit()
    return {"detalle": "Empresa eliminada correctamente"}
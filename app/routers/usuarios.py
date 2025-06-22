from fastapi import APIRouter, Depends, HTTPException, Security, Path, UploadFile, File, Form, Depends
from sqlalchemy.orm import Session
from .. import schemas, models
from ..database import get_db
from ..utils import hash_password
from app.models import Usuario
from app.auth.dependencies import get_current_user
from uuid import UUID
from typing import List
from app.models import Categoria
from app.models import Empresa
from app.models import Actividad
from app.models import ListaActividad
from PIL import Image
import os, shutil
import uuid

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])
UPLOAD_DIR = "uploads/fotos_usuarios"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def comprimir_imagen(imagen_path: str, calidad: int = 75, max_ancho: int = 500):
    try:
        img = Image.open(imagen_path)
        img = img.convert("RGB")  # fuerza a JPEG y evita errores
        if img.width > max_ancho:
            proporcion = max_ancho / img.width
            nuevo_alto = int(img.height * proporcion)
            img = img.resize((max_ancho, nuevo_alto))

        img.save(imagen_path, "JPEG", quality=calidad)
    except Exception as e:
        print("Error al comprimir imagen:", e)

@router.get("/perfil", response_model=schemas.me)
def obtener_perfil(usuario: Usuario = Depends(get_current_user)):
    return {"nombre": usuario.nombre, "email": usuario.email, "rol": usuario.rol, "id": usuario.id}

@router.post("/", response_model=schemas.UsuarioResponse)
def crear_usuario(
    nombre: str = Form(...),
    email: str = Form(...),
    contrasena: str = Form(...),
    rol: str = Form(...),
    numero: str = Form(None),
    direccion: str = Form(None),
    area_id: str = Form(None),
    identificacion: str = Form(None),
    supervisor_id: str = Form(None),
    foto: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    if current_user.rol != "admin":
        raise HTTPException(status_code=403, detail="No tienes permisos para crear usuarios")

    if db.query(Usuario).filter(Usuario.email == email).first():
        raise HTTPException(status_code=400, detail="Email ya registrado")

    hashed_password = hash_password(contrasena)

    ruta_foto = None
    if foto:
        if foto.content_type not in ["image/jpeg", "image/png"]:
            raise HTTPException(status_code=400, detail="Formato de imagen no válido")

        extension = "jpg"  # Fuerzamos JPEG
        nombre_archivo = f"{uuid.uuid4()}.{extension}"
        ruta_foto = os.path.join(UPLOAD_DIR, nombre_archivo)

        with open(ruta_foto, "wb") as buffer:
            shutil.copyfileobj(foto.file, buffer)

        # Comprimir la imagen después de guardarla
        comprimir_imagen(ruta_foto)

    nuevo_usuario = Usuario(
        nombre=nombre,
        email=email,
        contrasena=hashed_password,
        rol=rol,
        numero=numero,
        direccion=direccion,
        area_id=area_id if area_id else None,
        supervisor_id=supervisor_id if supervisor_id else None,
        foto=ruta_foto,
        creado_por=current_user.id,
        company_id=current_user.company_id,
        identificacion = identificacion
    )

    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)

    return nuevo_usuario

@router.put("/{usuario_id}", response_model=schemas.UsuarioResponse)
def editar_usuario(
    usuario_id: UUID = Path(..., description="ID del usuario a editar"),
    nombre: str = Form(None),
    email: str = Form(None),
    contrasena: str = Form(None),
    rol: str = Form(None),
    numero: str = Form(None),
    direccion: str = Form(None),
    identificacion: str = Form(None),
    area_id: str = Form(None),
    supervisor_id: str = Form(None),
    foto: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    if current_user.rol != "admin":
        raise HTTPException(status_code=403, detail="No tienes permisos para editar usuarios")

    db_usuario = db.query(models.Usuario).filter(
        models.Usuario.id == usuario_id,
        models.Usuario.company_id == current_user.company_id
    ).first()
    if not db_usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Validar email
    if email and email != db_usuario.email:
        existing_user = db.query(models.Usuario).filter(models.Usuario.email == email).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Email ya registrado por otro usuario")

    # Actualizar campos si vienen en el form
    if nombre is not None:
        db_usuario.nombre = nombre
    if email is not None:
        db_usuario.email = email
    if contrasena is not None:
        db_usuario.contrasena = hash_password(contrasena)
    if rol is not None:
        db_usuario.rol = rol
    if numero is not None:
        db_usuario.numero = numero
    if direccion is not None:
        db_usuario.direccion = direccion
    if area_id is not None:
        db_usuario.area_id = area_id
    if supervisor_id is not None:
        db_usuario.supervisor_id = supervisor_id
    if identificacion is not None:
        db_usuario.identificacion = identificacion

    # Procesar foto si viene
    if foto:
        if foto.content_type not in ["image/jpeg", "image/png"]:
            raise HTTPException(status_code=400, detail="Formato de imagen no válido")
        
        extension = foto.filename.split(".")[-1]
        from uuid import uuid4
        nombre_archivo = f"{uuid4()}.{extension}"
        ruta_foto = os.path.join(UPLOAD_DIR, nombre_archivo)

        with open(ruta_foto, "wb") as buffer:
            shutil.copyfileobj(foto.file, buffer)
        
        # Comprimir la imagen después de guardarla
        comprimir_imagen(ruta_foto)

        # Actualizar ruta foto en DB
        db_usuario.foto = ruta_foto

    db.commit()
    db.refresh(db_usuario)
    return db_usuario

@router.delete("/{usuario_id}")
def eliminar_usuario(
    usuario_id: UUID = Path(..., description="ID del usuario a eliminar"),
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    if current_user.rol != "admin":
        raise HTTPException(status_code=403, detail="No tienes permisos para eliminar usuarios")

    db_usuario = db.query(models.Usuario).filter(
        models.Usuario.id == usuario_id,
        models.Usuario.company_id == current_user.company_id
    ).first()
    if not db_usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    db.delete(db_usuario)
    db.commit()
    return {"detail": "Usuario eliminado"}


@router.get("/", response_model=List[schemas.UsuarioResponse])
def obtener_usuarios_creados(
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    if current_user.rol not in ["admin", "supervisor"]:
        raise HTTPException(status_code=403, detail="No tienes permisos para ver usuarios")

    usuarios = db.query(models.Usuario).filter(
        models.Usuario.company_id == current_user.company_id
    ).all()
    
    return usuarios

@router.get("/{usuario_id}", response_model=schemas.UsuarioResponse)
def obtener_usuario(
    usuario_id: UUID = Path(..., description="ID del usuario a obtener"),
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    if current_user.rol.lower() not in ["admin", "supervisor"]:
        raise HTTPException(status_code=403, detail="No tienes permisos")

    db_usuario = db.query(models.Usuario).filter(
        models.Usuario.id == usuario_id,
        models.Usuario.company_id == current_user.company_id
    ).first()
    if not db_usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    return db_usuario

@router.get("/mis-usuarios", response_model=List[schemas.UsuarioResponse])
def obtener_usuarios_creados_por_mi(
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    return db.query(models.Usuario).filter(models.Usuario.creado_por == current_user.id).all()

@router.get("/mis-empresas", response_model=List[schemas.EmpresaResponse])
def obtener_empresas_creadas(
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    return db.query(Empresa).filter(Empresa.usuario_id == current_user.id).all()

@router.get("/mis-categorias", response_model=List[schemas.CategoriaResponse])
def obtener_categorias_creadas(
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    return db.query(Categoria).filter(Categoria.usuario_id == current_user.id).all()

@router.get("/mis-actividades", response_model=List[schemas.ActividadResponse])
def obtener_actividades_creadas(
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    return db.query(Actividad).filter(Actividad.usuario_id == current_user.id).all()

@router.get("/mis-listas-actividades", response_model=List[schemas.ListaActividadResponse])
def obtener_listas_actividades_creadas(
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    return db.query(ListaActividad).filter(ListaActividad.usuario_id == current_user.id).all()
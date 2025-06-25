from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from uuid import UUID
from datetime import datetime
from typing import List
from typing import Literal

# Usuario
# Este modelo representa la estructura de los datos del usuario
class UsuarioCreate(BaseModel):
    nombre: str
    email: EmailStr
    contrasena: str
    rol: str
    numero: Optional[str] = None
    direccion: Optional[str] = None
    foto: Optional[str] = None
    area_id: Optional[UUID] = None
    supervisor_id: Optional[UUID] = None
    identificacion: Optional[str] = None

class UsuarioResponse(BaseModel):
    id: UUID
    nombre: str
    email: str
    rol: str
    company_id: UUID
    numero: Optional[str] = None
    direccion: Optional[str] = None
    foto: Optional[str] = None
    identificacion: Optional[str] = None
    area_id: Optional[UUID] = None
    area_nombre: Optional[str] = None
    supervisor_id: Optional[UUID] = None
    creado_por: Optional[UUID] = None

    class Config:
        from_attributes = True

class me(BaseModel):
    rol: str
    email: str
    nombre: str
    id: UUID
    company_id: UUID
    numero: Optional[str] = None
    direccion: Optional[str] = None
    foto: Optional[str] = None
    area_id: Optional[UUID] = None
    supervisor_id: Optional[UUID] = None
    identificacion: Optional[str] = None
    empresa_nombre: Optional[str] = None

class UsuarioUpdate(BaseModel):
    nombre: Optional[str] = None
    email: Optional[EmailStr] = None
    contrasena: Optional[str] = None
    rol: Literal['admin', 'empleado', 'supervisor', 'cliente']
    numero: Optional[str] = None
    direccion: Optional[str] = None
    foto: Optional[str] = None
    identificacion: Optional[str] = None
    area_id: Optional[UUID] = None
    supervisor_id: Optional[UUID] = None

class UsuarioLogin(BaseModel):
    email: str
    contrasena: str

# Token
# Este modelo representa la estructura del token de acceso
class Token(BaseModel):
    access_token: str
    token_type: str

# Empresa
# Este modelo representa la estructura de los datos de la empresa
class EmpresaBase(BaseModel):
    nombre: str
    imagen: Optional[str] = None

class EmpresaCreate(EmpresaBase):
    pass

class EmpresaUpdate(BaseModel):
    nombre: Optional[str] = None
    imagen: Optional[str] = None

class EmpresaResponse(EmpresaBase):
    id: UUID
    usuario_id: UUID
    creado_en: datetime
    company_id: UUID

    class Config:
        from_attributes = True

# Locacion
# Este modelo representa la estructura de los datos de la locación
class LocacionBase(BaseModel):
    nombre: str
    direccion: Optional[str] = None
    latitud: Optional[float] = None
    longitud: Optional[float] = None

class LocacionCreate(LocacionBase):
    empresa_id: UUID

class LocacionUpdate(BaseModel):
    nombre: Optional[str] = None
    direccion: Optional[str] = None
    latitud: Optional[float] = None
    longitud: Optional[float] = None

class LocacionOut(LocacionBase):
    id: UUID
    empresa_id: UUID
    usuario_id: UUID
    creado_en: datetime
    company_id: UUID
    nombre: str
    direccion: Optional[str] = None
    latitud: Optional[float] = None
    longitud: Optional[float] = None

    class Config:
        from_attributes = True

# Area
# Este modelo representa la estructura de los datos del área
class AreaBase(BaseModel):
    nombre: str
    locacion_id: UUID

class AreaCreate(AreaBase):
    pass

class AreaUpdate(BaseModel):
    nombre: Optional[str] = None
    locacion_id: Optional[UUID] = None

class AreaOut(BaseModel):
    id: UUID
    nombre: str
    locacion_id: UUID
    usuario_id: UUID
    creado_en: datetime
    company_id: UUID

    class Config:
        from_attributes = True

# categoria
# Este modelo representa la estructura de los datos de la categoría
class CategoriaBase(BaseModel):
    nombre: str

class CategoriaCreate(CategoriaBase):
    pass

class CategoriaUpdate(BaseModel):
    nombre: str | None = None

class CategoriaResponse(CategoriaBase):
    id: UUID
    usuario_id: UUID
    creado_en: datetime
    company_id: UUID

    class Config:
        from_attributes = True

# Actividades
class ActividadBase(BaseModel):
    nombre: Optional[str] = None
    categoria_id: Optional[UUID] = None

class ActividadCreate(ActividadBase):
    nombre: str  # Forzamos aquí que sea requerido

class ActividadUpdate(ActividadBase):
    pass

class ActividadResponse(ActividadBase):
    id: UUID
    usuario_id: UUID
    creado_en: datetime
    company_id: UUID

    class Config:
        from_attribute = True

# Lista de actividades

class ListaActividadCreate(BaseModel):
    nombre: str
    code: Optional[bool] = False
    codeout: Optional[bool] = False
    qrin: Optional[bool] = True
    qrout: Optional[bool] = False
    actividad_ids: Optional[List[UUID]] = Field(default_factory=list)
    imagen: Optional[bool] = False

class ListaActividadUpdate(BaseModel):
    nombre: Optional[str] = None
    code: Optional[bool] = False
    qrin: Optional[bool] = True
    qrout: Optional[bool] = False
    codeout: Optional[bool] = False
    actividad_ids: Optional[List[UUID]] = None
    imagen: Optional[bool] = False

class ListaActividadResponse(BaseModel):
    id: UUID
    nombre: str
    company_id: UUID
    usuario_id: UUID
    code: Optional[str]
    codeout: Optional[str]
    qrin: Optional[str]
    qrout: Optional[str]
    creado_en: datetime
    actividades: List[ActividadResponse] = []
    imagen: Optional[bool] = False

    class Config:
        from_attribute = True

# Actividades Usuario
class ActividadUsuarioBase(BaseModel):
    lista_id: Optional[UUID] = None
    finalizada: Optional[bool] = False
    comentario: Optional[str] = None

class ActividadUsuarioCreate(ActividadUsuarioBase):
    pass

class ActividadUsuarioUpdate(ActividadUsuarioBase):
    pass

class ActividadUsuarioResponse(ActividadUsuarioBase):
    id: UUID
    creado_en: datetime
    company_id: UUID
    usuario_id: UUID

    class Config:
        from_attributes = True

class EmpresaMini(BaseModel):
    id: UUID
    nombre: str

    class Config:
        from_attributes = True

class LocacionMini(BaseModel):
    id: UUID
    nombre: str
    empresa: EmpresaMini

    class Config:
        from_attributes = True

class AreaMini(BaseModel):
    id: UUID
    nombre: str
    locacion: LocacionMini

    class Config:
        from_attributes = True

class ActividadUsuarioUsuario(BaseModel):
    id: UUID
    nombre: str
    identificacion: Optional[str] = None
    area: Optional[AreaMini]

    class Config:
        from_attributes = True

class ActividadMiniResponse(BaseModel):
    id: UUID
    nombre: str

    class Config:
        from_attributes = True

class ActividadUsuarioListaConActividades(BaseModel):
    id: UUID
    nombre: str
    actividades: List[ActividadMiniResponse] = []

    class Config:
        from_attributes = True

class ActividadUsuarioResponseExtendido(BaseModel):
    id: UUID
    hora_inicio: datetime
    hora_fin: Optional[datetime]
    finalizada: Optional[bool]
    comentario: Optional[str]
    imagen: Optional[str]

    usuario: ActividadUsuarioUsuario  # Aquí viene toda la jerarquía: area, locacion, empresa
    lista: Optional[ActividadUsuarioListaConActividades]

    class Config:
        from_attributes = True

class ActividadFinalizar(BaseModel):
    comentario: Optional[str]
    imagen: Optional[str]

    class Config:
        from_attributes = True

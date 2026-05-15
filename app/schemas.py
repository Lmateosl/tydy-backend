from pydantic import BaseModel as PydanticBaseModel, ConfigDict, EmailStr, Field
from typing import Optional
from uuid import UUID
from datetime import datetime
from typing import List
from typing import Literal
from .datetime_utils import serialize_datetime_utc


class BaseModel(PydanticBaseModel):
    model_config = ConfigDict(json_encoders={datetime: serialize_datetime_utc})

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

class CompanyBase(BaseModel):
    nombre: str
    ruc: Optional[str] = None
    direccion: Optional[str] = None
    telefono: Optional[str] = None
    logo: Optional[str] = None

class ComapnyResponse(CompanyBase):
    pass

    class Config:
        from_attributes = True

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

class ClienteEmpresaAsignacion(BaseModel):
    usuario_id: UUID
    empresa_id: UUID

class ClienteEmpresaResponse(BaseModel):
    id: UUID
    usuario_id: UUID
    empresa_id: UUID
    company_id: UUID
    creado_en: datetime
    creado_por: UUID
    empresa: EmpresaResponse

    class Config:
        from_attributes = True

# Locacion
# Este modelo representa la estructura de los datos de la locación
class LocacionBase(BaseModel):
    nombre: str
    direccion: Optional[str] = None
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    radio_verificacion_metros: Optional[int] = 1000
    supervisor_id: Optional[UUID] = None

class LocacionCreate(LocacionBase):
    empresa_id: UUID

class LocacionUpdate(BaseModel):
    nombre: Optional[str] = None
    direccion: Optional[str] = None
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    radio_verificacion_metros: Optional[int] = None
    supervisor_id: Optional[UUID] = None

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
    radio_verificacion_metros: Optional[int] = 1000

    class Config:
        from_attributes = True


class LocacionSupervisorAssign(BaseModel):
    supervisor_id: UUID


class EmpresaSupervisorAssign(BaseModel):
    supervisor_id: UUID

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
    latitud_inicio: Optional[float] = None
    longitud_inicio: Optional[float] = None
    precision_inicio: Optional[float] = None
    distancia_validacion: Optional[float] = None
    metodo_inicio: Optional[Literal["qr", "codigo", "manual"]] = None
    latitud_fin: Optional[float] = None
    longitud_fin: Optional[float] = None
    precision_fin: Optional[float] = None
    distancia_fin: Optional[float] = None
    metodo_fin: Optional[Literal["qr", "codigo", "manual"]] = None

class ActividadUsuarioCreate(ActividadUsuarioBase):
    pass

class ActividadUsuarioUpdate(ActividadUsuarioBase):
    pass

class ActividadUsuarioResponse(ActividadUsuarioBase):
    id: UUID
    creado_en: datetime
    company_id: UUID
    usuario_id: UUID
    supervisor_id: Optional[UUID] = None
    estado_verificacion: Optional[str] = None
    duracion_segundos: Optional[int] = None
    evidencia_obligatoria: Optional[bool] = None
    evidencia_entregada: Optional[bool] = None
    evidencia_subida_en: Optional[datetime] = None
    evidencia_usuario_id: Optional[UUID] = None
    evidencia_tipo: Optional[str] = None
    evidencia_nombre_archivo: Optional[str] = None

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

# -------------------------
# Feedback QR Schemas
# -------------------------
class FeedbackQRCreate(BaseModel):
    empresa_id: UUID
    locacion_id: Optional[UUID] = None
    contexto: Optional[str] = None

class FeedbackQRUpdate(BaseModel):
    empresa_id: Optional[UUID] = None
    locacion_id: Optional[UUID] = None
    contexto: Optional[str] = None
    nombre: Optional[str] = None
    direccion: Optional[str] = None

class FeedbackQRResponse(BaseModel):
    id: UUID
    url: str
    empresa_id: Optional[UUID] = None
    locacion_id: Optional[UUID] = None
    contexto: Optional[str] = None
    nombre: str
    direccion: Optional[str] = None

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
    evidencia_obligatoria: Optional[bool]
    evidencia_entregada: Optional[bool]
    evidencia_subida_en: Optional[datetime]
    evidencia_usuario_id: Optional[UUID]
    evidencia_tipo: Optional[str]
    evidencia_nombre_archivo: Optional[str]
    latitud_inicio: Optional[float]
    longitud_inicio: Optional[float]
    precision_inicio: Optional[float]
    distancia_validacion: Optional[float]
    metodo_inicio: Optional[str]
    latitud_fin: Optional[float]
    longitud_fin: Optional[float]
    precision_fin: Optional[float]
    distancia_fin: Optional[float]
    metodo_fin: Optional[str]
    duracion_segundos: Optional[int]
    supervisor_id: Optional[UUID]
    estado_verificacion: Optional[str]

    usuario: ActividadUsuarioUsuario  # Aquí viene toda la jerarquía: area, locacion, empresa
    lista: Optional[ActividadUsuarioListaConActividades]

    class Config:
        from_attributes = True

class ActividadFinalizar(BaseModel):
    comentario: Optional[str]
    imagen: Optional[str]

    class Config:
        from_attributes = True


# Otros esquemas usuario
class EmpresaMini(BaseModel):
    id: UUID
    nombre: str
    imagen: Optional[str]

    class Config:
        from_attributes = True


class LocacionMini(BaseModel):
    id: UUID
    nombre: str
    direccion: Optional[str]
    latitud: Optional[float]
    longitud: Optional[float]
    radio_verificacion_metros: Optional[int] = 1000
    empresa: EmpresaMini

    class Config:
        from_attributes = True


class AreaMini(BaseModel):
    id: UUID
    nombre: str
    locacion: LocacionMini

    class Config:
        from_attributes = True

# -------------------------
# Feedback Schemas
# -------------------------
class FeedbackCreate(BaseModel):
    nombre: Optional[str] = None
    empresa: Optional[str] = None
    direccion: Optional[str] = None
    empresa_id: Optional[UUID] = None
    locacion_id: Optional[UUID] = None
    contexto: Optional[str] = None
    calificacion: float
    company_id: UUID
    comentario: Optional[str] = None
    foto: Optional[str] = None


class FeedbackUpdate(BaseModel):
    nombre: Optional[str] = None
    empresa: Optional[str] = None
    direccion: Optional[str] = None
    empresa_id: Optional[UUID] = None
    locacion_id: Optional[UUID] = None
    contexto: Optional[str] = None
    calificacion: Optional[float] = None
    comentario: Optional[str] = None
    foto: Optional[str] = None


class FeedbackResponse(BaseModel):
    id: UUID
    nombre: Optional[str] = None
    empresa: Optional[str] = None
    direccion: Optional[str] = None
    empresa_id: Optional[UUID] = None
    locacion_id: Optional[UUID] = None
    contexto: Optional[str] = None
    calificacion: float
    comentario: Optional[str] = None
    foto: Optional[str] = None
    creado_en: datetime

    class Config:
        from_attributes = True


class IncidenteCreate(BaseModel):
    tipo: Literal["feedback_negativo", "actividad_no_finalizada", "comentario_empleado", "evidencia_faltante", "manual"]
    prioridad: Literal["baja", "media", "alta", "critica"] = "media"
    descripcion: str
    empresa_id: Optional[UUID] = None
    locacion_id: Optional[UUID] = None
    area_id: Optional[UUID] = None
    empleado_id: Optional[UUID] = None
    supervisor_id: Optional[UUID] = None
    asignado_a_id: Optional[UUID] = None
    actividad_usuario_id: Optional[UUID] = None
    feedback_id: Optional[UUID] = None
    evidencia_inicial: Optional[str] = None


class IncidenteUpdate(BaseModel):
    tipo: Optional[Literal["feedback_negativo", "actividad_no_finalizada", "comentario_empleado", "evidencia_faltante", "manual"]] = None
    prioridad: Optional[Literal["baja", "media", "alta", "critica"]] = None
    descripcion: Optional[str] = None
    estado: Optional[Literal["abierto", "asignado", "en_proceso", "resuelto", "cerrado"]] = None
    empresa_id: Optional[UUID] = None
    locacion_id: Optional[UUID] = None
    area_id: Optional[UUID] = None
    empleado_id: Optional[UUID] = None
    supervisor_id: Optional[UUID] = None
    asignado_a_id: Optional[UUID] = None
    actividad_usuario_id: Optional[UUID] = None
    feedback_id: Optional[UUID] = None
    evidencia_inicial: Optional[str] = None
    evidencia_resolucion: Optional[str] = None


class IncidenteResolver(BaseModel):
    evidencia_resolucion: Optional[str] = None


class IncidenteComentarioCreate(BaseModel):
    mensaje: Optional[str] = Field(default=None, max_length=2000)


class IncidenteCerrar(BaseModel):
    pass


class IncidenteResponse(BaseModel):
    id: UUID
    tipo: str
    prioridad: str
    descripcion: str
    estado: str
    company_id: UUID
    empresa_id: Optional[UUID] = None
    locacion_id: Optional[UUID] = None
    area_id: Optional[UUID] = None
    empleado_id: Optional[UUID] = None
    supervisor_id: Optional[UUID] = None
    asignado_a_id: Optional[UUID] = None
    actividad_usuario_id: Optional[UUID] = None
    feedback_id: Optional[UUID] = None
    evidencia_inicial: Optional[str] = None
    evidencia_resolucion: Optional[str] = None
    foto_resolucion: Optional[str] = None
    creado_en: datetime
    actualizado_en: datetime
    ultimo_evento_en: Optional[datetime] = None
    resuelto_en: Optional[datetime] = None
    cerrado_en: Optional[datetime] = None
    creado_por: UUID

    class Config:
        from_attributes = True


class IncidenteEventoActorResponse(BaseModel):
    id: Optional[UUID] = None
    nombre: Optional[str] = None
    rol: Optional[str] = None

    class Config:
        from_attributes = True


class IncidenteEventoResponse(BaseModel):
    id: UUID
    incidente_id: UUID
    tipo_evento: str
    actor_id: Optional[UUID] = None
    actor_rol: Optional[str] = None
    actor: Optional[IncidenteEventoActorResponse] = None
    mensaje: Optional[str] = None
    foto_url: Optional[str] = None
    metadata: dict = Field(default_factory=dict, alias="metadata_json")
    creado_en: datetime

    class Config:
        from_attributes = True
        populate_by_name = True


class IncidenteTimelineResponse(BaseModel):
    items: list[IncidenteEventoResponse] = Field(default_factory=list)
    total: int = 0


class NotificacionActorResponse(BaseModel):
    id: Optional[UUID] = None
    nombre: Optional[str] = None
    rol: Optional[str] = None

    class Config:
        from_attributes = True


class NotificacionItemResponse(BaseModel):
    id: UUID
    notification_id: UUID
    user_id: UUID
    tipo: str
    categoria: str
    evento: str
    severity: str
    titulo: str
    mensaje: str
    source_type: Optional[str] = None
    source_id: Optional[UUID] = None
    source_event_id: Optional[UUID] = None
    deep_link: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    actor: Optional[NotificacionActorResponse] = None
    read_at: Optional[datetime] = None
    delivered_at: datetime
    created_at: datetime


class NotificacionesListResponse(BaseModel):
    items: list[NotificacionItemResponse] = Field(default_factory=list)
    total: int = 0


class NotificacionesUnreadCountResponse(BaseModel):
    unread_count: int


class NotificacionMarcarLeidaResponse(BaseModel):
    detail: str
    read_at: datetime


class NotificacionMarcarTodasLeidasResponse(BaseModel):
    detail: str
    updated: int


class AlertaManualCreate(BaseModel):
    titulo: str = Field(min_length=1, max_length=140)
    mensaje: str = Field(min_length=1, max_length=2000)
    severity: Literal["info", "warning", "critical"] = "info"
    audiencia_tipo: Literal["all", "role", "empresa", "locacion", "user"]
    rol: Optional[Literal["admin", "supervisor", "empleado"]] = None
    empresa_id: Optional[UUID] = None
    locacion_id: Optional[UUID] = None
    user_ids: list[UUID] = Field(default_factory=list)


class DashboardRiesgoLocacionItem(BaseModel):
    locacion_id: Optional[UUID] = None
    locacion_nombre: str
    empresa_nombre: Optional[str] = None
    total_problemas: int
    actividades_no_verificadas: int
    evidencias_faltantes: int


class DashboardRiesgoEmpleadoPendienteItem(BaseModel):
    usuario_id: Optional[UUID] = None
    nombre: str
    identificacion: Optional[str] = None
    area_nombre: Optional[str] = None
    locacion_nombre: Optional[str] = None
    total_pendientes: int


class DashboardRiesgoComentarioRecienteItem(BaseModel):
    actividad_id: UUID
    comentario: str
    hora_inicio: datetime
    hora_fin: Optional[datetime] = None
    usuario_id: Optional[UUID] = None
    usuario_nombre: Optional[str] = None
    locacion_nombre: Optional[str] = None
    empresa_nombre: Optional[str] = None
    estado_verificacion: Optional[str] = None


class DashboardRiesgoFeedbackNegativoItem(BaseModel):
    feedback_id: UUID
    nombre: Optional[str] = None
    empresa: str
    direccion: str
    calificacion: float
    comentario: Optional[str] = None
    creado_en: datetime


class DashboardIncidenteRecienteItem(BaseModel):
    id: UUID
    estado: str
    tipo: str
    prioridad: str
    locacion_id: Optional[UUID] = None
    locacion_nombre: Optional[str] = None
    area_id: Optional[UUID] = None
    area_nombre: Optional[str] = None
    empresa_id: Optional[UUID] = None
    empresa_nombre: Optional[str] = None
    creado_en: datetime
    resuelto_en: Optional[datetime] = None


class DashboardLocacionIncidenteItem(BaseModel):
    locacion_id: Optional[UUID] = None
    locacion_nombre: Optional[str] = None
    empresa_nombre: Optional[str] = None
    total_incidentes: int
    incidentes_abiertos: int


class PortalClienteSeguimientoRecienteItem(BaseModel):
    id: UUID
    estado: str
    tipo_publico: str
    locacion_nombre: Optional[str] = None
    area_nombre: Optional[str] = None
    creado_en: datetime
    resuelto_en: Optional[datetime] = None
    evidencia_resolucion: Optional[str] = None
    foto_resolucion: Optional[str] = None
    tiempo_respuesta_horas: Optional[float] = None


class PortalClienteAreaSeguimientoItem(BaseModel):
    locacion_id: Optional[UUID] = None
    locacion_nombre: Optional[str] = None
    area_id: Optional[UUID] = None
    area_nombre: Optional[str] = None
    total_seguimientos: int
    seguimientos_abiertos: int


class DashboardRiesgosResponse(BaseModel):
    locaciones_con_problemas: List[DashboardRiesgoLocacionItem] = []
    empleados_con_pendientes: List[DashboardRiesgoEmpleadoPendienteItem] = []
    comentarios_recientes: List[DashboardRiesgoComentarioRecienteItem] = []
    feedback_negativo_reciente: List[DashboardRiesgoFeedbackNegativoItem] = []
    incidentes_recientes: List[DashboardIncidenteRecienteItem] = []
    locaciones_con_mas_incidentes: List[DashboardLocacionIncidenteItem] = []
    seguimientos_recientes: List[PortalClienteSeguimientoRecienteItem] = []
    areas_con_seguimiento: List[PortalClienteAreaSeguimientoItem] = []


class PortalClienteResumenResponse(BaseModel):
    actividades_hoy: int = 0
    actividades_completadas_hoy: int = 0
    actividades_pendientes_hoy: int = 0
    actividades_vencidas: int = 0
    empleados_activos_hoy: int = 0
    locaciones_con_actividad_hoy: int = 0
    evidencias_faltantes: int = 0
    feedbacks_negativos: int = 0
    incidentes_abiertos: int = 0
    seguimientos_abiertos: int = 0
    seguimientos_resueltos: int = 0
    tiempo_promedio_respuesta_horas: float = 0.0

from sqlalchemy import Column, String, Text, TIMESTAMP, ForeignKey, Numeric, Table, Boolean, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
from .database import Base
from .datetime_utils import utc_now_naive
from datetime import datetime
from uuid import uuid4
from sqlalchemy.orm import relationship
from sqlalchemy import DateTime

#Comapanies
# La compania que es la que abarca a todos los usuarios por ejemplo Britot

class Company(Base):
    __tablename__ = "companies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre = Column(Text, nullable=False)
    ruc = Column(Text)
    direccion = Column(Text)
    telefono = Column(Text)
    creado_en = Column(DateTime, default=datetime.utcnow)
    email = Column(Text, unique=True)
    logo = Column(Text)

    usuarios = relationship("Usuario", back_populates="own_company")
    empresas = relationship("Empresa", back_populates="own_company")
    locaciones = relationship("Locacion", back_populates="own_company")
    areas = relationship("Area", back_populates="own_company")
    categorias = relationship("Categoria", back_populates="own_company")
    actividades = relationship("Actividad", back_populates="own_company")
    listas_actividades = relationship("ListaActividad", back_populates="own_company")
    feedbacks_qr = relationship("FeedbackQR", back_populates="own_company")
    feedbacks = relationship("Feedback", back_populates="own_company")
    cliente_empresas = relationship("ClienteEmpresa", back_populates="company")
    ai_settings = relationship("CompanyAISettings", back_populates="company", uselist=False, cascade="all, delete-orphan")
    ai_usage_monthly = relationship("CompanyAIUsageMonthly", back_populates="company", cascade="all, delete-orphan")
    ai_reports = relationship("AIReport", back_populates="company", cascade="all, delete-orphan")
    ai_report_runs = relationship("AIReportRun", back_populates="company", cascade="all, delete-orphan")

class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre = Column(Text, nullable=False)
    email = Column(Text, nullable=False, unique=True)
    contrasena = Column(Text, nullable=False)
    rol = Column(Text, nullable=False)
    numero = Column(Text)
    direccion = Column(Text)
    foto = Column(Text)
    identificacion = Column(Text)
    creado_en = Column(TIMESTAMP)
    creado_por = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
    area_id = Column(UUID(as_uuid=True), ForeignKey("areas.id"), nullable=True)
    supervisor_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True)

    empresas = relationship("Empresa", back_populates="creador")
    locaciones_creadas = relationship(
        "Locacion",
        back_populates="usuario",
        foreign_keys="Locacion.usuario_id",
    )
    categorias = relationship("Categoria", back_populates="creador")
    actividades = relationship("Actividad", back_populates="creador")
    listas_actividades = relationship("ListaActividad", back_populates="creador")
    feedbacks_qr = relationship("FeedbackQR", back_populates="usuario")
    feedbacks = relationship("Feedback", back_populates="usuario")
    empresas_cliente = relationship(
        "ClienteEmpresa",
        back_populates="usuario",
        foreign_keys="ClienteEmpresa.usuario_id",
        cascade="all, delete-orphan"
    )
    cliente_empresas_creadas = relationship(
        "ClienteEmpresa",
        back_populates="creador_asignacion",
        foreign_keys="ClienteEmpresa.creado_por"
    )
    supervisor = relationship("Usuario", remote_side=[id], backref="subordinados", foreign_keys=[supervisor_id])
    creador = relationship("Usuario", remote_side=[id], backref="usuarios_creados", foreign_keys=[creado_por])
    own_company = relationship("Company", back_populates="usuarios", foreign_keys=[company_id])
    area = relationship("Area", back_populates="usuarios", foreign_keys=[area_id])
    ai_reports_requested = relationship("AIReport", back_populates="requester", foreign_keys="AIReport.requested_by")

class Empresa(Base):
    __tablename__ = "empresas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    nombre = Column(String, nullable=False)
    imagen = Column(String)
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
    creado_en = Column(DateTime, default=datetime.utcnow)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True)

    own_company = relationship("Company", back_populates="empresas", foreign_keys=[company_id])
    creador = relationship("Usuario", back_populates="empresas")
    locaciones = relationship("Locacion", back_populates="empresa", cascade="all, delete")
    clientes_asignados = relationship(
        "ClienteEmpresa",
        back_populates="empresa",
        cascade="all, delete-orphan"
    )

class ClienteEmpresa(Base):
    __tablename__ = "cliente_empresas"
    __table_args__ = (
        UniqueConstraint("usuario_id", "empresa_id", name="uq_cliente_empresas_usuario_empresa"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    empresa_id = Column(UUID(as_uuid=True), ForeignKey("empresas.id"), nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    creado_en = Column(DateTime, default=datetime.utcnow, nullable=False)
    creado_por = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)

    usuario = relationship("Usuario", back_populates="empresas_cliente", foreign_keys=[usuario_id])
    empresa = relationship("Empresa", back_populates="clientes_asignados", foreign_keys=[empresa_id])
    company = relationship("Company", back_populates="cliente_empresas", foreign_keys=[company_id])
    creador_asignacion = relationship("Usuario", back_populates="cliente_empresas_creadas", foreign_keys=[creado_por])

class Locacion(Base):
    __tablename__ = "locaciones"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre = Column(Text, nullable=False)
    empresa_id = Column(UUID(as_uuid=True), ForeignKey("empresas.id"))
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
    supervisor_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)
    creado_en = Column(TIMESTAMP, default=datetime.utcnow)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True)
    direccion = Column(Text)
    latitud = Column(Numeric(9, 6))
    longitud = Column(Numeric(9, 6))
    radio_verificacion_metros = Column(Integer, nullable=True, default=1000)

    own_company = relationship("Company", back_populates="locaciones", foreign_keys=[company_id])
    empresa = relationship("Empresa", back_populates="locaciones")
    usuario = relationship(
        "Usuario",
        back_populates="locaciones_creadas",
        foreign_keys=[usuario_id],
    )
    supervisor = relationship("Usuario", foreign_keys=[supervisor_id])
    areas = relationship("Area", back_populates="locacion", cascade="all, delete")

class Area(Base):
    __tablename__ = "areas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre = Column(String, nullable=False)
    locacion_id = Column(UUID(as_uuid=True), ForeignKey("locaciones.id"), nullable=False)
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    creado_en = Column(DateTime, default=datetime.utcnow)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True)
    usuarios = relationship("Usuario", back_populates="area", foreign_keys=[Usuario.area_id])

    # Relaciones
    own_company = relationship("Company", back_populates="areas", foreign_keys=[company_id])
    locacion = relationship("Locacion", back_populates="areas")

class Categoria(Base):
    __tablename__ = "categorias"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre = Column(String, nullable=False)
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
    creado_en = Column(DateTime, default=datetime.utcnow)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True)

    own_company = relationship("Company", back_populates="categorias", foreign_keys=[company_id])
    creador = relationship("Usuario", back_populates="categorias")
    actividades = relationship("Actividad", back_populates="categoria", cascade="all, delete")

# Tabla intermedia para relación muchos a muchos entre listas y actividades
lista_actividad_actividades = Table(
    "lista_actividad_actividades",
    Base.metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("lista_id", UUID(as_uuid=True), ForeignKey("listas_actividades.id", ondelete="CASCADE")),
    Column("actividad_id", UUID(as_uuid=True), ForeignKey("actividades.id", ondelete="CASCADE")),
)

class Actividad(Base):
    __tablename__ = "actividades"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre = Column(String, nullable=False)
    categoria_id = Column(UUID(as_uuid=True), ForeignKey("categorias.id", ondelete="CASCADE"), nullable=False)
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
    creado_en = Column(DateTime, default=datetime.utcnow)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True)

    own_company = relationship("Company", back_populates="actividades", foreign_keys=[company_id])
    categoria = relationship("Categoria", back_populates="actividades")
    creador = relationship("Usuario", back_populates="actividades")
    listas = relationship(
        "ListaActividad",
        secondary=lista_actividad_actividades,
        back_populates="actividades"
    )

class ListaActividad(Base):
    __tablename__ = "listas_actividades"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre = Column(Text, nullable=False)
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
    creado_en = Column(DateTime, default=datetime.utcnow)
    qrin = Column(Text, nullable=True)
    qrout = Column(Text, nullable=True)
    code = Column(Text, nullable=True)
    codeout = Column(Text, nullable=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True)
    imagen = Column(Boolean, nullable=True)

    own_company = relationship("Company", back_populates="listas_actividades", foreign_keys=[company_id])
    creador = relationship("Usuario", back_populates="listas_actividades")
    actividades = relationship(
        "Actividad",
        secondary=lista_actividad_actividades,
        back_populates="listas"
    )
    historial = relationship("ActividadUsuario", back_populates="lista", cascade="all, delete")

class ActividadUsuario(Base):
    __tablename__ = "historial_listas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lista_id = Column(UUID(as_uuid=True), ForeignKey("listas_actividades.id"), nullable=True)
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)
    supervisor_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)
    hora_inicio = Column(DateTime, nullable=False, default=datetime.utcnow)
    hora_fin = Column(DateTime, nullable=True)
    creado_en = Column(DateTime, default=datetime.utcnow)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True)
    finalizada = Column(Boolean, nullable=True)
    comentario = Column(String, nullable=True)
    imagen = Column(Text, nullable=True)
    evidencia_obligatoria = Column(Boolean, nullable=True)
    evidencia_entregada = Column(Boolean, nullable=True)
    evidencia_subida_en = Column(DateTime, nullable=True)
    evidencia_usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)
    evidencia_tipo = Column(String, nullable=True)
    evidencia_nombre_archivo = Column(String, nullable=True)
    latitud_inicio = Column(Numeric(9, 6), nullable=True)
    longitud_inicio = Column(Numeric(9, 6), nullable=True)
    precision_inicio = Column(Numeric(10, 2), nullable=True)
    distancia_validacion = Column(Numeric(10, 2), nullable=True)
    metodo_inicio = Column(String, nullable=True)
    latitud_fin = Column(Numeric(9, 6), nullable=True)
    longitud_fin = Column(Numeric(9, 6), nullable=True)
    precision_fin = Column(Numeric(10, 2), nullable=True)
    distancia_fin = Column(Numeric(10, 2), nullable=True)
    metodo_fin = Column(String, nullable=True)
    duracion_segundos = Column(Integer, nullable=True)
    estado_verificacion = Column(String, nullable=True, default="iniciada")

    usuario = relationship("Usuario", foreign_keys=[usuario_id])
    supervisor = relationship("Usuario", foreign_keys=[supervisor_id])
    evidencia_usuario = relationship("Usuario", foreign_keys=[evidencia_usuario_id])
    lista = relationship("ListaActividad", back_populates="historial")
    company = relationship("Company")

# FeedbackQR model
class FeedbackQR(Base):
    __tablename__ = "feedback_qr"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url = Column(Text, nullable=False)
    nombre = Column(Text, nullable=False)
    direccion = Column(Text, nullable=False)
    empresa_id = Column(UUID(as_uuid=True), ForeignKey("empresas.id"), nullable=True)
    locacion_id = Column(UUID(as_uuid=True), ForeignKey("locaciones.id"), nullable=True)
    area_id = Column(UUID(as_uuid=True), ForeignKey("areas.id"), nullable=True)
    contexto = Column(Text, nullable=True)
    creado_en = Column(DateTime, default=datetime.utcnow)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True)
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)

    # Relaciones
    own_company = relationship("Company", back_populates="feedbacks_qr", foreign_keys=[company_id])
    usuario = relationship("Usuario", back_populates="feedbacks_qr", foreign_keys=[usuario_id])
    empresa_rel = relationship("Empresa", foreign_keys=[empresa_id])
    locacion = relationship("Locacion", foreign_keys=[locacion_id])
    area = relationship("Area", foreign_keys=[area_id])

class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre = Column(Text, nullable=True)
    empresa = Column(Text, nullable=False)
    direccion = Column(Text, nullable=False)
    empresa_id = Column(UUID(as_uuid=True), ForeignKey("empresas.id"), nullable=True)
    locacion_id = Column(UUID(as_uuid=True), ForeignKey("locaciones.id"), nullable=True)
    area_id = Column(UUID(as_uuid=True), ForeignKey("areas.id"), nullable=True)
    contexto = Column(Text, nullable=True)
    calificacion = Column(Numeric(2, 1), nullable=False)
    comentario = Column(Text, nullable=True)
    foto = Column(Text, nullable=True)
    creado_en = Column(DateTime, default=datetime.utcnow)

    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True)
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)

    own_company = relationship("Company", back_populates="feedbacks", foreign_keys=[company_id])
    usuario = relationship("Usuario", back_populates="feedbacks", foreign_keys=[usuario_id])
    empresa_rel = relationship("Empresa", foreign_keys=[empresa_id])
    locacion = relationship("Locacion", foreign_keys=[locacion_id])
    area = relationship("Area", foreign_keys=[area_id])


class Incidente(Base):
    __tablename__ = "incidentes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tipo = Column(Text, nullable=False)
    prioridad = Column(Text, nullable=False, default="media")
    descripcion = Column(Text, nullable=False)
    estado = Column(Text, nullable=False, default="abierto")
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    empresa_id = Column(UUID(as_uuid=True), ForeignKey("empresas.id"), nullable=True)
    locacion_id = Column(UUID(as_uuid=True), ForeignKey("locaciones.id"), nullable=True)
    area_id = Column(UUID(as_uuid=True), ForeignKey("areas.id"), nullable=True)
    empleado_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)
    supervisor_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)
    asignado_a_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)
    actividad_usuario_id = Column(UUID(as_uuid=True), ForeignKey("historial_listas.id"), nullable=True)
    feedback_id = Column(UUID(as_uuid=True), ForeignKey("feedback.id"), nullable=True)
    evidencia_inicial = Column(Text, nullable=True)
    evidencia_resolucion = Column(Text, nullable=True)
    foto_resolucion = Column(Text, nullable=True)
    creado_en = Column(DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = Column(DateTime, default=datetime.utcnow, nullable=False)
    ultimo_evento_en = Column(DateTime, nullable=True)
    resuelto_en = Column(DateTime, nullable=True)
    cerrado_en = Column(DateTime, nullable=True)
    creado_por = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)

    company = relationship("Company", foreign_keys=[company_id])
    empresa = relationship("Empresa", foreign_keys=[empresa_id])
    locacion = relationship("Locacion", foreign_keys=[locacion_id])
    area = relationship("Area", foreign_keys=[area_id])
    empleado = relationship("Usuario", foreign_keys=[empleado_id])
    supervisor = relationship("Usuario", foreign_keys=[supervisor_id])
    asignado_a = relationship("Usuario", foreign_keys=[asignado_a_id])
    actividad_usuario = relationship("ActividadUsuario", foreign_keys=[actividad_usuario_id])
    feedback = relationship("Feedback", foreign_keys=[feedback_id])
    creador = relationship("Usuario", foreign_keys=[creado_por])
    eventos = relationship("IncidenteEvento", back_populates="incidente", cascade="all, delete-orphan")


class IncidenteEvento(Base):
    __tablename__ = "incidente_eventos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incidente_id = Column(UUID(as_uuid=True), ForeignKey("incidentes.id", ondelete="CASCADE"), nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    tipo_evento = Column(Text, nullable=False)
    actor_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)
    actor_rol = Column(Text, nullable=True)
    mensaje = Column(Text, nullable=True)
    foto_url = Column(Text, nullable=True)
    foto_public_id = Column(Text, nullable=True)
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)
    creado_en = Column(DateTime, default=datetime.utcnow, nullable=False)

    incidente = relationship("Incidente", back_populates="eventos", foreign_keys=[incidente_id])
    actor = relationship("Usuario", foreign_keys=[actor_id])
    company = relationship("Company", foreign_keys=[company_id])


class Notificacion(Base):
    __tablename__ = "notificaciones"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    actor_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    tipo = Column(Text, nullable=False)
    categoria = Column(Text, nullable=False)
    evento = Column(Text, nullable=False)
    severity = Column(Text, nullable=False, default="info")
    titulo = Column(Text, nullable=False)
    mensaje = Column(Text, nullable=False)
    source_type = Column(Text, nullable=True)
    source_id = Column(UUID(as_uuid=True), nullable=True)
    source_event_id = Column(UUID(as_uuid=True), nullable=True)
    deep_link = Column(Text, nullable=True)
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)
    dedupe_key = Column(Text, nullable=True)
    creado_en = Column(DateTime, default=utc_now_naive, nullable=False)

    company = relationship("Company", foreign_keys=[company_id])
    actor = relationship("Usuario", foreign_keys=[actor_id])
    destinatarios = relationship(
        "NotificacionDestinatario",
        back_populates="notificacion",
        cascade="all, delete-orphan",
    )


class NotificacionDestinatario(Base):
    __tablename__ = "notificacion_destinatarios"
    __table_args__ = (
        UniqueConstraint("notification_id", "user_id", name="uq_notificacion_destinatario"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    notification_id = Column(UUID(as_uuid=True), ForeignKey("notificaciones.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    read_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, default=utc_now_naive, nullable=False)
    hidden_at = Column(DateTime, nullable=True)
    creado_en = Column(DateTime, default=utc_now_naive, nullable=False)

    notificacion = relationship("Notificacion", back_populates="destinatarios", foreign_keys=[notification_id])
    usuario = relationship("Usuario", foreign_keys=[user_id])
    company = relationship("Company", foreign_keys=[company_id])


class CompanyAISettings(Base):
    __tablename__ = "company_ai_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, unique=True)
    ai_enabled = Column(Boolean, nullable=False, default=False)
    plan_name = Column(Text, nullable=True)
    reports_monthly_limit = Column(Integer, nullable=False, default=0)
    monthly_token_limit = Column(Integer, nullable=False, default=0)
    monthly_cost_limit_usd = Column(Numeric(12, 6), nullable=False, default=0)
    reset_day = Column(Integer, nullable=False, default=1)
    hard_block_on_limit = Column(Boolean, nullable=False, default=True)
    dedupe_window_hours = Column(Integer, nullable=False, default=24)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False)
    updated_at = Column(DateTime, default=utc_now_naive, nullable=False)

    company = relationship("Company", back_populates="ai_settings", foreign_keys=[company_id])


class CompanyAIUsageMonthly(Base):
    __tablename__ = "company_ai_usage_monthly"
    __table_args__ = (
        UniqueConstraint("company_id", "usage_year", "usage_month", name="uq_company_ai_usage_monthly_company_period"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    usage_year = Column(Integer, nullable=False)
    usage_month = Column(Integer, nullable=False)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    reports_generated_count = Column(Integer, nullable=False, default=0)
    prompt_tokens = Column(Integer, nullable=False, default=0)
    completion_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    total_cost_usd = Column(Numeric(12, 6), nullable=False, default=0)
    last_report_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False)
    updated_at = Column(DateTime, default=utc_now_naive, nullable=False)

    company = relationship("Company", back_populates="ai_usage_monthly", foreign_keys=[company_id])


class AIReport(Base):
    __tablename__ = "ai_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    scope_type = Column(Text, nullable=False)
    scope_entity_id = Column(UUID(as_uuid=True), nullable=True)
    period_type = Column(Text, nullable=False)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    status = Column(Text, nullable=False, default="queued")
    prompt_template_key = Column(Text, nullable=False)
    prompt_template_version = Column(Text, nullable=False)
    provider = Column(Text, nullable=False)
    model = Column(Text, nullable=False)
    requested_by = Column(UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False)
    request_fingerprint = Column(Text, nullable=True)
    report_json = Column(JSONB, nullable=True)
    facts_json = Column(JSONB, nullable=True)
    citations_json = Column(JSONB, nullable=True)
    langfuse_trace_id = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    generation_block_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False)
    updated_at = Column(DateTime, default=utc_now_naive, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)

    company = relationship("Company", back_populates="ai_reports", foreign_keys=[company_id])
    requester = relationship("Usuario", back_populates="ai_reports_requested", foreign_keys=[requested_by])
    runs = relationship("AIReportRun", back_populates="report", cascade="all, delete-orphan")


class AIReportRun(Base):
    __tablename__ = "ai_report_runs"
    __table_args__ = (
        UniqueConstraint("report_id", "run_number", name="uq_ai_report_runs_report_run"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(UUID(as_uuid=True), ForeignKey("ai_reports.id", ondelete="CASCADE"), nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    run_number = Column(Integer, nullable=False)
    status = Column(Text, nullable=False, default="queued")
    provider = Column(Text, nullable=False)
    model = Column(Text, nullable=False)
    prompt_template_key = Column(Text, nullable=False)
    prompt_template_version = Column(Text, nullable=False)
    input_facts_json = Column(JSONB, nullable=False, default=dict)
    output_json = Column(JSONB, nullable=True)
    raw_response_json = Column(JSONB, nullable=True)
    usage_prompt_tokens = Column(Integer, nullable=True)
    usage_completion_tokens = Column(Integer, nullable=True)
    usage_total_tokens = Column(Integer, nullable=True)
    estimated_cost_usd = Column(Numeric(12, 6), nullable=True)
    billing_counted = Column(Boolean, nullable=False, default=False)
    latency_ms = Column(Integer, nullable=True)
    langfuse_trace_id = Column(Text, nullable=True)
    langfuse_observation_id = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False)

    report = relationship("AIReport", back_populates="runs", foreign_keys=[report_id])
    company = relationship("Company", back_populates="ai_report_runs", foreign_keys=[company_id])

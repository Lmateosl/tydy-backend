from sqlalchemy import Column, String, Text, TIMESTAMP, ForeignKey, Numeric, Table, Boolean, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
import uuid
from .database import Base
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
    locaciones_creadas = relationship("Locacion", back_populates="creador")
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
    creado_en = Column(TIMESTAMP, default=datetime.utcnow)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True)
    direccion = Column(Text)
    latitud = Column(Numeric(9, 6))
    longitud = Column(Numeric(9, 6))
    radio_verificacion_metros = Column(Integer, nullable=True, default=1000)

    own_company = relationship("Company", back_populates="locaciones", foreign_keys=[company_id])
    empresa = relationship("Empresa", back_populates="locaciones")
    creador = relationship("Usuario", back_populates="locaciones_creadas")
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
    contexto = Column(Text, nullable=True)
    creado_en = Column(DateTime, default=datetime.utcnow)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True)
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)

    # Relaciones
    own_company = relationship("Company", back_populates="feedbacks_qr", foreign_keys=[company_id])
    usuario = relationship("Usuario", back_populates="feedbacks_qr", foreign_keys=[usuario_id])
    empresa_rel = relationship("Empresa", foreign_keys=[empresa_id])

class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre = Column(Text, nullable=True)
    empresa = Column(Text, nullable=False)
    direccion = Column(Text, nullable=False)
    empresa_id = Column(UUID(as_uuid=True), ForeignKey("empresas.id"), nullable=True)
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

from sqlalchemy import Column, String, Text, TIMESTAMP, ForeignKey, Numeric, Table, Boolean
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

    usuarios = relationship("Usuario", back_populates="own_company")
    empresas = relationship("Empresa", back_populates="own_company")
    locaciones = relationship("Locacion", back_populates="own_company")
    areas = relationship("Area", back_populates="own_company")
    categorias = relationship("Categoria", back_populates="own_company")
    actividades = relationship("Actividad", back_populates="own_company")
    listas_actividades = relationship("ListaActividad", back_populates="own_company")

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
    hora_inicio = Column(DateTime, nullable=False, default=datetime.utcnow)
    hora_fin = Column(DateTime, nullable=True)
    creado_en = Column(DateTime, default=datetime.utcnow)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True)
    finalizada = Column(Boolean, nullable=True)
    comentario = Column(String, nullable=True)
    imagen = Column(Text, nullable=True)

    usuario = relationship("Usuario")
    lista = relationship("ListaActividad", back_populates="historial")
    company = relationship("Company")
    
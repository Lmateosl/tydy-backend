from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# Cargar las variables de entorno
load_dotenv()

# Obtener la URL de conexión.
# En desarrollo usamos DATABASE_URL; si no existe, caemos a DATABASE_URL_PROD.
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("DATABASE_URL_PROD")

if not DATABASE_URL:
    raise RuntimeError("Debes definir DATABASE_URL o DATABASE_URL_PROD en el .env")

# Crear el motor
engine = create_engine(DATABASE_URL)

# Crear una sesión
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base para los modelos
Base = declarative_base()

# Función para obtener la sesión de la base de datos
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

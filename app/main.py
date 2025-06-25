from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware
from app.routers import usuarios, empresas, locaciones, areas, categorias, actividades, lista_actividades, historial
from app.auth import routes as auth_routes
from app.database import Base, engine
from app import models
from fastapi.staticfiles import StaticFiles
from app import config

# Crear las tablas en la base de datos
Base.metadata.create_all(bind=engine)

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["10/minute"]
)

app = FastAPI()

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Aquí puedes poner la URL de tu frontend en vez de "*"
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Montar carpeta de imágenes públicas
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Incluir rutas
app.include_router(auth_routes.router)
app.include_router(usuarios.router)
app.include_router(empresas.router)
app.include_router(locaciones.router)
app.include_router(areas.router)
app.include_router(categorias.router)
app.include_router(actividades.router)
app.include_router(lista_actividades.router)
app.include_router(historial.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

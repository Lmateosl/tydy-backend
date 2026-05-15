import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware
from app.routers import usuarios, empresas, locaciones, areas, categorias, actividades, lista_actividades, historial, dashboard, portal_cliente, incidentes, notificaciones, alertas_manuales
from app.auth import routes as auth_routes
from app.database import Base, SessionLocal, engine
from app import models
from fastapi.staticfiles import StaticFiles
from app import config
from app.services.incidentes_automaticos import (
    crear_incidentes_actividades_no_finalizadas,
    obtener_intervalo_job_actividad_no_finalizada_segundos,
)

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
app.include_router(dashboard.router)
app.include_router(portal_cliente.router)
app.include_router(incidentes.router)
app.include_router(notificaciones.router)
app.include_router(alertas_manuales.router)


async def _job_periodico_incidentes_actividades_no_finalizadas():
    intervalo_segundos = obtener_intervalo_job_actividad_no_finalizada_segundos()
    while True:
        db = SessionLocal()
        try:
            crear_incidentes_actividades_no_finalizadas(db)
        except Exception as exc:
            db.rollback()
            print("Error ejecutando job actividad_no_finalizada:", exc)
        finally:
            db.close()

        await asyncio.sleep(intervalo_segundos)


@app.on_event("startup")
async def iniciar_job_incidentes_actividades_no_finalizadas():
    app.state.job_incidentes_actividades_no_finalizadas = asyncio.create_task(
        _job_periodico_incidentes_actividades_no_finalizadas()
    )


@app.on_event("shutdown")
async def detener_job_incidentes_actividades_no_finalizadas():
    tarea = getattr(app.state, "job_incidentes_actividades_no_finalizadas", None)
    if tarea is not None:
        tarea.cancel()
        try:
            await tarea
        except asyncio.CancelledError:
            pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

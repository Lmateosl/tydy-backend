from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import usuarios, empresas, locaciones, areas, categorias, actividades, lista_actividades, historial
from app.auth import routes as auth_routes
from app.database import Base, engine
from app import models

# Crear las tablas en la base de datos
Base.metadata.create_all(bind=engine)

app = FastAPI()

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Aquí puedes poner la URL de tu frontend en vez de "*"
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# ⚙️ Tydy — Backend API

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?style=flat-square&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![JWT](https://img.shields.io/badge/Auth-JWT-black?style=flat-square)
![Swagger](https://img.shields.io/badge/API%20Docs-Swagger-85EA2D?style=flat-square&logo=swagger&logoColor=black)

Production-ready backend for **Tydy**, a QR-based task management and operational supervision platform designed for multi-location teams, role-based workflows, and auditable execution history.

**Product demo:** [https://tydy.pro](https://tydy.pro)  
**Frontend repository:** [https://github.com/Lmateosl/tydy-frontend](https://github.com/Lmateosl/tydy-frontend)  
**Access:** authorization required  
**API docs:** run locally and open `/docs`

## Overview

This backend powers the operational side of Tydy and is focused on reliability, operational visibility, and controlled multi-tenant access:

- Multi-tenant company data isolation
- JWT-based authentication
- Role-based access control
- QR-driven task list execution
- Activity history, evidence uploads, and exportable reports
- Feedback QR generation for external user flows

## Production Notes

- `https://tydy.pro` should be presented as the **product/frontend entry point** for the overall system.
- This repository does **not** document a separate public backend base URL.
- The production demo requires authorization/login, so it should be presented as a protected product demo rather than an open public API.

## Tech Stack

- **Python**
- **FastAPI**
- **SQLAlchemy**
- **PostgreSQL**
- **Pydantic**
- **Uvicorn**
- **JWT authentication**
- **Cloudinary** for image storage
- **FastAPI-Mail** (SMTP integration)
- **SlowAPI** for rate limiting

`Docker` is not included in this repository, so it was intentionally removed from the documented stack.

## Getting Started

This project can be run locally with `uvicorn`, and FastAPI exposes interactive API documentation through Swagger UI.

### Prerequisites

- Python 3.10+
- PostgreSQL database
- `pip`

### 1. Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file in the project root.

```env
DATABASE_URL_PROD=postgresql://user:password@localhost:5432/tydy
SECRET_KEY=your-jwt-secret

# JWT
JWT_ALGORITHM=HS256

# Mail
MAIL_USERNAME=your-user
MAIL_PASSWORD=your-password
MAIL_FROM=no-reply@example.com
MAIL_PORT=587
MAIL_SERVER=smtp.example.com
MAIL_STARTTLS=True
MAIL_SSL_TLS=False

# Cloudinary
CLOUDINARY_CLOUD_NAME=your-cloud-name
CLOUDINARY_API_KEY=your-api-key
CLOUDINARY_API_SECRET=your-api-secret

# Geocoding
LOCATIONIQ_API_KEY=your-locationiq-key

# Optional in deployment environments
PORT=8000
```

### 4. Database initialization

This project does **not** include Alembic or another migration system in the repository.

At startup, the app currently creates tables with SQLAlchemy:

```python
Base.metadata.create_all(bind=engine)
```

That means there is **no migration step to run** in the current codebase.

### 5. Run the application

The verified local command is:

```bash
uvicorn app.main:app --reload
```

Then open:

- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

## Authentication Flow

The API uses JWT bearer tokens for protected routes.

JWT tokens are short-lived and validated on every protected request.

1. The client sends credentials to `POST /auth/login`.
2. The backend validates the user and returns an `access_token`.
3. The client sends `Authorization: Bearer <token>` on protected requests.
4. The backend decodes the JWT, resolves the current user, and applies role-based authorization.

## Core Data Model

The current relational model is centered around these business entities:

- **Company**: top-level tenant that owns users, companies, locations, areas, categories, activities, lists, and feedback records.
- **Empresa**: operational business unit within a company tenant.
- **Location (`Locacion`)**: physical site associated with an `Empresa`.
- **Area**: operational zone inside a location.
- **Employee (`Usuario`)**: authenticated user with a role such as admin, supervisor, employee, or client.
- **Category (`Categoria`)**: grouping for activities.
- **Task (`Actividad`)**: atomic task definition.
- **Task List (`ListaActividad`)**: checklist composed of one or more activities, optionally with QR/code entry and exit flow.
- **Task Execution Log (`ActividadUsuario`)**: execution record with start/end timestamps, completion status, comment, and evidence image.
- **Feedback QR / Feedback**: records used for QR-triggered customer feedback flows.

## Role Permissions

Current permissions are enforced at the endpoint level.

- **Admin**
  Full CRUD on users, companies, locations, and areas. Can also create and manage execution records.
- **Supervisor**
  Can manage categories, activities, and task lists. Can also view company users.
- **Employee**
  Can execute and update task execution records, and use authenticated self-service endpoints such as profile/password-related flows.
- **Client**
  The role exists in the data model, but dedicated client-only API flows are not clearly exposed in the current router set.

## Project Structure

```text
app/
  auth/
    dependencies.py
    routes.py
    tokens.py
  routers/
    actividades.py
    areas.py
    categorias.py
    empresas.py
    historial.py
    lista_actividades.py
    locaciones.py
    usuarios.py
  config.py
  database.py
  main.py
  models.py
  schemas.py
  utils.py
uploads/
Procfile
requirements.txt
README.md
```

Notes:

- `routers/` contains most of the HTTP and business-flow logic today.
- `models.py` defines the SQLAlchemy models.
- `schemas.py` contains the Pydantic request/response schemas.
- `utils.py` contains password hashing and JWT helpers.
- There is **no `services/` directory yet** in the current repository.

## API Surface

These are real routes currently defined in the codebase:

### Auth

- `POST /auth/login`

### Users

- `GET /usuarios/perfil`
- `GET /usuarios/mi-compania`
- `GET /usuarios/`
- `GET /usuarios/{usuario_id}`
- `POST /usuarios/`
- `PUT /usuarios/{usuario_id}`
- `PUT /usuarios/{usuario_id}/cambiar-contrasena`
- `DELETE /usuarios/{usuario_id}`

### Companies, Locations, and Areas

- `GET /empresas/`
- `POST /empresas/`
- `GET /locaciones/`
- `POST /locaciones/`
- `GET /locaciones/coordenadas/`
- `GET /areas/`
- `GET /areas/resumen-totales`
- `POST /areas/`

### Categories, Activities, and Task Lists

- `GET /categorias/`
- `POST /categorias/`
- `GET /categorias/categoria/{categoria_id}/actividades`
- `GET /actividades/`
- `POST /actividades/`
- `GET /listas_actividades/`
- `POST /listas_actividades/`
- `GET /listas_actividades/por_codigo/{code}`
- `GET /listas_actividades/por_codigoout/{codeout}`

### Execution History and Reporting

- `POST /actividades-usuario/`
- `GET /actividades-usuario/`
- `GET /actividades-usuario/exportar`
- `PUT /actividades-usuario/{actividad_id}/finalizar`

### Feedback

- `POST /listas_actividades/feedback/list`
- `GET /listas_actividades/feedback`
- `POST /listas_actividades/feedback-user`
- `GET /listas_actividades/feedback-user`

## Error Handling and Validation

Validation and error handling currently rely on a straightforward FastAPI + Pydantic approach:

- **Pydantic schemas** for request and response contracts
- **FastAPI validation** for typed parameters, forms, files, and query inputs
- **HTTPException** for business-rule failures such as unauthorized access, duplicates, or missing resources
- **Structured status codes** like `400`, `401`, `403`, and `404`

Examples from the codebase include:

- duplicate category or company validation
- invalid image type validation
- location latitude/longitude range validation
- JWT token validation for protected routes
- company-scoped resource checks for multi-tenant isolation

## Architecture Flow

```mermaid
flowchart LR
    A["Frontend / Product Demo<br/>https://tydy.pro"] --> B["FastAPI Backend"]
    B --> C["JWT Auth"]
    B --> D["PostgreSQL"]
    B --> E["Cloudinary"]
    B --> F["Mail Service"]
    A --> G["QR Scan / Task Flow"]
    G --> B
    B --> H["Reports / Export / History"]
```

## Current Status

- MVP backend is running with authenticated operational flows.
- Swagger/OpenAPI documentation is available through FastAPI at `/docs`.
- QR-based task list execution is implemented end-to-end.
- Reporting and export flows already exist for activity history.
- Media upload and notification integrations are already connected.

## Roadmap

- Advanced analytics & reporting
- Expand role-specific permissions and client flows
- Refactor business logic into a dedicated `services/` layer
- Introduce formal database migrations
- Performance optimization & scaling strategy

## Author

**Luis Mateo Sánchez Loaiza**

Senior Frontend Engineer | Full-Stack Builder  
React | Angular | Backend APIs | AI Systems

## Notes

- Local development entrypoint: `uvicorn app.main:app --reload`
- Deployment `Procfile` also points to `app.main:app`
- The database env var used by the current code is `DATABASE_URL_PROD`
- `JWT_ALGORITHM` is documented here for clarity, but the current implementation hardcodes `HS256` in the codebase

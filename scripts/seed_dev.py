import argparse
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database import Base, SessionLocal, engine
from app.models import Company, Usuario
from app.utils import hash_password


DEFAULT_COMPANY_EMAIL = "dev@tydy.local"
DEFAULT_ADMIN_EMAIL = "admin@tydy.local"


def seed_dev(admin_password: str):
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.email == DEFAULT_COMPANY_EMAIL).first()
        if not company:
            company = Company(
                nombre="TYDY Dev Company",
                ruc="DEV-LOCAL",
                direccion="Local development",
                telefono="0000000000",
                email=DEFAULT_COMPANY_EMAIL,
                logo=None,
            )
            db.add(company)
            db.flush()

        admin = db.query(Usuario).filter(Usuario.email == DEFAULT_ADMIN_EMAIL).first()
        if not admin:
            admin = Usuario(
                nombre="Admin Dev",
                email=DEFAULT_ADMIN_EMAIL,
                contrasena=hash_password(admin_password),
                rol="admin",
                numero="0000000000",
                direccion="Local development",
                identificacion="DEV-ADMIN",
                creado_en=datetime.utcnow(),
                company_id=company.id,
            )
            db.add(admin)
        else:
            admin.nombre = "Admin Dev"
            admin.contrasena = hash_password(admin_password)
            admin.rol = "admin"
            admin.company_id = company.id
            admin.identificacion = admin.identificacion or "DEV-ADMIN"

        db.commit()

        print("Seed local listo.")
        print(f"Company: {company.nombre} ({company.email})")
        print(f"Admin email: {DEFAULT_ADMIN_EMAIL}")
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Seed local data for TYDY development.")
    parser.add_argument("--password", required=True, help="Password for admin@tydy.local")
    args = parser.parse_args()
    seed_dev(args.password)


if __name__ == "__main__":
    main()

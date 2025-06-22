from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm
from app.database import get_db
from app.models import Usuario
from app.utils import verify_password
from app.auth.tokens import crear_token
from .. import schemas

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.email == form_data.username).first()
    if not usuario or not verify_password(form_data.password, usuario.contrasena):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    token_data = {"sub": str(usuario.id), "rol": usuario.rol}
    token = crear_token(token_data)
    return {"access_token": token, "token_type": "bearer"}
from fastapi import APIRouter, Depends, HTTPException, Security
from sqlalchemy.orm import Session

from .. import schemas
from ..auth.dependencies import get_current_user
from ..database import get_db
from ..models import Usuario
from ..services.notificaciones_service import crear_alerta_manual


router = APIRouter(prefix="/alertas-manuales", tags=["Alertas Manuales"])


def _validar_permisos(current_user: Usuario, audiencia_tipo: str):
    rol = (current_user.rol or "").lower()

    if rol == "admin":
        return

    if rol == "supervisor":
        if audiencia_tipo not in {"locacion", "user"}:
            raise HTTPException(
                status_code=403,
                detail="No tienes permisos para enviar alertas a esa audiencia",
            )
        return

    raise HTTPException(status_code=403, detail="No tienes permisos")


@router.post("/", response_model=schemas.AlertaManualCreateResponse)
def enviar_alerta_manual(
    payload: schemas.AlertaManualCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    _validar_permisos(current_user, payload.audiencia_tipo)

    notificacion, total_destinatarios = crear_alerta_manual(
        db,
        payload=payload,
        current_user=current_user,
    )
    db.commit()

    return schemas.AlertaManualCreateResponse(
        detail="Alerta enviada",
        notification_id=notificacion.id,
        destinatarios=total_destinatarios,
    )

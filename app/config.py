from fastapi_mail import ConnectionConfig
from pydantic import BaseModel, EmailStr

conf = ConnectionConfig(
    MAIL_USERNAME="mateofff97@gmail.com",
    MAIL_PASSWORD="Supermateo@luis12",
    MAIL_FROM="mateofff97@gmail.com",
    MAIL_SERVER="smtp.gmail.com",
    MAIL_FROM_NAME="Sistema de Actividades",
    MAIL_STARTTLS = True,
    MAIL_SSL_TLS = False,
    MAIL_PORT = 587,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True
)
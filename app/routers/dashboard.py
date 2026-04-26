from datetime import datetime, time, timedelta

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth.dependencies import get_current_user
from ..database import get_db
from ..models import Usuario


router = APIRouter(prefix="/dashboard/operativo", tags=["Dashboard"])


def _rango_hoy_utc():
    inicio = datetime.combine(datetime.utcnow().date(), time.min)
    fin = inicio + timedelta(days=1)
    return inicio, fin


def _aplicar_filtro_fecha(query, columna, desde: Optional[datetime], hasta: Optional[datetime]):
    if desde:
        query = query.filter(columna >= desde)
    if hasta:
        query = query.filter(columna <= hasta)
    return query


def _validar_permisos_dashboard(current_user: Usuario):
    if current_user.rol.lower() not in ["admin", "supervisor"]:
        raise HTTPException(status_code=403, detail="No tienes permisos")


@router.get("/resumen")
def obtener_resumen_operativo(
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    _validar_permisos_dashboard(current_user)

    inicio_hoy, fin_hoy = _rango_hoy_utc()
    company_id = current_user.company_id

    actividades_hoy = db.query(func.count(models.ActividadUsuario.id)).filter(
        models.ActividadUsuario.company_id == company_id,
        models.ActividadUsuario.hora_inicio >= inicio_hoy,
        models.ActividadUsuario.hora_inicio < fin_hoy,
    ).scalar() or 0

    actividades_completadas_hoy = db.query(func.count(models.ActividadUsuario.id)).filter(
        models.ActividadUsuario.company_id == company_id,
        models.ActividadUsuario.hora_inicio >= inicio_hoy,
        models.ActividadUsuario.hora_inicio < fin_hoy,
        models.ActividadUsuario.finalizada.is_(True),
    ).scalar() or 0

    actividades_pendientes_hoy = db.query(func.count(models.ActividadUsuario.id)).filter(
        models.ActividadUsuario.company_id == company_id,
        models.ActividadUsuario.hora_inicio >= inicio_hoy,
        models.ActividadUsuario.hora_inicio < fin_hoy,
        or_(
            models.ActividadUsuario.finalizada.is_(False),
            models.ActividadUsuario.finalizada.is_(None),
        ),
    ).scalar() or 0

    actividades_vencidas = db.query(func.count(models.ActividadUsuario.id)).filter(
        models.ActividadUsuario.company_id == company_id,
        models.ActividadUsuario.hora_inicio < inicio_hoy,
        or_(
            models.ActividadUsuario.finalizada.is_(False),
            models.ActividadUsuario.finalizada.is_(None),
        ),
    ).scalar() or 0

    empleados_activos_hoy = db.query(func.count(func.distinct(models.ActividadUsuario.usuario_id))).filter(
        models.ActividadUsuario.company_id == company_id,
        models.ActividadUsuario.hora_inicio >= inicio_hoy,
        models.ActividadUsuario.hora_inicio < fin_hoy,
        models.ActividadUsuario.usuario_id.isnot(None),
    ).scalar() or 0

    locaciones_con_actividad_hoy = (
        db.query(func.count(func.distinct(models.Area.locacion_id)))
        .select_from(models.ActividadUsuario)
        .join(models.Usuario, models.ActividadUsuario.usuario_id == models.Usuario.id)
        .join(models.Area, models.Usuario.area_id == models.Area.id)
        .filter(
            models.ActividadUsuario.company_id == company_id,
            models.ActividadUsuario.hora_inicio >= inicio_hoy,
            models.ActividadUsuario.hora_inicio < fin_hoy,
            models.Area.locacion_id.isnot(None),
        )
        .scalar()
        or 0
    )

    evidencias_faltantes = db.query(func.count(models.ActividadUsuario.id)).filter(
        models.ActividadUsuario.company_id == company_id,
        models.ActividadUsuario.evidencia_obligatoria.is_(True),
        or_(
            models.ActividadUsuario.evidencia_entregada.is_(False),
            models.ActividadUsuario.evidencia_entregada.is_(None),
        ),
    ).scalar() or 0

    feedbacks_negativos = db.query(func.count(models.Feedback.id)).filter(
        models.Feedback.company_id == company_id,
        models.Feedback.calificacion < 3,
    ).scalar() or 0

    incidentes_historial = db.query(func.count(models.ActividadUsuario.id)).filter(
        models.ActividadUsuario.company_id == company_id,
        models.ActividadUsuario.comentario.isnot(None),
        func.length(func.trim(models.ActividadUsuario.comentario)) > 0,
    ).scalar() or 0

    incidentes_abiertos = incidentes_historial + feedbacks_negativos

    return {
        "actividades_hoy": actividades_hoy,
        "actividades_completadas_hoy": actividades_completadas_hoy,
        "actividades_pendientes_hoy": actividades_pendientes_hoy,
        "actividades_vencidas": actividades_vencidas,
        "empleados_activos_hoy": empleados_activos_hoy,
        "locaciones_con_actividad_hoy": locaciones_con_actividad_hoy,
        "evidencias_faltantes": evidencias_faltantes,
        "feedbacks_negativos": feedbacks_negativos,
        "incidentes_abiertos": incidentes_abiertos,
    }


@router.get("/riesgos", response_model=schemas.DashboardRiesgosResponse)
def obtener_riesgos_operativos(
    desde: Optional[datetime] = Query(None),
    hasta: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    _validar_permisos_dashboard(current_user)

    company_id = current_user.company_id

    locaciones_query = (
        db.query(
            models.Locacion.id.label("locacion_id"),
            models.Locacion.nombre.label("locacion_nombre"),
            models.Empresa.nombre.label("empresa_nombre"),
            func.count(models.ActividadUsuario.id).label("total_problemas"),
            func.sum(
                case(
                    (
                        func.lower(func.coalesce(models.ActividadUsuario.estado_verificacion, ""))
                        != "verificada",
                        1,
                    ),
                    else_=0,
                )
            ).label("actividades_no_verificadas"),
            func.sum(
                case(
                    (
                        or_(
                            models.ActividadUsuario.evidencia_entregada.is_(False),
                            models.ActividadUsuario.evidencia_entregada.is_(None),
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("evidencias_faltantes"),
        )
        .select_from(models.ActividadUsuario)
        .join(models.Usuario, models.ActividadUsuario.usuario_id == models.Usuario.id)
        .join(models.Area, models.Usuario.area_id == models.Area.id, isouter=True)
        .join(models.Locacion, models.Area.locacion_id == models.Locacion.id, isouter=True)
        .join(models.Empresa, models.Locacion.empresa_id == models.Empresa.id, isouter=True)
        .filter(
            models.ActividadUsuario.company_id == company_id,
            or_(
                func.lower(func.coalesce(models.ActividadUsuario.estado_verificacion, "")) != "verificada",
                or_(
                    models.ActividadUsuario.evidencia_entregada.is_(False),
                    models.ActividadUsuario.evidencia_entregada.is_(None),
                ),
            ),
        )
    )
    locaciones_query = _aplicar_filtro_fecha(
        locaciones_query,
        models.ActividadUsuario.hora_inicio,
        desde,
        hasta,
    )
    locaciones_con_problemas = [
        {
            "locacion_id": fila.locacion_id,
            "locacion_nombre": fila.locacion_nombre or "Sin locación",
            "empresa_nombre": fila.empresa_nombre,
            "total_problemas": int(fila.total_problemas or 0),
            "actividades_no_verificadas": int(fila.actividades_no_verificadas or 0),
            "evidencias_faltantes": int(fila.evidencias_faltantes or 0),
        }
        for fila in locaciones_query.group_by(
            models.Locacion.id,
            models.Locacion.nombre,
            models.Empresa.nombre,
        ).order_by(
            func.count(models.ActividadUsuario.id).desc(),
            models.Locacion.nombre.asc(),
        ).all()
    ]

    empleados_query = (
        db.query(
            models.Usuario.id.label("usuario_id"),
            models.Usuario.nombre.label("nombre"),
            models.Usuario.identificacion.label("identificacion"),
            models.Area.nombre.label("area_nombre"),
            models.Locacion.nombre.label("locacion_nombre"),
            func.count(models.ActividadUsuario.id).label("total_pendientes"),
        )
        .select_from(models.ActividadUsuario)
        .join(models.Usuario, models.ActividadUsuario.usuario_id == models.Usuario.id)
        .join(models.Area, models.Usuario.area_id == models.Area.id, isouter=True)
        .join(models.Locacion, models.Area.locacion_id == models.Locacion.id, isouter=True)
        .filter(
            models.ActividadUsuario.company_id == company_id,
            or_(
                models.ActividadUsuario.finalizada.is_(False),
                models.ActividadUsuario.finalizada.is_(None),
            ),
        )
    )
    empleados_query = _aplicar_filtro_fecha(
        empleados_query,
        models.ActividadUsuario.hora_inicio,
        desde,
        hasta,
    )
    empleados_con_pendientes = [
        {
            "usuario_id": fila.usuario_id,
            "nombre": fila.nombre or "Sin usuario",
            "identificacion": fila.identificacion,
            "area_nombre": fila.area_nombre,
            "locacion_nombre": fila.locacion_nombre,
            "total_pendientes": int(fila.total_pendientes or 0),
        }
        for fila in empleados_query.group_by(
            models.Usuario.id,
            models.Usuario.nombre,
            models.Usuario.identificacion,
            models.Area.nombre,
            models.Locacion.nombre,
        ).order_by(
            func.count(models.ActividadUsuario.id).desc(),
            models.Usuario.nombre.asc(),
        ).all()
    ]

    comentarios_query = (
        db.query(models.ActividadUsuario, models.Usuario, models.Area, models.Locacion, models.Empresa)
        .select_from(models.ActividadUsuario)
        .join(models.Usuario, models.ActividadUsuario.usuario_id == models.Usuario.id, isouter=True)
        .join(models.Area, models.Usuario.area_id == models.Area.id, isouter=True)
        .join(models.Locacion, models.Area.locacion_id == models.Locacion.id, isouter=True)
        .join(models.Empresa, models.Locacion.empresa_id == models.Empresa.id, isouter=True)
        .filter(
            models.ActividadUsuario.company_id == company_id,
            models.ActividadUsuario.comentario.isnot(None),
            func.length(func.trim(models.ActividadUsuario.comentario)) > 0,
        )
    )
    comentarios_query = _aplicar_filtro_fecha(
        comentarios_query,
        func.coalesce(models.ActividadUsuario.hora_fin, models.ActividadUsuario.hora_inicio),
        desde,
        hasta,
    )
    comentarios_recientes = [
        {
            "actividad_id": actividad.id,
            "comentario": actividad.comentario,
            "hora_inicio": actividad.hora_inicio,
            "hora_fin": actividad.hora_fin,
            "usuario_id": usuario.id if usuario else None,
            "usuario_nombre": usuario.nombre if usuario else None,
            "locacion_nombre": locacion.nombre if locacion else None,
            "empresa_nombre": empresa.nombre if empresa else None,
            "estado_verificacion": actividad.estado_verificacion,
        }
        for actividad, usuario, _, locacion, empresa in comentarios_query.order_by(
            func.coalesce(models.ActividadUsuario.hora_fin, models.ActividadUsuario.hora_inicio).desc()
        ).limit(10).all()
    ]

    feedback_query = db.query(models.Feedback).filter(
        models.Feedback.company_id == company_id,
        models.Feedback.calificacion <= 2,
    )
    feedback_query = _aplicar_filtro_fecha(
        feedback_query,
        models.Feedback.creado_en,
        desde,
        hasta,
    )
    feedback_negativo_reciente = [
        {
            "feedback_id": feedback.id,
            "nombre": feedback.nombre,
            "empresa": feedback.empresa,
            "direccion": feedback.direccion,
            "calificacion": float(feedback.calificacion),
            "comentario": feedback.comentario,
            "creado_en": feedback.creado_en,
        }
        for feedback in feedback_query.order_by(models.Feedback.creado_en.desc()).limit(10).all()
    ]

    return {
        "locaciones_con_problemas": locaciones_con_problemas,
        "empleados_con_pendientes": empleados_con_pendientes,
        "comentarios_recientes": comentarios_recientes,
        "feedback_negativo_reciente": feedback_negativo_reciente,
    }

from datetime import datetime, time, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..auth.dependencies import get_current_user
from ..database import get_db
from ..models import Usuario, ListaActividad, Area, Locacion, Empresa


router = APIRouter(prefix="/portal-cliente", tags=["Portal Cliente"])


def _validar_cliente(current_user: Usuario):
    if current_user.rol.lower() != "cliente":
        raise HTTPException(status_code=403, detail="No tienes permisos")


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


def _obtener_empresas_asignadas(db: Session, current_user: Usuario):
    asignaciones = db.query(models.ClienteEmpresa).filter(
        models.ClienteEmpresa.usuario_id == current_user.id,
        models.ClienteEmpresa.company_id == current_user.company_id,
    ).all()
    empresa_ids = [asignacion.empresa_id for asignacion in asignaciones]
    empresa_nombres = [asignacion.empresa.nombre for asignacion in asignaciones if asignacion.empresa and asignacion.empresa.nombre]
    return empresa_ids, empresa_nombres


def _filtro_feedback_cliente(empresa_ids, empresa_nombres):
    filtros = []
    if empresa_ids:
        filtros.append(models.Feedback.empresa_id.in_(empresa_ids))
    if empresa_nombres:
        filtros.append(
            and_(
                models.Feedback.empresa_id.is_(None),
                models.Feedback.empresa.in_(empresa_nombres),
            )
        )
    if not filtros:
        return models.Feedback.id.is_(None)
    return or_(*filtros)


def _query_actividades_cliente(db: Session, current_user: Usuario, empresa_ids: list):
    return (
        db.query(models.ActividadUsuario)
        .join(models.Usuario, models.ActividadUsuario.usuario_id == models.Usuario.id)
        .join(models.Area, models.Usuario.area_id == models.Area.id)
        .join(models.Locacion, models.Area.locacion_id == models.Locacion.id)
        .join(models.Empresa, models.Locacion.empresa_id == models.Empresa.id)
        .filter(
            models.ActividadUsuario.company_id == current_user.company_id,
            models.Empresa.id.in_(empresa_ids),
        )
    )


@router.get("/resumen", response_model=schemas.PortalClienteResumenResponse)
def obtener_resumen_portal_cliente(
    desde: Optional[datetime] = Query(None),
    hasta: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    _validar_cliente(current_user)
    empresa_ids, empresa_nombres = _obtener_empresas_asignadas(db, current_user)
    if not empresa_ids:
        return schemas.PortalClienteResumenResponse()

    actividades_base = _query_actividades_cliente(db, current_user, empresa_ids)
    if desde is None and hasta is None:
        rango_desde, rango_hasta = _rango_hoy_utc()
        actividades_en_rango = actividades_base.filter(
            models.ActividadUsuario.hora_inicio >= rango_desde,
            models.ActividadUsuario.hora_inicio < rango_hasta,
        )
        corte_vencidas = rango_desde
    else:
        actividades_en_rango = _aplicar_filtro_fecha(
            actividades_base,
            models.ActividadUsuario.hora_inicio,
            desde,
            hasta,
        )
        corte_vencidas = desde or hasta

    actividades_hoy = actividades_en_rango.count()

    actividades_completadas_hoy = actividades_en_rango.filter(
        models.ActividadUsuario.finalizada.is_(True),
    ).count()

    actividades_pendientes_hoy = actividades_en_rango.filter(
        or_(
            models.ActividadUsuario.finalizada.is_(False),
            models.ActividadUsuario.finalizada.is_(None),
        ),
    ).count()

    actividades_vencidas = actividades_base.filter(
        models.ActividadUsuario.hora_inicio < corte_vencidas,
        or_(
            models.ActividadUsuario.finalizada.is_(False),
            models.ActividadUsuario.finalizada.is_(None),
        ),
    ).count()

    empleados_activos_hoy = (
        db.query(func.count(func.distinct(models.ActividadUsuario.usuario_id)))
        .select_from(models.ActividadUsuario)
        .join(models.Usuario, models.ActividadUsuario.usuario_id == models.Usuario.id)
        .join(models.Area, models.Usuario.area_id == models.Area.id)
        .join(models.Locacion, models.Area.locacion_id == models.Locacion.id)
        .join(models.Empresa, models.Locacion.empresa_id == models.Empresa.id)
        .filter(
            models.ActividadUsuario.company_id == current_user.company_id,
            models.Empresa.id.in_(empresa_ids),
            models.ActividadUsuario.usuario_id.isnot(None),
        )
    )
    if desde is None and hasta is None:
        empleados_activos_hoy = empleados_activos_hoy.filter(
            models.ActividadUsuario.hora_inicio >= rango_desde,
            models.ActividadUsuario.hora_inicio < rango_hasta,
        )
    else:
        empleados_activos_hoy = _aplicar_filtro_fecha(
            empleados_activos_hoy,
            models.ActividadUsuario.hora_inicio,
            desde,
            hasta,
        )
    empleados_activos_hoy = (
        empleados_activos_hoy.scalar()
        or 0
    )

    locaciones_con_actividad_hoy = (
        db.query(func.count(func.distinct(models.Area.locacion_id)))
        .select_from(models.ActividadUsuario)
        .join(models.Usuario, models.ActividadUsuario.usuario_id == models.Usuario.id)
        .join(models.Area, models.Usuario.area_id == models.Area.id)
        .join(models.Locacion, models.Area.locacion_id == models.Locacion.id)
        .join(models.Empresa, models.Locacion.empresa_id == models.Empresa.id)
        .filter(
            models.ActividadUsuario.company_id == current_user.company_id,
            models.Empresa.id.in_(empresa_ids),
            models.Area.locacion_id.isnot(None),
        )
    )
    if desde is None and hasta is None:
        locaciones_con_actividad_hoy = locaciones_con_actividad_hoy.filter(
            models.ActividadUsuario.hora_inicio >= rango_desde,
            models.ActividadUsuario.hora_inicio < rango_hasta,
        )
    else:
        locaciones_con_actividad_hoy = _aplicar_filtro_fecha(
            locaciones_con_actividad_hoy,
            models.ActividadUsuario.hora_inicio,
            desde,
            hasta,
        )
    locaciones_con_actividad_hoy = (
        locaciones_con_actividad_hoy.scalar()
        or 0
    )

    evidencias_faltantes = (
        actividades_base.filter(
            models.ActividadUsuario.evidencia_obligatoria.is_(True),
            or_(
                models.ActividadUsuario.evidencia_entregada.is_(False),
                models.ActividadUsuario.evidencia_entregada.is_(None),
            ),
        ).count()
    )

    feedbacks_negativos = 0
    if empresa_ids or empresa_nombres:
        feedbacks_negativos = (
            db.query(func.count(models.Feedback.id))
            .filter(
                models.Feedback.company_id == current_user.company_id,
                _filtro_feedback_cliente(empresa_ids, empresa_nombres),
                models.Feedback.calificacion < 3,
            )
            .scalar()
            or 0
        )

    incidentes_historial = (
        actividades_base.filter(
            models.ActividadUsuario.comentario.isnot(None),
            func.length(func.trim(models.ActividadUsuario.comentario)) > 0,
        ).count()
    )

    return {
        "actividades_hoy": actividades_hoy,
        "actividades_completadas_hoy": actividades_completadas_hoy,
        "actividades_pendientes_hoy": actividades_pendientes_hoy,
        "actividades_vencidas": actividades_vencidas,
        "empleados_activos_hoy": empleados_activos_hoy,
        "locaciones_con_actividad_hoy": locaciones_con_actividad_hoy,
        "evidencias_faltantes": evidencias_faltantes,
        "feedbacks_negativos": feedbacks_negativos,
        "incidentes_abiertos": incidentes_historial + feedbacks_negativos,
    }


@router.get("/riesgos", response_model=schemas.DashboardRiesgosResponse)
def obtener_riesgos_portal_cliente(
    desde: Optional[datetime] = Query(None),
    hasta: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    _validar_cliente(current_user)
    empresa_ids, empresa_nombres = _obtener_empresas_asignadas(db, current_user)
    if not empresa_ids:
        return schemas.DashboardRiesgosResponse()

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
            models.Empresa.id.in_(empresa_ids),
            or_(
                func.lower(func.coalesce(models.ActividadUsuario.estado_verificacion, "")) != "verificada",
                or_(
                    models.ActividadUsuario.evidencia_entregada.is_(False),
                    models.ActividadUsuario.evidencia_entregada.is_(None),
                ),
            ),
        )
    )
    locaciones_query = _aplicar_filtro_fecha(locaciones_query, models.ActividadUsuario.hora_inicio, desde, hasta)
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
        .join(models.Empresa, models.Locacion.empresa_id == models.Empresa.id, isouter=True)
        .filter(
            models.ActividadUsuario.company_id == company_id,
            models.Empresa.id.in_(empresa_ids),
            or_(
                models.ActividadUsuario.finalizada.is_(False),
                models.ActividadUsuario.finalizada.is_(None),
            ),
        )
    )
    empleados_query = _aplicar_filtro_fecha(empleados_query, models.ActividadUsuario.hora_inicio, desde, hasta)
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
            models.Empresa.id.in_(empresa_ids),
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

    feedback_negativo_reciente = []
    if empresa_ids or empresa_nombres:
        feedback_query = db.query(models.Feedback).filter(
            models.Feedback.company_id == company_id,
            _filtro_feedback_cliente(empresa_ids, empresa_nombres),
            models.Feedback.calificacion <= 2,
        )
        feedback_query = _aplicar_filtro_fecha(feedback_query, models.Feedback.creado_en, desde, hasta)
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


@router.get("/historial", response_model=list[schemas.ActividadUsuarioResponseExtendido])
def obtener_historial_portal_cliente(
    finalizada: Optional[bool] = Query(None),
    empresa: Optional[str] = Query(None),
    estado_verificacion: Optional[str] = Query(None),
    desde: Optional[datetime] = Query(None),
    hasta: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    _validar_cliente(current_user)
    empresa_ids, _ = _obtener_empresas_asignadas(db, current_user)
    if not empresa_ids:
        return []

    query = (
        db.query(models.ActividadUsuario)
        .join(models.Usuario, models.ActividadUsuario.usuario_id == models.Usuario.id)
        .join(models.Area, models.Usuario.area_id == models.Area.id)
        .join(models.Locacion, models.Area.locacion_id == models.Locacion.id)
        .join(models.Empresa, models.Locacion.empresa_id == models.Empresa.id)
        .filter(
            models.ActividadUsuario.company_id == current_user.company_id,
            models.Empresa.id.in_(empresa_ids),
        )
        .options(
            joinedload(models.ActividadUsuario.usuario),
            joinedload(models.ActividadUsuario.lista).joinedload(ListaActividad.actividades),
            joinedload(models.ActividadUsuario.usuario)
                .joinedload(Usuario.area)
                .joinedload(Area.locacion)
                .joinedload(Locacion.empresa),
        )
    )

    if finalizada is not None:
        query = query.filter(models.ActividadUsuario.finalizada == finalizada)
    if empresa:
        query = query.filter(func.lower(models.Empresa.nombre) == empresa.strip().lower())
    if estado_verificacion:
        query = query.filter(
            func.lower(models.ActividadUsuario.estado_verificacion) == estado_verificacion.strip().lower()
        )
    if desde:
        query = query.filter(models.ActividadUsuario.hora_inicio >= desde)
    if hasta:
        query = query.filter(models.ActividadUsuario.hora_inicio <= hasta)

    return query.order_by(models.ActividadUsuario.hora_inicio.desc()).all()


@router.get("/feedback", response_model=list[schemas.FeedbackResponse])
def obtener_feedback_portal_cliente(
    desde: Optional[datetime] = Query(None),
    hasta: Optional[datetime] = Query(None),
    empresa: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Security(get_current_user),
):
    _validar_cliente(current_user)
    empresa_ids, empresa_nombres = _obtener_empresas_asignadas(db, current_user)
    if not empresa_ids and not empresa_nombres:
        return []

    query = db.query(models.Feedback).filter(
        models.Feedback.company_id == current_user.company_id,
        _filtro_feedback_cliente(empresa_ids, empresa_nombres),
    )

    if empresa:
        query = query.filter(func.lower(models.Feedback.empresa) == empresa.strip().lower())
    if desde:
        query = query.filter(models.Feedback.creado_en >= desde)
    if hasta:
        query = query.filter(models.Feedback.creado_en <= hasta)

    return query.order_by(models.Feedback.creado_en.desc()).all()

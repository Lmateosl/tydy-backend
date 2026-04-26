from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session

from .. import models


ESTADOS_INCIDENTE_DUPLICADO = ("abierto", "asignado", "en_proceso", "resuelto")


def _obtener_actor_automatico(db: Session, company_id):
    admin = db.query(models.Usuario).filter(
        models.Usuario.company_id == company_id,
        models.Usuario.rol == "admin",
    ).order_by(models.Usuario.creado_en.asc().nullslast(), models.Usuario.id.asc()).first()
    if admin:
        return admin

    supervisor = db.query(models.Usuario).filter(
        models.Usuario.company_id == company_id,
        models.Usuario.rol == "supervisor",
    ).order_by(models.Usuario.creado_en.asc().nullslast(), models.Usuario.id.asc()).first()
    return supervisor


def _buscar_incidente_duplicado_por_feedback(db: Session, feedback_id):
    return db.query(models.Incidente).filter(
        models.Incidente.feedback_id == feedback_id,
        models.Incidente.estado.in_(ESTADOS_INCIDENTE_DUPLICADO),
    ).first()


def _buscar_incidente_duplicado_por_actividad_y_tipo(
    db: Session,
    actividad_usuario_id,
    tipo: str,
):
    return db.query(models.Incidente).filter(
        models.Incidente.actividad_usuario_id == actividad_usuario_id,
        models.Incidente.tipo == tipo,
        models.Incidente.estado.in_(ESTADOS_INCIDENTE_DUPLICADO),
    ).first()


def _crear_incidente_automatico(
    db: Session,
    *,
    company_id,
    tipo: str,
    prioridad: str,
    descripcion: str,
    empresa_id=None,
    locacion_id=None,
    area_id=None,
    empleado_id=None,
    supervisor_id=None,
    actividad_usuario_id=None,
    feedback_id=None,
    auto_commit: bool = True,
):
    actor = _obtener_actor_automatico(db, company_id)
    if actor is None:
        referencia = f"actividad_usuario_id={actividad_usuario_id}" if actividad_usuario_id else f"feedback_id={feedback_id}"
        print(
            f"No se pudo crear incidente automatico tipo={tipo} "
            f"para {referencia}: no hay admin ni supervisor en company_id={company_id}"
        )
        return None

    incidente = models.Incidente(
        tipo=tipo,
        estado="abierto",
        prioridad=prioridad,
        descripcion=descripcion,
        company_id=company_id,
        empresa_id=empresa_id,
        locacion_id=locacion_id,
        area_id=area_id,
        empleado_id=empleado_id,
        supervisor_id=supervisor_id,
        actividad_usuario_id=actividad_usuario_id,
        feedback_id=feedback_id,
        creado_por=actor.id,
        creado_en=datetime.utcnow(),
        actualizado_en=datetime.utcnow(),
    )

    db.add(incidente)
    if auto_commit:
        db.commit()
        db.refresh(incidente)

    return incidente


def _extraer_contexto_actividad(actividad: models.ActividadUsuario, company_id_fallback=None):
    usuario = actividad.usuario
    area = usuario.area if usuario and usuario.area else None
    locacion = area.locacion if area and area.locacion else None
    empresa = locacion.empresa if locacion and locacion.empresa else None
    company_id = actividad.company_id or company_id_fallback

    return {
        "company_id": company_id,
        "empresa_id": empresa.id if empresa else None,
        "empresa_nombre": empresa.nombre if empresa and empresa.nombre else None,
        "locacion_id": locacion.id if locacion else None,
        "locacion_nombre": locacion.nombre if locacion and locacion.nombre else None,
        "area_id": area.id if area else None,
        "area_nombre": area.nombre if area and area.nombre else None,
        "empleado_id": actividad.usuario_id,
        "empleado_nombre": usuario.nombre if usuario and usuario.nombre else None,
        "empleado_identificacion": usuario.identificacion if usuario and usuario.identificacion else None,
        "supervisor_id": actividad.supervisor_id,
        "lista_nombre": actividad.lista.nombre if actividad.lista and actividad.lista.nombre else None,
        "radio_verificacion_metros": (
            float(locacion.radio_verificacion_metros)
            if locacion and locacion.radio_verificacion_metros
            else 1000.0
        ),
    }


def _construir_descripcion_feedback_negativo(feedback: models.Feedback) -> str:
    empresa = (feedback.empresa or "").strip() or "Sin empresa"
    lugar = (feedback.contexto or feedback.direccion or "").strip() or "Sin contexto"
    calificacion = feedback.calificacion

    partes = [
        "Incidente automatico por feedback negativo.",
        f"Empresa: {empresa}.",
        f"Lugar/contexto: {lugar}.",
        f"Calificacion: {calificacion}.",
    ]

    comentario = (feedback.comentario or "").strip()
    if comentario:
        partes.append(f"Comentario: {comentario}.")

    return " ".join(partes)


def _construir_descripcion_comentario_actividad(
    actividad: models.ActividadUsuario,
    contexto: dict,
) -> str:
    comentario = (actividad.comentario or "").strip()
    empleado = contexto["empleado_nombre"] or "Sin empleado"
    if contexto["empleado_identificacion"]:
        empleado = f"{empleado} ({contexto['empleado_identificacion']})"

    partes = [
        "Incidente automatico por comentario al finalizar actividad.",
        f"Lista: {contexto['lista_nombre'] or 'Sin lista'}.",
        f"Locacion: {contexto['locacion_nombre'] or 'Sin locacion'}.",
        f"Area: {contexto['area_nombre'] or 'Sin area'}.",
        f"Empleado: {empleado}.",
        f"Comentario: {comentario}.",
    ]

    return " ".join(partes)


def _construir_descripcion_geolocalizacion(
    actividad: models.ActividadUsuario,
    contexto: dict,
) -> str:
    partes = [
        "Incidente automatico por geolocalizacion fallida al finalizar actividad.",
        f"Estado de verificacion: {actividad.estado_verificacion or 'sin_estado'}.",
        f"Lista: {contexto['lista_nombre'] or 'Sin lista'}.",
        f"Locacion: {contexto['locacion_nombre'] or 'Sin locacion'}.",
        f"Area: {contexto['area_nombre'] or 'Sin area'}.",
        f"Distancia inicio: {actividad.distancia_validacion if actividad.distancia_validacion is not None else 'sin dato'} m.",
        f"Distancia cierre: {actividad.distancia_fin if actividad.distancia_fin is not None else 'sin dato'} m.",
    ]

    if actividad.precision_inicio is not None:
        partes.append(f"Precision inicio: {actividad.precision_inicio} m.")
    if actividad.precision_fin is not None:
        partes.append(f"Precision cierre: {actividad.precision_fin} m.")
    if not actividad.metodo_inicio or not actividad.metodo_fin:
        partes.append("GPS/metodo incompleto al validar inicio o cierre.")

    return " ".join(partes)


def _resolver_prioridad_incidente_geolocalizacion(
    actividad: models.ActividadUsuario,
    radio_verificacion_metros: float,
) -> str:
    distancia_inicio = float(actividad.distancia_validacion) if actividad.distancia_validacion is not None else None
    distancia_fin = float(actividad.distancia_fin) if actividad.distancia_fin is not None else None

    if (
        (distancia_inicio is not None and distancia_inicio > radio_verificacion_metros)
        or (distancia_fin is not None and distancia_fin > radio_verificacion_metros)
    ):
        return "alta"

    return "media"


def crear_incidentes_automaticos_por_finalizacion(
    db: Session,
    actividad: models.ActividadUsuario,
    company_id_fallback=None,
):
    try:
        contexto = _extraer_contexto_actividad(actividad, company_id_fallback=company_id_fallback)
        company_id = contexto["company_id"]
        if company_id is None:
            print(
                "No se pudo crear incidentes automaticos por finalizacion "
                f"para actividad_usuario_id={actividad.id}: company_id no disponible"
            )
            return []

        incidentes_creados = []
        comentario = (actividad.comentario or "").strip()

        if comentario and not _buscar_incidente_duplicado_por_actividad_y_tipo(
            db,
            actividad.id,
            "comentario_empleado",
        ):
            incidente = _crear_incidente_automatico(
                db,
                company_id=company_id,
                tipo="comentario_empleado",
                prioridad="media",
                descripcion=_construir_descripcion_comentario_actividad(actividad, contexto),
                empresa_id=contexto["empresa_id"],
                locacion_id=contexto["locacion_id"],
                area_id=contexto["area_id"],
                empleado_id=contexto["empleado_id"],
                supervisor_id=contexto["supervisor_id"],
                actividad_usuario_id=actividad.id,
                auto_commit=False,
            )
            if incidente is not None:
                incidentes_creados.append(incidente)

        if (
            actividad.estado_verificacion == "requiere_revision"
            and not _buscar_incidente_duplicado_por_actividad_y_tipo(
                db,
                actividad.id,
                "geolocalizacion_fallida",
            )
        ):
            incidente = _crear_incidente_automatico(
                db,
                company_id=company_id,
                tipo="geolocalizacion_fallida",
                prioridad=_resolver_prioridad_incidente_geolocalizacion(
                    actividad,
                    contexto["radio_verificacion_metros"],
                ),
                descripcion=_construir_descripcion_geolocalizacion(actividad, contexto),
                empresa_id=contexto["empresa_id"],
                locacion_id=contexto["locacion_id"],
                area_id=contexto["area_id"],
                empleado_id=contexto["empleado_id"],
                supervisor_id=contexto["supervisor_id"],
                actividad_usuario_id=actividad.id,
                auto_commit=False,
            )
            if incidente is not None:
                incidentes_creados.append(incidente)

        if incidentes_creados:
            db.commit()
            for incidente in incidentes_creados:
                db.refresh(incidente)

        return incidentes_creados
    except Exception as exc:
        db.rollback()
        print(
            "Error creando incidentes automaticos por finalizacion "
            f"para actividad_usuario_id={actividad.id}: {exc}"
        )
        return []


def crear_incidente_automatico_por_feedback_negativo(
    db: Session,
    feedback: models.Feedback,
):
    if feedback.calificacion is None:
        return None

    if Decimal(str(feedback.calificacion)) > Decimal("2"):
        return None

    if _buscar_incidente_duplicado_por_feedback(db, feedback.id):
        return None

    prioridad = "alta" if Decimal(str(feedback.calificacion)) <= Decimal("1") else "media"

    return _crear_incidente_automatico(
        db,
        company_id=feedback.company_id,
        tipo="feedback_negativo",
        prioridad=prioridad,
        descripcion=_construir_descripcion_feedback_negativo(feedback),
        empresa_id=feedback.empresa_id,
        feedback_id=feedback.id,
    )

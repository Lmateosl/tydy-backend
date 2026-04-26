ALTER TABLE incidentes
    DROP CONSTRAINT IF EXISTS chk_incidentes_tipo;

ALTER TABLE incidentes
    ADD CONSTRAINT chk_incidentes_tipo CHECK (
        tipo IN (
            'feedback_negativo',
            'actividad_no_finalizada',
            'comentario_empleado',
            'evidencia_faltante',
            'geolocalizacion_fallida',
            'manual'
        )
    );

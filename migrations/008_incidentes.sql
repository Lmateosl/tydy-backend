CREATE TABLE IF NOT EXISTS incidentes (
    id UUID PRIMARY KEY,
    tipo TEXT NOT NULL,
    prioridad TEXT NOT NULL DEFAULT 'media',
    descripcion TEXT NOT NULL,
    estado TEXT NOT NULL DEFAULT 'abierto',
    company_id UUID NOT NULL REFERENCES companies(id),
    empresa_id UUID REFERENCES empresas(id),
    locacion_id UUID REFERENCES locaciones(id),
    area_id UUID REFERENCES areas(id),
    empleado_id UUID REFERENCES usuarios(id),
    supervisor_id UUID REFERENCES usuarios(id),
    asignado_a_id UUID REFERENCES usuarios(id),
    actividad_usuario_id UUID REFERENCES historial_listas(id),
    feedback_id UUID REFERENCES feedback(id),
    evidencia_inicial TEXT,
    evidencia_resolucion TEXT,
    creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resuelto_en TIMESTAMP,
    cerrado_en TIMESTAMP,
    creado_por UUID NOT NULL REFERENCES usuarios(id),
    CONSTRAINT chk_incidentes_tipo CHECK (
        tipo IN (
            'feedback_negativo',
            'actividad_no_finalizada',
            'comentario_empleado',
            'evidencia_faltante',
            'manual'
        )
    ),
    CONSTRAINT chk_incidentes_prioridad CHECK (
        prioridad IN ('baja', 'media', 'alta', 'critica')
    ),
    CONSTRAINT chk_incidentes_estado CHECK (
        estado IN ('abierto', 'asignado', 'en_proceso', 'resuelto', 'cerrado')
    )
);

CREATE INDEX IF NOT EXISTS ix_incidentes_company_id
    ON incidentes (company_id);

CREATE INDEX IF NOT EXISTS ix_incidentes_estado
    ON incidentes (estado);

CREATE INDEX IF NOT EXISTS ix_incidentes_tipo
    ON incidentes (tipo);

CREATE INDEX IF NOT EXISTS ix_incidentes_prioridad
    ON incidentes (prioridad);

CREATE INDEX IF NOT EXISTS ix_incidentes_empresa_id
    ON incidentes (empresa_id);

CREATE INDEX IF NOT EXISTS ix_incidentes_locacion_id
    ON incidentes (locacion_id);

CREATE INDEX IF NOT EXISTS ix_incidentes_area_id
    ON incidentes (area_id);

CREATE INDEX IF NOT EXISTS ix_incidentes_empleado_id
    ON incidentes (empleado_id);

CREATE INDEX IF NOT EXISTS ix_incidentes_supervisor_id
    ON incidentes (supervisor_id);

CREATE INDEX IF NOT EXISTS ix_incidentes_asignado_a_id
    ON incidentes (asignado_a_id);

CREATE INDEX IF NOT EXISTS ix_incidentes_actividad_usuario_id
    ON incidentes (actividad_usuario_id);

CREATE INDEX IF NOT EXISTS ix_incidentes_feedback_id
    ON incidentes (feedback_id);

CREATE INDEX IF NOT EXISTS ix_incidentes_company_estado_creado_en
    ON incidentes (company_id, estado, creado_en DESC);

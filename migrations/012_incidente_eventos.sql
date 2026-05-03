CREATE EXTENSION IF NOT EXISTS pgcrypto;

ALTER TABLE incidentes
    ADD COLUMN IF NOT EXISTS ultimo_evento_en TIMESTAMP;

UPDATE incidentes
SET ultimo_evento_en = COALESCE(actualizado_en, creado_en)
WHERE ultimo_evento_en IS NULL;

CREATE TABLE IF NOT EXISTS incidente_eventos (
    id UUID PRIMARY KEY,
    incidente_id UUID NOT NULL REFERENCES incidentes(id) ON DELETE CASCADE,
    company_id UUID NOT NULL REFERENCES companies(id),
    tipo_evento TEXT NOT NULL,
    actor_id UUID REFERENCES usuarios(id),
    actor_rol TEXT,
    mensaje TEXT,
    foto_url TEXT,
    foto_public_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_incidente_eventos_tipo CHECK (
        tipo_evento IN (
            'creado',
            'comentario',
            'actualizado',
            'estado_cambiado',
            'asignacion_cambiada',
            'resuelto',
            'cerrado'
        )
    )
);

CREATE INDEX IF NOT EXISTS ix_incidente_eventos_incidente_id
    ON incidente_eventos (incidente_id);

CREATE INDEX IF NOT EXISTS ix_incidente_eventos_company_id
    ON incidente_eventos (company_id);

CREATE INDEX IF NOT EXISTS ix_incidente_eventos_tipo_evento
    ON incidente_eventos (tipo_evento);

CREATE INDEX IF NOT EXISTS ix_incidente_eventos_incidente_creado_en
    ON incidente_eventos (incidente_id, creado_en DESC);

CREATE INDEX IF NOT EXISTS ix_incidente_eventos_company_creado_en
    ON incidente_eventos (company_id, creado_en DESC);

CREATE INDEX IF NOT EXISTS ix_incidente_eventos_actor_id
    ON incidente_eventos (actor_id);

INSERT INTO incidente_eventos (
    id,
    incidente_id,
    company_id,
    tipo_evento,
    actor_id,
    actor_rol,
    mensaje,
    metadata,
    creado_en
)
SELECT
    gen_random_uuid(),
    i.id,
    i.company_id,
    'creado',
    i.creado_por,
    u.rol,
    'Incidente creado',
    jsonb_strip_nulls(
        jsonb_build_object(
            'origen', CASE
                WHEN i.feedback_id IS NOT NULL OR i.actividad_usuario_id IS NOT NULL THEN 'automatico'
                ELSE 'manual'
            END,
            'tipo_incidente', i.tipo,
            'estado', i.estado,
            'prioridad', i.prioridad,
            'descripcion', i.descripcion,
            'actividad_usuario_id', i.actividad_usuario_id,
            'feedback_id', i.feedback_id
        )
    ),
    i.creado_en
FROM incidentes i
LEFT JOIN usuarios u ON u.id = i.creado_por
WHERE NOT EXISTS (
    SELECT 1
    FROM incidente_eventos e
    WHERE e.incidente_id = i.id
      AND e.tipo_evento = 'creado'
);

INSERT INTO incidente_eventos (
    id,
    incidente_id,
    company_id,
    tipo_evento,
    actor_id,
    actor_rol,
    mensaje,
    foto_url,
    metadata,
    creado_en
)
SELECT
    gen_random_uuid(),
    i.id,
    i.company_id,
    'resuelto',
    i.creado_por,
    u.rol,
    COALESCE(NULLIF(i.evidencia_resolucion, ''), 'Incidente resuelto'),
    i.foto_resolucion,
    jsonb_strip_nulls(
        jsonb_build_object(
            'estado_nuevo', 'resuelto',
            'evidencia_resolucion', i.evidencia_resolucion
        )
    ),
    i.resuelto_en
FROM incidentes i
LEFT JOIN usuarios u ON u.id = i.creado_por
WHERE i.resuelto_en IS NOT NULL
  AND NOT EXISTS (
    SELECT 1
    FROM incidente_eventos e
    WHERE e.incidente_id = i.id
      AND e.tipo_evento = 'resuelto'
);

INSERT INTO incidente_eventos (
    id,
    incidente_id,
    company_id,
    tipo_evento,
    actor_id,
    actor_rol,
    mensaje,
    metadata,
    creado_en
)
SELECT
    gen_random_uuid(),
    i.id,
    i.company_id,
    'cerrado',
    i.creado_por,
    u.rol,
    'Incidente cerrado',
    jsonb_build_object(
        'estado_nuevo', 'cerrado'
    ),
    i.cerrado_en
FROM incidentes i
LEFT JOIN usuarios u ON u.id = i.creado_por
WHERE i.cerrado_en IS NOT NULL
  AND NOT EXISTS (
    SELECT 1
    FROM incidente_eventos e
    WHERE e.incidente_id = i.id
      AND e.tipo_evento = 'cerrado'
);

UPDATE incidentes
SET ultimo_evento_en = COALESCE(cerrado_en, resuelto_en, actualizado_en, creado_en)
WHERE ultimo_evento_en IS NULL
   OR ultimo_evento_en <> COALESCE(cerrado_en, resuelto_en, actualizado_en, creado_en);

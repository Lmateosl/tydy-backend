CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS notificaciones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    actor_id UUID NULL REFERENCES usuarios(id) ON DELETE SET NULL,
    tipo TEXT NOT NULL,
    categoria TEXT NOT NULL,
    evento TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'info',
    titulo TEXT NOT NULL,
    mensaje TEXT NOT NULL,
    source_type TEXT NULL,
    source_id UUID NULL,
    source_event_id UUID NULL,
    deep_link TEXT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    dedupe_key TEXT NULL,
    creado_en TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_notificaciones_tipo
        CHECK (tipo IN ('automatica', 'manual')),
    CONSTRAINT chk_notificaciones_categoria
        CHECK (categoria IN ('incidente', 'actividad', 'feedback', 'operativa')),
    CONSTRAINT chk_notificaciones_severity
        CHECK (severity IN ('info', 'warning', 'critical')),
    CONSTRAINT chk_notificaciones_source_type
        CHECK (
            source_type IS NULL OR
            source_type IN ('incidente', 'incidente_evento', 'actividad', 'feedback', 'alerta_manual')
        ),
    CONSTRAINT chk_notificaciones_titulo_nonempty
        CHECK (btrim(titulo) <> ''),
    CONSTRAINT chk_notificaciones_mensaje_nonempty
        CHECK (btrim(mensaje) <> '')
);

CREATE TABLE IF NOT EXISTS notificacion_destinatarios (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notification_id UUID NOT NULL REFERENCES notificaciones(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    read_at TIMESTAMP NULL,
    delivered_at TIMESTAMP NOT NULL DEFAULT NOW(),
    hidden_at TIMESTAMP NULL,
    creado_en TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_notificacion_destinatario UNIQUE (notification_id, user_id),
    CONSTRAINT chk_notificacion_destinatarios_read_after_delivery
        CHECK (read_at IS NULL OR read_at >= delivered_at),
    CONSTRAINT chk_notificacion_destinatarios_hidden_after_delivery
        CHECK (hidden_at IS NULL OR hidden_at >= delivered_at)
);

CREATE INDEX IF NOT EXISTS ix_notificaciones_company_creado_en
    ON notificaciones (company_id, creado_en DESC);

CREATE INDEX IF NOT EXISTS ix_notificaciones_tipo
    ON notificaciones (tipo);

CREATE INDEX IF NOT EXISTS ix_notificaciones_categoria
    ON notificaciones (categoria);

CREATE INDEX IF NOT EXISTS ix_notificaciones_evento
    ON notificaciones (evento);

CREATE INDEX IF NOT EXISTS ix_notificaciones_source
    ON notificaciones (source_type, source_id);

CREATE INDEX IF NOT EXISTS ix_notificaciones_source_event_id
    ON notificaciones (source_event_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_notificaciones_company_dedupe_key
    ON notificaciones (company_id, dedupe_key)
    WHERE dedupe_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_notif_destinatarios_user_delivery
    ON notificacion_destinatarios (user_id, delivered_at DESC);

CREATE INDEX IF NOT EXISTS ix_notif_destinatarios_user_unread
    ON notificacion_destinatarios (user_id, delivered_at DESC)
    WHERE read_at IS NULL AND hidden_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_notif_destinatarios_notification
    ON notificacion_destinatarios (notification_id);

CREATE INDEX IF NOT EXISTS ix_notif_destinatarios_company_user
    ON notificacion_destinatarios (company_id, user_id);

ALTER TABLE historial_listas
    ADD COLUMN IF NOT EXISTS supervisor_id UUID REFERENCES usuarios(id),
    ADD COLUMN IF NOT EXISTS latitud_inicio NUMERIC(9, 6),
    ADD COLUMN IF NOT EXISTS longitud_inicio NUMERIC(9, 6),
    ADD COLUMN IF NOT EXISTS distancia_validacion NUMERIC(10, 2),
    ADD COLUMN IF NOT EXISTS metodo_inicio VARCHAR,
    ADD COLUMN IF NOT EXISTS estado_verificacion VARCHAR DEFAULT 'iniciada';


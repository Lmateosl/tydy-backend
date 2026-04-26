ALTER TABLE historial_listas
    ADD COLUMN IF NOT EXISTS evidencia_obligatoria BOOLEAN,
    ADD COLUMN IF NOT EXISTS evidencia_entregada BOOLEAN,
    ADD COLUMN IF NOT EXISTS evidencia_subida_en TIMESTAMP,
    ADD COLUMN IF NOT EXISTS evidencia_usuario_id UUID REFERENCES usuarios(id),
    ADD COLUMN IF NOT EXISTS evidencia_tipo VARCHAR,
    ADD COLUMN IF NOT EXISTS evidencia_nombre_archivo VARCHAR;


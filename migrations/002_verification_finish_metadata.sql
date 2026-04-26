ALTER TABLE historial_listas
    ADD COLUMN IF NOT EXISTS latitud_fin NUMERIC(9, 6),
    ADD COLUMN IF NOT EXISTS longitud_fin NUMERIC(9, 6),
    ADD COLUMN IF NOT EXISTS distancia_fin NUMERIC(10, 2),
    ADD COLUMN IF NOT EXISTS metodo_fin VARCHAR,
    ADD COLUMN IF NOT EXISTS duracion_segundos INTEGER;


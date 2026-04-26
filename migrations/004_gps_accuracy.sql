ALTER TABLE historial_listas
    ADD COLUMN IF NOT EXISTS precision_inicio NUMERIC(10, 2),
    ADD COLUMN IF NOT EXISTS precision_fin NUMERIC(10, 2);


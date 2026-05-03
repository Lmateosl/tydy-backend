ALTER TABLE locaciones
    ADD COLUMN IF NOT EXISTS supervisor_id UUID NULL REFERENCES usuarios(id);

CREATE INDEX IF NOT EXISTS ix_locaciones_supervisor_id
    ON locaciones (supervisor_id);

CREATE INDEX IF NOT EXISTS ix_locaciones_company_supervisor
    ON locaciones (company_id, supervisor_id);

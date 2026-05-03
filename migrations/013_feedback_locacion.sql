ALTER TABLE feedback_qr
    ADD COLUMN IF NOT EXISTS locacion_id UUID REFERENCES locaciones(id);

ALTER TABLE feedback
    ADD COLUMN IF NOT EXISTS locacion_id UUID REFERENCES locaciones(id);

CREATE INDEX IF NOT EXISTS ix_feedback_qr_locacion_id
    ON feedback_qr (locacion_id);

CREATE INDEX IF NOT EXISTS ix_feedback_locacion_id
    ON feedback (locacion_id);

CREATE INDEX IF NOT EXISTS ix_feedback_qr_company_empresa_contexto
    ON feedback_qr (company_id, empresa_id, contexto);

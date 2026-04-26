ALTER TABLE feedback_qr
    ADD COLUMN IF NOT EXISTS empresa_id UUID REFERENCES empresas(id),
    ADD COLUMN IF NOT EXISTS contexto TEXT;

ALTER TABLE feedback
    ADD COLUMN IF NOT EXISTS empresa_id UUID REFERENCES empresas(id),
    ADD COLUMN IF NOT EXISTS contexto TEXT;

CREATE INDEX IF NOT EXISTS ix_feedback_qr_company_empresa
    ON feedback_qr (company_id, empresa_id);

CREATE INDEX IF NOT EXISTS ix_feedback_company_empresa
    ON feedback (company_id, empresa_id);

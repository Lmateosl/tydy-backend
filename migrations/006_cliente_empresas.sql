CREATE TABLE IF NOT EXISTS cliente_empresas (
    id UUID PRIMARY KEY,
    usuario_id UUID NOT NULL REFERENCES usuarios(id),
    empresa_id UUID NOT NULL REFERENCES empresas(id),
    company_id UUID NOT NULL REFERENCES companies(id),
    creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    creado_por UUID NOT NULL REFERENCES usuarios(id),
    CONSTRAINT uq_cliente_empresas_usuario_empresa UNIQUE (usuario_id, empresa_id)
);

CREATE INDEX IF NOT EXISTS ix_cliente_empresas_usuario_id
    ON cliente_empresas (usuario_id);

CREATE INDEX IF NOT EXISTS ix_cliente_empresas_empresa_id
    ON cliente_empresas (empresa_id);

CREATE INDEX IF NOT EXISTS ix_cliente_empresas_company_id
    ON cliente_empresas (company_id);

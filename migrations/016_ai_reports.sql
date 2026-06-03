CREATE TABLE company_ai_settings (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL UNIQUE REFERENCES companies(id) ON DELETE CASCADE,
    ai_enabled BOOLEAN NOT NULL DEFAULT false,
    plan_name TEXT NULL,
    reports_monthly_limit INTEGER NOT NULL DEFAULT 0,
    monthly_token_limit INTEGER NOT NULL DEFAULT 0,
    monthly_cost_limit_usd NUMERIC(12, 6) NOT NULL DEFAULT 0,
    reset_day INTEGER NOT NULL DEFAULT 1,
    hard_block_on_limit BOOLEAN NOT NULL DEFAULT true,
    dedupe_window_hours INTEGER NOT NULL DEFAULT 24,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE company_ai_usage_monthly (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    usage_year INTEGER NOT NULL,
    usage_month INTEGER NOT NULL,
    period_start TIMESTAMP NOT NULL,
    period_end TIMESTAMP NOT NULL,
    reports_generated_count INTEGER NOT NULL DEFAULT 0,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    total_cost_usd NUMERIC(12, 6) NOT NULL DEFAULT 0,
    last_report_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_company_ai_usage_monthly_company_period UNIQUE (company_id, usage_year, usage_month)
);

CREATE TABLE ai_reports (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    scope_type TEXT NOT NULL CHECK (scope_type IN ('company', 'empresa', 'locacion')),
    scope_entity_id UUID NULL,
    period_type TEXT NOT NULL CHECK (period_type IN ('weekly', 'monthly')),
    period_start TIMESTAMP NOT NULL,
    period_end TIMESTAMP NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('queued', 'processing', 'completed', 'failed')),
    prompt_template_key TEXT NOT NULL,
    prompt_template_version TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    requested_by UUID NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
    request_fingerprint TEXT NULL,
    report_json JSONB NULL,
    facts_json JSONB NULL,
    citations_json JSONB NULL,
    langfuse_trace_id TEXT NULL,
    error_message TEXT NULL,
    generation_block_reason TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP NULL,
    failed_at TIMESTAMP NULL
);

CREATE TABLE ai_report_runs (
    id UUID PRIMARY KEY,
    report_id UUID NOT NULL REFERENCES ai_reports(id) ON DELETE CASCADE,
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    run_number INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('queued', 'processing', 'completed', 'failed')),
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_template_key TEXT NOT NULL,
    prompt_template_version TEXT NOT NULL,
    input_facts_json JSONB NOT NULL,
    output_json JSONB NULL,
    raw_response_json JSONB NULL,
    usage_prompt_tokens INTEGER NULL,
    usage_completion_tokens INTEGER NULL,
    usage_total_tokens INTEGER NULL,
    estimated_cost_usd NUMERIC(12, 6) NULL,
    billing_counted BOOLEAN NOT NULL DEFAULT false,
    latency_ms INTEGER NULL,
    langfuse_trace_id TEXT NULL,
    langfuse_observation_id TEXT NULL,
    error_message TEXT NULL,
    started_at TIMESTAMP NULL,
    completed_at TIMESTAMP NULL,
    failed_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_ai_report_runs_report_run UNIQUE (report_id, run_number)
);

CREATE INDEX idx_company_ai_usage_monthly_company_period
    ON company_ai_usage_monthly (company_id, usage_year, usage_month);

CREATE INDEX idx_ai_reports_company_created_at
    ON ai_reports (company_id, created_at DESC);

CREATE INDEX idx_ai_reports_status
    ON ai_reports (status);

CREATE INDEX idx_ai_reports_scope_period
    ON ai_reports (company_id, scope_type, scope_entity_id, period_start, period_end);

CREATE INDEX idx_ai_reports_request_fingerprint
    ON ai_reports (company_id, request_fingerprint);

CREATE INDEX idx_ai_report_runs_report_created_at
    ON ai_report_runs (report_id, created_at DESC);

CREATE INDEX idx_ai_report_runs_company_created_at
    ON ai_report_runs (company_id, created_at DESC);

CREATE INDEX idx_ai_report_runs_status
    ON ai_report_runs (status);

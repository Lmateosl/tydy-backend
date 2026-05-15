ALTER TABLE feedback_qr
    ADD COLUMN IF NOT EXISTS area_id UUID REFERENCES areas(id);

ALTER TABLE feedback
    ADD COLUMN IF NOT EXISTS area_id UUID REFERENCES areas(id);

CREATE INDEX IF NOT EXISTS ix_feedback_qr_area_id
    ON feedback_qr (area_id);

CREATE INDEX IF NOT EXISTS ix_feedback_area_id
    ON feedback (area_id);

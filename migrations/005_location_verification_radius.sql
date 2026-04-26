ALTER TABLE locaciones
    ADD COLUMN IF NOT EXISTS radio_verificacion_metros INTEGER DEFAULT 1000;

UPDATE locaciones
SET radio_verificacion_metros = 1000
WHERE radio_verificacion_metros IS NULL;


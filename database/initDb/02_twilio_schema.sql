-- Twilio dashboard extension to the existing schema.
-- Adds one table (twilio_call) and seeds lookup rows.
-- Depends on 01_schema.sql (recordSession, file, fileType, account tables).

CREATE TABLE IF NOT EXISTS twilio_call (
    id                    INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    recordingSession_id   INT NOT NULL UNIQUE,
    call_sid              VARCHAR(64) NOT NULL UNIQUE,
    direction             VARCHAR(16) NOT NULL,
    from_number           VARCHAR(32),
    to_number             VARCHAR(32),
    status                VARCHAR(32) NOT NULL,
    duration_seconds      INT,
    recording_sid         VARCHAR(64) UNIQUE,
    recording_twilio_url  TEXT,
    recording_file_id     INT,
    error_code            VARCHAR(16),
    error_message         TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_twilio_call_session
        FOREIGN KEY (recordingSession_id) REFERENCES recordSession(recordingSession_id) ON DELETE CASCADE,
    CONSTRAINT fk_twilio_call_file
        FOREIGN KEY (recording_file_id)   REFERENCES file(file_id)                      ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_twilio_call_status     ON twilio_call(status);
CREATE INDEX IF NOT EXISTS idx_twilio_call_created_at ON twilio_call(created_at DESC);

-- Keep updated_at fresh on every row update
CREATE OR REPLACE FUNCTION twilio_call_set_updated_at() RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS twilio_call_updated_at ON twilio_call;
CREATE TRIGGER twilio_call_updated_at
  BEFORE UPDATE ON twilio_call
  FOR EACH ROW EXECUTE FUNCTION twilio_call_set_updated_at();

-- Seed rows consumed by the dashboard
INSERT INTO fileType (fileTypeName) VALUES ('audio/mpeg') ON CONFLICT (fileTypeName) DO NOTHING;
INSERT INTO fileType (fileTypeName) VALUES ('audio/wav')  ON CONFLICT (fileTypeName) DO NOTHING;

INSERT INTO account (password, account_email)
  VALUES ('dashboard-seed-no-login', 'dashboard@local')
  ON CONFLICT (account_email) DO NOTHING;

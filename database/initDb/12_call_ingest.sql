-- Call ingest extension: conversation grouping + twilio_call column additions.
-- Applied automatically by Postgres container after 09_content_analysis.sql.

-- 1. call_conversation table (mirrors whatsapp_conversation)
CREATE TABLE IF NOT EXISTS call_conversation (
    id             SERIAL PRIMARY KEY,
    contact_phone  VARCHAR(30) NOT NULL UNIQUE,
    contact_name   VARCHAR(255),
    last_call_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Extend twilio_call with conversation grouping, analysis link, transcript
ALTER TABLE twilio_call ADD COLUMN IF NOT EXISTS conversation_id       INT REFERENCES call_conversation(id) ON DELETE SET NULL;
ALTER TABLE twilio_call ADD COLUMN IF NOT EXISTS incident_form_id      INT REFERENCES incident_form(id)     ON DELETE SET NULL;
ALTER TABLE twilio_call ADD COLUMN IF NOT EXISTS transcript_text       TEXT;
ALTER TABLE twilio_call ADD COLUMN IF NOT EXISTS local_recording_path  TEXT;

-- Make recordingSession_id nullable (call row inserted before voice-app returns session)
ALTER TABLE twilio_call ALTER COLUMN "recordingsession_id" DROP NOT NULL;

CREATE INDEX IF NOT EXISTS idx_twilio_call_conversation ON twilio_call(conversation_id);
CREATE INDEX IF NOT EXISTS idx_twilio_call_incident     ON twilio_call(incident_form_id) WHERE incident_form_id IS NOT NULL;

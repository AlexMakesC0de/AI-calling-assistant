-- whatsapp_conversation: one row per external contact phone number.
-- Groups messages into a thread; updated on every new message.
CREATE TABLE IF NOT EXISTS whatsapp_conversation (
    id              SERIAL PRIMARY KEY,
    contact_phone   VARCHAR(30)  NOT NULL UNIQUE,  -- E.164, no "whatsapp:" prefix
    contact_name    VARCHAR(255),                   -- Twilio ProfileName when available
    last_message_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- whatsapp_message: every inbound and outbound message.
CREATE TABLE IF NOT EXISTS whatsapp_message (
    id               SERIAL PRIMARY KEY,
    conversation_id  INT          NOT NULL,
    twilio_sid       VARCHAR(64)  UNIQUE,           -- Twilio MessageSid; NULL if not yet confirmed
    direction        TEXT         NOT NULL
                     CHECK (direction IN ('inbound', 'outbound')),
    status           TEXT         NOT NULL DEFAULT 'received'
                     CHECK (status IN ('received', 'queued', 'sent', 'delivered', 'read', 'failed', 'undelivered')),
    message_type     TEXT         NOT NULL DEFAULT 'text'
                     CHECK (message_type IN ('text', 'voice_note', 'image', 'document', 'video', 'sticker', 'location', 'unknown')),
    body             TEXT,
    -- set when an inbound voice note is successfully processed into a form
    incident_form_id INT,
    raw_payload      JSONB        NOT NULL DEFAULT '{}',
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_wa_msg_conversation
        FOREIGN KEY (conversation_id) REFERENCES whatsapp_conversation(id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_wa_msg_incident
        FOREIGN KEY (incident_form_id) REFERENCES incident_form(id)
        ON DELETE SET NULL
);

-- whatsapp_media: one row per attachment on a message.
-- A single WhatsApp message can carry up to 10 media items (Twilio MediaUrl0..9).
CREATE TABLE IF NOT EXISTS whatsapp_media (
    id              SERIAL PRIMARY KEY,
    message_id      INT          NOT NULL,
    media_index     SMALLINT     NOT NULL DEFAULT 0, -- 0-based; mirrors Twilio MediaUrl{n}
    twilio_url      TEXT         NOT NULL,
    content_type    VARCHAR(100) NOT NULL DEFAULT 'application/octet-stream',
    local_path      TEXT,                             -- path under /data/shared/whatsapp-media/
    file_size_bytes BIGINT,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_wa_media_message
        FOREIGN KEY (message_id) REFERENCES whatsapp_message(id)
        ON DELETE CASCADE,
    CONSTRAINT uq_wa_media_msg_index
        UNIQUE (message_id, media_index)
);

CREATE INDEX IF NOT EXISTS idx_wa_msg_conversation ON whatsapp_message(conversation_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_wa_msg_type         ON whatsapp_message(message_type);
CREATE INDEX IF NOT EXISTS idx_wa_msg_incident     ON whatsapp_message(incident_form_id) WHERE incident_form_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_wa_conv_last_msg    ON whatsapp_conversation(last_message_at DESC);

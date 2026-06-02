-- email_conversation: one row per unique sender email address.
-- Groups messages into a thread; updated on every new inbound email.
CREATE TABLE IF NOT EXISTS email_conversation (
    id              SERIAL PRIMARY KEY,
    sender_email    VARCHAR(255)  NOT NULL UNIQUE,  -- normalized to lowercase
    sender_name     VARCHAR(255),                   -- display name from From header
    last_message_at TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- email_message: every inbound (and future outbound) email.
CREATE TABLE IF NOT EXISTS email_message (
    id                SERIAL PRIMARY KEY,
    conversation_id   INT           NOT NULL,
    message_id_header VARCHAR(500)  UNIQUE,           -- RFC 5322 Message-ID header
    direction         TEXT          NOT NULL
                      CHECK (direction IN ('inbound', 'outbound')),
    subject           TEXT,
    from_email        VARCHAR(255)  NOT NULL,
    from_name         VARCHAR(255),
    to_email          TEXT,
    cc                TEXT,
    body_text         TEXT,
    body_html         TEXT,
    headers           JSONB         NOT NULL DEFAULT '{}',
    envelope          JSONB         NOT NULL DEFAULT '{}',
    raw_payload       JSONB         NOT NULL DEFAULT '{}',
    created_at        TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_email_msg_conversation
        FOREIGN KEY (conversation_id) REFERENCES email_conversation(id)
        ON DELETE RESTRICT
);

-- email_attachment: one row per attachment on a message.
CREATE TABLE IF NOT EXISTS email_attachment (
    id               SERIAL PRIMARY KEY,
    message_id       INT           NOT NULL,
    attachment_index SMALLINT      NOT NULL DEFAULT 0,
    external_id      VARCHAR(500),                     -- Outlook Graph attachment ID for proxying downloads
    file_name        VARCHAR(500),
    content_type     VARCHAR(100)  NOT NULL DEFAULT 'application/octet-stream',
    local_path       TEXT,                             -- path under /data/shared/email-attachments/ (optional cache)
    file_size_bytes  BIGINT,
    content_id       VARCHAR(255),                     -- for inline/CID attachments (future use)
    created_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_email_att_message
        FOREIGN KEY (message_id) REFERENCES email_message(id)
        ON DELETE CASCADE,
    CONSTRAINT uq_email_att_msg_index
        UNIQUE (message_id, attachment_index)
);

CREATE INDEX IF NOT EXISTS idx_email_msg_conversation ON email_message(conversation_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_email_conv_last_msg    ON email_conversation(last_message_at DESC);
CREATE INDEX IF NOT EXISTS idx_email_att_message      ON email_attachment(message_id);

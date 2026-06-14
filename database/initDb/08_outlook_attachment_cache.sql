CREATE TABLE IF NOT EXISTS outlook_attachment_cache (
    id              SERIAL PRIMARY KEY,
    message_id      VARCHAR(500)  NOT NULL,
    attachment_id   VARCHAR(500)  NOT NULL,
    file_name       VARCHAR(500),
    content_type    VARCHAR(100)  NOT NULL DEFAULT 'application/octet-stream',
    local_path      TEXT          NOT NULL,
    file_size_bytes BIGINT,
    content_id      VARCHAR(255),
    is_inline       BOOLEAN       NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_outlook_att_cache UNIQUE (message_id, attachment_id)
);

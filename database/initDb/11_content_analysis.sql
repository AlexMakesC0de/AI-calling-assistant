CREATE TABLE IF NOT EXISTS content_analysis (
    id                        SERIAL PRIMARY KEY,
    source_type               VARCHAR(30) NOT NULL,
    source_id                 TEXT NOT NULL,
    account_id                INT NOT NULL,
    classification_label      VARCHAR(20),
    classification_confidence REAL,
    classification_reason     TEXT,
    incident_form_id          INT,
    pipeline_status           VARCHAR(30) NOT NULL DEFAULT 'pending',
    pipeline_step             VARCHAR(30),
    error_message             TEXT,
    content_preview           TEXT,
    sender                    TEXT,
    analyzed_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_content_analysis_source UNIQUE (source_type, source_id)
);

CREATE INDEX IF NOT EXISTS idx_content_analysis_account ON content_analysis(account_id);
CREATE INDEX IF NOT EXISTS idx_content_analysis_incident ON content_analysis(incident_form_id);

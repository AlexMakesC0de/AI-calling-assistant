CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS account (
    account_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    password VARCHAR(255) NOT NULL,
    account_email VARCHAR(255) UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS recordSession (
    recordingSession_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    startTime TIMESTAMP NOT NULL,
    endTime TIMESTAMP,
    AccountId INT NOT NULL,
    FOREIGN KEY (AccountId) REFERENCES Account(account_id)
);

CREATE TABLE IF NOT EXISTS fileType (
    fileType_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    fileTypeName VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS file (
    file_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    fileTypeId INT NOT NULL,
    fileUrl TEXT NOT NULL,
    recordingSession_id INT NOT NULL,
    FOREIGN KEY (fileTypeId) REFERENCES FileType(fileType_id),
    FOREIGN KEY (recordingSession_id) REFERENCES RecordSession(recordingSession_id)
);


CREATE TABLE IF NOT EXISTS TranscriptChunk (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    file_id INT NOT NULL,
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(1536),
    FOREIGN KEY (file_id) REFERENCES File(file_id)
);

CREATE TABLE IF NOT EXISTS incident_forms (
    id SERIAL PRIMARY KEY,
    form_id TEXT UNIQUE NOT NULL,
    file_id INT NOT NULl,
    completed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status TEXT NOT NULL DEFAULT 'completed',
    category TEXT,
    priority TEXT,
    caller_name TEXT,
    agent_name TEXT,
    sentiment TEXT,
    summary TEXT,
    audio_filename TEXT,
    form_data JSONB NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_incident_forms_file
        FOREIGN KEY (file_id) REFERENCES File(file_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_incident_forms_form_id
    ON incident_forms (form_id);
CREATE INDEX IF NOT EXISTS idx_incident_forms_file_id
    ON incident_forms (file_id);
CREATE INDEX IF NOT EXISTS idx_incident_forms_category
    ON incident_forms (category);
CREATE INDEX IF NOT EXISTS idx_incident_forms_created_at
    ON incident_forms (created_at DESC);


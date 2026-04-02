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

CREATE TABLE IF NOT EXISTS incident_form (
    id SERIAL PRIMARY KEY,
    file_id INT NOT NULL,
    status TEXT NOT NULL DEFAULT 'completed',
    category TEXT,
    priority TEXT,
    completed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_incident_file
        FOREIGN KEY (file_id) REFERENCES file(file_id)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS incident_transcription (
    id SERIAL PRIMARY KEY,
    incident_form_id INT NOT NULL,
    lang_code VARCHAR(10) NOT NULL,
    transcript_text TEXT,
    summary TEXT,
    sentiment TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT fk_transcription_form
        FOREIGN KEY (incident_form_id) REFERENCES incident_form(id)
        ON DELETE CASCADE,
    CONSTRAINT unique_lang_per_form
        UNIQUE (incident_form_id, lang_code)
);

CREATE TABLE IF NOT EXISTS incident_general_information (
    incident_form_id INT PRIMARY KEY,
    caller_name VARCHAR(255),
    agent_name VARCHAR(255),
    audio_filename TEXT,
    form_data JSONB NOT NULL DEFAULT '{}',

    CONSTRAINT fk_info_form
        FOREIGN KEY (incident_form_id) REFERENCES incident_form(id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_transcription_form_id ON incident_transcription(incident_form_id);
CREATE INDEX IF NOT EXISTS idx_incident_form_file_id ON incident_form(file_id);
CREATE INDEX IF NOT EXISTS idx_transcription_lang ON incident_transcription(lang_code);


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
    AccountId INT NOT NULL REFERENCES Account(account_id),
    FOREIGN KEY (AccountId) REFERENCES Account(account_id)
);

CREATE TABLE FileType (
    fileType_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    fileTypeName VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE File (
    file_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    fileTypeId INT NOT NULL REFERENCES FileType(fileType_id),
    fileUrl TEXT NOT NULL,
    recordingSession_id INT NOT NULL,
    FOREIGN KEY (fileTypeId) REFERENCES FileType(fileType_id),
    FOREIGN KEY (recordingSession_id) REFERENCES RecordSession(recordingSession_id)
);


CREATE TABLE TranscriptChunk (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    file_id INT NOT NULL,
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(1536),
    FOREIGN KEY (file_id) REFERENCES File(file_id)
);


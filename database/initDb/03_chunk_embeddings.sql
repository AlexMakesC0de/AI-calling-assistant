-- Resize TranscriptChunk.embedding to match the local Ollama model used for
-- semantic search (nomic-embed-text → 768 dims). The existing column is
-- vector(1536) but the voice-app pipeline never wrote to it, so dropping and
-- recreating is safe.
--
-- This file ships in docker-entrypoint-initdb.d, so a fresh `support_db`
-- volume picks it up automatically. To migrate an existing volume:
--   docker exec -i support-db psql -U support -d support_db < database/initDb/03_chunk_embeddings.sql

ALTER TABLE TranscriptChunk
    DROP COLUMN IF EXISTS embedding;

ALTER TABLE TranscriptChunk
    ADD COLUMN embedding vector(768);

-- Cosine-distance index for fast top-k semantic queries.
CREATE INDEX IF NOT EXISTS transcriptchunk_embedding_cosine_idx
    ON TranscriptChunk
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

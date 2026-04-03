import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras
import psycopg2.pool

from config import AppConfig


class PostgresRepository:
    def __init__(self, config: AppConfig, log: logging.Logger):
        self._config = config
        self._log = log
        self._pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=8,
            host=self._config.db_host,
            port=self._config.db_port,
            dbname=self._config.db_name,
            user=self._config.db_user,
            password=self._config.db_password,
        )

    def get_connection(self):
        return self._pool.getconn()

    def _release_connection(self, conn) -> None:
        self._pool.putconn(conn)

    def init_db(self) -> None:
        """Ensure application tables exist and are compatible with current schema."""
        try:
            conn = self.get_connection()
            try:
                with conn.cursor() as cur:
                    # Ensure prerequisite tables exist (normally created by
                    # database/initDb/schema.sql, but needed if init hasn't run).
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS account (
                            account_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                            password   VARCHAR(255) NOT NULL,
                            account_email VARCHAR(255) UNIQUE NOT NULL
                        );
                        CREATE TABLE IF NOT EXISTS recordSession (
                            recordingSession_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                            startTime   TIMESTAMP NOT NULL,
                            endTime     TIMESTAMP,
                            AccountId   INT NOT NULL,
                            FOREIGN KEY (AccountId) REFERENCES account(account_id)
                        );
                        CREATE TABLE IF NOT EXISTS fileType (
                            fileType_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                            fileTypeName VARCHAR(50) NOT NULL UNIQUE
                        );
                        CREATE TABLE IF NOT EXISTS file (
                            file_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                            fileTypeId INT NOT NULL,
                            fileUrl    TEXT NOT NULL,
                            recordingSession_id INT NOT NULL,
                            FOREIGN KEY (fileTypeId) REFERENCES fileType(fileType_id),
                            FOREIGN KEY (recordingSession_id) REFERENCES recordSession(recordingSession_id)
                        );
                        """
                    )
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS incident_form (
                            id              SERIAL PRIMARY KEY,
                            file_id         INT NOT NULL,
                            status          TEXT NOT NULL DEFAULT 'completed',
                            category        TEXT,
                            priority        TEXT,
                            completed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            CONSTRAINT fk_incident_file
                                FOREIGN KEY (file_id) REFERENCES file(file_id)
                                ON DELETE RESTRICT
                        );

                        CREATE TABLE IF NOT EXISTS incident_transcription (
                            id                SERIAL PRIMARY KEY,
                            incident_form_id  INT NOT NULL,
                            lang_code         VARCHAR(10) NOT NULL,
                            transcript_text   TEXT,
                            summary           TEXT,
                            sentiment         TEXT,
                            created_at        TIMESTAMPTZ DEFAULT NOW(),
                            CONSTRAINT fk_transcription_form
                                FOREIGN KEY (incident_form_id) REFERENCES incident_form(id)
                                ON DELETE CASCADE,
                            CONSTRAINT unique_lang_per_form
                                UNIQUE (incident_form_id, lang_code)
                        );

                        CREATE TABLE IF NOT EXISTS incident_general_information (
                            incident_form_id INT PRIMARY KEY,
                            caller_name      VARCHAR(255),
                            agent_name       VARCHAR(255),
                            audio_filename   TEXT,
                            form_data        JSONB NOT NULL DEFAULT '{}',
                            CONSTRAINT fk_info_form
                                FOREIGN KEY (incident_form_id) REFERENCES incident_form(id)
                                ON DELETE CASCADE
                        );

                        CREATE INDEX IF NOT EXISTS idx_transcription_form_id
                            ON incident_transcription (incident_form_id);
                        CREATE INDEX IF NOT EXISTS idx_transcription_lang
                            ON incident_transcription (lang_code);
                        CREATE INDEX IF NOT EXISTS idx_incident_form_file_id
                            ON incident_form (file_id);
                        """
                    )
                conn.commit()
            finally:
                self._release_connection(conn)
            self._log.info("Database tables for incident form pipeline are ready.")
        except Exception as exc:
            self._log.warning(
                "Could not initialise database (will retry on first write): %s", exc
            )

    def store_form(self, form: dict[str, Any], audio_filename: str) -> bool:
        """Backward-compatible entrypoint.

        New schema requires file linkage, so direct form-only writes are skipped.
        """
        self._log.warning(
            "store_form() is deprecated for current schema; use store_upload_with_form()."
        )
        return False

    def list_forms(
        self, limit: int, category: str | None = None, priority: str | None = None
    ) -> list[dict[str, Any]]:
        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                query = (
                    """
                    SELECT
                        f.id,
                        gi.form_data->>'form_id' AS form_id,
                        f.completed_at,
                        f.status,
                        f.category,
                        f.priority,
                        gi.caller_name,
                        gi.agent_name,
                        tr_orig.sentiment,
                        tr_orig.summary,
                        gi.audio_filename,
                        COALESCE(tr_orig.transcript_text, '') AS original_transcript,
                        COALESCE(tr_nl.transcript_text, '') AS dutch_transcript,
                        gi.form_data,
                        f.completed_at AS created_at
                    FROM incident_form f
                    LEFT JOIN incident_general_information gi
                        ON gi.incident_form_id = f.id
                    LEFT JOIN incident_transcription tr_orig
                        ON tr_orig.incident_form_id = f.id
                        AND tr_orig.lang_code <> 'nl'
                    LEFT JOIN incident_transcription tr_nl
                        ON tr_nl.incident_form_id = f.id
                        AND tr_nl.lang_code = 'nl'
                    WHERE 1=1
                    """
                )
                params: list[Any] = []
                if category:
                    query += " AND f.category = %s"
                    params.append(category)
                if priority:
                    query += " AND f.priority = %s"
                    params.append(priority)
                query += " ORDER BY f.completed_at DESC LIMIT %s"
                params.append(limit)
                cur.execute(query, params)
                rows = cur.fetchall()
        finally:
            self._release_connection(conn)

        forms: list[dict[str, Any]] = []
        for row in rows:
            form_entry = dict(row)
            for key in ("completed_at", "created_at"):
                if form_entry.get(key):
                    form_entry[key] = form_entry[key].isoformat()
            forms.append(form_entry)
        return forms

    def get_form(self, form_id: str) -> dict[str, Any] | None:
        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT
                        f.*,
                        gi.caller_name,
                        gi.agent_name,
                        gi.audio_filename,
                        gi.form_data
                    FROM incident_form f
                    JOIN incident_general_information gi
                      ON gi.incident_form_id = f.id
                    WHERE gi.form_data->>'form_id' = %s
                    """,
                    (form_id,),
                )
                row = cur.fetchone()
                if row:
                    cur.execute(
                        """
                        SELECT lang_code, transcript_text, summary, sentiment, created_at
                        FROM incident_transcription
                        WHERE incident_form_id = %s
                        ORDER BY created_at ASC
                        """,
                        (row["id"],),
                    )
                    transcriptions = cur.fetchall()
                else:
                    transcriptions = []
        finally:
            self._release_connection(conn)

        if row is None:
            return None

        result = dict(row)
        for key in ("completed_at", "created_at"):
            if result.get(key):
                result[key] = result[key].isoformat()
        for item in transcriptions:
            if item.get("created_at"):
                item["created_at"] = item["created_at"].isoformat()
        result["transcriptions"] = [dict(t) for t in transcriptions]
        return result

    def _get_or_create_storage_account(self, cur) -> int:
        cur.execute(
            "SELECT account_id FROM account WHERE account_email = %s",
            (self._config.storage_account_email,),
        )
        row = cur.fetchone()
        if row:
            return row[0]

        cur.execute(
            """
            INSERT INTO account (password, account_email)
            VALUES (%s, %s)
            RETURNING account_id
            """,
            (self._config.storage_account_password, self._config.storage_account_email),
        )
        return cur.fetchone()[0]

    def _get_or_create_file_type(self, cur, extension: str) -> int:
        cur.execute(
            "SELECT filetype_id FROM filetype WHERE filetypename = %s", (extension,)
        )
        row = cur.fetchone()
        if row:
            return row[0]

        cur.execute(
            """
            INSERT INTO filetype (filetypename)
            VALUES (%s)
            RETURNING filetype_id
            """,
            (extension,),
        )
        return cur.fetchone()[0]

    def store_storage_projection(
        self,
        audio_filename: str,
        audio_path: str,
        transcript_text: str,
        completed_at: str | None,
    ) -> bool:
        """Persist upload metadata and transcript into storage schema tables."""
        try:
            session_start = datetime.now(timezone.utc)
            session_end = session_start
            if completed_at:
                try:
                    session_end = datetime.fromisoformat(
                        completed_at.replace("Z", "+00:00")
                    )
                except ValueError:
                    self._log.warning(
                        "Could not parse completed_at '%s'; using current time.",
                        completed_at,
                    )

            extension = Path(audio_filename).suffix.lstrip(".").lower() or "unknown"
            transcript_chunks = [
                line.strip() for line in transcript_text.splitlines() if line.strip()
            ]
            if not transcript_chunks and transcript_text.strip():
                transcript_chunks = [transcript_text.strip()]

            conn = self.get_connection()
            try:
                with conn.cursor() as cur:
                    account_id = self._get_or_create_storage_account(cur)
                    file_type_id = self._get_or_create_file_type(cur, extension)

                    cur.execute(
                        """
                        INSERT INTO recordsession (starttime, endtime, accountid)
                        VALUES (%s, %s, %s)
                        RETURNING recordingsession_id
                        """,
                        (session_start, session_end, account_id),
                    )
                    recording_session_id = cur.fetchone()[0]

                    cur.execute(
                        """
                        INSERT INTO file (filetypeid, fileurl, recordingsession_id)
                        VALUES (%s, %s, %s)
                        RETURNING file_id
                        """,
                        (file_type_id, audio_path, recording_session_id),
                    )
                    file_id = cur.fetchone()[0]

                    for idx, chunk in enumerate(transcript_chunks):
                        cur.execute(
                            """
                            INSERT INTO transcriptchunk (file_id, chunk_index, content)
                            VALUES (%s, %s, %s)
                            """,
                            (file_id, idx, chunk),
                        )

                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                self._release_connection(conn)
            self._log.info(
                "Stored upload in storage schema for file %s.", audio_filename
            )
            return True
        except Exception as exc:
            self._log.error("Failed to store upload in storage schema: %s", exc)
            return False

    def store_upload_with_form(
        self,
        form: dict[str, Any],
        audio_filename: str,
        audio_path: str,
        transcript_text: str,
        completed_at: str | None,
        source_lang: str | None,
    ) -> dict[str, Any] | None:
        """Store storage projection + multilingual form data in one transaction."""

        try:
            session_start = datetime.now(timezone.utc)
            session_end = session_start
            if completed_at:
                try:
                    session_end = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
                except ValueError:
                    self._log.warning(
                        "Could not parse completed_at '%s'; using current time.",
                        completed_at,
                    )

            extension = Path(audio_filename).suffix.lstrip(".").lower() or "unknown"
            transcript_chunks = [
                line.strip() for line in transcript_text.splitlines() if line.strip()
            ]
            if not transcript_chunks and transcript_text.strip():
                transcript_chunks = [transcript_text.strip()]

            translated_nl = form.get("translated_nl") if isinstance(form, dict) else None
            if not isinstance(translated_nl, dict):
                translated_nl = {}

            original_lang = (source_lang or "und").strip().lower()[:10] or "und"
            if original_lang == "nl":
                original_lang = "orig"

            conn = self.get_connection()
            try:
                with conn.cursor() as cur:
                    account_id = self._get_or_create_storage_account(cur)
                    file_type_id = self._get_or_create_file_type(cur, extension)

                    cur.execute(
                        """
                        INSERT INTO recordsession (starttime, endtime, accountid)
                        VALUES (%s, %s, %s)
                        RETURNING recordingsession_id
                        """,
                        (session_start, session_end, account_id),
                    )
                    recording_session_id = cur.fetchone()[0]

                    cur.execute(
                        """
                        INSERT INTO file (filetypeid, fileurl, recordingsession_id)
                        VALUES (%s, %s, %s)
                        RETURNING file_id
                        """,
                        (file_type_id, audio_path, recording_session_id),
                    )
                    file_id = cur.fetchone()[0]

                    for idx, chunk in enumerate(transcript_chunks):
                        cur.execute(
                            """
                            INSERT INTO transcriptchunk (file_id, chunk_index, content)
                            VALUES (%s, %s, %s)
                            """,
                            (file_id, idx, chunk),
                        )

                    cur.execute(
                        """
                        INSERT INTO incident_form (file_id, status, category, priority, completed_at)
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            file_id,
                            form.get("status", "completed"),
                            form.get("issue", {}).get("category"),
                            form.get("issue", {}).get("priority"),
                            form.get("completed_at"),
                        ),
                    )
                    incident_form_id = cur.fetchone()[0]

                    cur.execute(
                        """
                        INSERT INTO incident_general_information
                            (incident_form_id, caller_name, agent_name, audio_filename, form_data)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (
                            incident_form_id,
                            form.get("caller_information", {}).get("name"),
                            form.get("call_details", {}).get("agent_name"),
                            audio_filename,
                            psycopg2.extras.Json(form),
                        ),
                    )

                    cur.execute(
                        """
                        INSERT INTO incident_transcription
                            (incident_form_id, lang_code, transcript_text, summary, sentiment)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (
                            incident_form_id,
                            original_lang,
                            transcript_text,
                            form.get("call_summary"),
                            form.get("customer_sentiment"),
                        ),
                    )

                    if translated_nl.get("transcript_text") or translated_nl.get("call_summary"):
                        cur.execute(
                            """
                            INSERT INTO incident_transcription
                                (incident_form_id, lang_code, transcript_text, summary, sentiment)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (incident_form_id, lang_code) DO NOTHING
                            """,
                            (
                                incident_form_id,
                                "nl",
                                translated_nl.get("transcript_text"),
                                translated_nl.get("call_summary"),
                                form.get("customer_sentiment"),
                            ),
                        )

                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                self._release_connection(conn)

            self._log.info(
                "Stored upload + multilingual form for file %s (file_id=%s).",
                audio_filename,
                file_id,
            )
            return {
                "file_id": file_id,
                "recording_session_id": recording_session_id,
                "incident_form_id": incident_form_id,
                "incident_form_stored": True,
            }
        except Exception as exc:
            self._log.error("Failed to store upload+form transaction: %s", exc)
            return None
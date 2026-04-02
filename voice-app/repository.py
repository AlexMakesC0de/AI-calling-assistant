import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras

from config import AppConfig


class PostgresRepository:
    def __init__(self, config: AppConfig, log: logging.Logger):
        self._config = config
        self._log = log

    def get_connection(self):
        return psycopg2.connect(
            host=self._config.db_host,
            port=self._config.db_port,
            dbname=self._config.db_name,
            user=self._config.db_user,
            password=self._config.db_password,
        )

    def init_db(self) -> None:
        """Ensure application tables exist and are compatible with the current schema."""
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS incident_forms (
                        id              SERIAL PRIMARY KEY,
                        form_id         TEXT UNIQUE NOT NULL,
                        file_id         INT,
                        completed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        status          TEXT NOT NULL DEFAULT 'completed',
                        category        TEXT,
                        priority        TEXT,
                        caller_name     TEXT,
                        agent_name      TEXT,
                        sentiment       TEXT,
                        summary         TEXT,
                        audio_filename  TEXT,
                        form_data       JSONB NOT NULL,
                        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )

                cur.execute("ALTER TABLE incident_forms ADD COLUMN IF NOT EXISTS file_id INT")

                cur.execute("SELECT COUNT(*) FROM incident_forms WHERE file_id IS NULL")
                null_count = cur.fetchone()[0]
                if null_count == 0:
                    cur.execute(
                        "ALTER TABLE incident_forms ALTER COLUMN file_id SET NOT NULL"
                    )
                else:
                    self._log.warning(
                        "incident_forms has %s rows with NULL file_id; leaving column nullable.",
                        null_count,
                    )

                cur.execute(
                    "ALTER TABLE incident_forms DROP CONSTRAINT IF EXISTS fk_incident_forms_file"
                )
                cur.execute(
                    """
                    ALTER TABLE incident_forms
                        ADD CONSTRAINT fk_incident_forms_file
                        FOREIGN KEY (file_id) REFERENCES file(file_id)
                        ON DELETE RESTRICT
                    """
                )

                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_incident_forms_form_id ON incident_forms (form_id)"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_incident_forms_file_id ON incident_forms (file_id)"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_incident_forms_category ON incident_forms (category)"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_incident_forms_created_at ON incident_forms (created_at DESC)"
                )
            conn.commit()
            conn.close()
            self._log.info("Database table 'incident_forms' ready.")
        except Exception as exc:
            self._log.warning(
                "Could not initialise database (will retry on first write): %s", exc
            )

    def store_form(
        self,
        form: dict[str, Any],
        audio_filename: str,
        file_id: int | None = None,
    ) -> bool:
        """Persist a completed incident form to PostgreSQL."""
        if file_id is None:
            self._log.error(
                "Refusing to store form %s without file_id; storage projection missing.",
                form.get("form_id"),
            )
            return False
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO incident_forms
                        (form_id, file_id, completed_at, status, category, priority,
                         caller_name, agent_name, sentiment, summary,
                         audio_filename, form_data)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (form_id) DO UPDATE
                    SET file_id = COALESCE(incident_forms.file_id, EXCLUDED.file_id)
                    """,
                    (
                        form.get("form_id"),
                        file_id,
                        form.get("completed_at"),
                        form.get("status", "completed"),
                        form.get("issue", {}).get("category"),
                        form.get("issue", {}).get("priority"),
                        form.get("caller_information", {}).get("name"),
                        form.get("call_details", {}).get("agent_name"),
                        form.get("customer_sentiment"),
                        form.get("call_summary"),
                        audio_filename,
                        psycopg2.extras.Json(form),
                    ),
                )
            conn.commit()
            conn.close()
            self._log.info("Stored form %s in database.", form.get("form_id"))
            return True
        except Exception as exc:
            self._log.error("Failed to store form in database: %s", exc)
            return False

    def store_upload_with_form(
        self,
        form: dict[str, Any],
        audio_filename: str,
        audio_path: str,
        transcript_text: str,
        completed_at: str | None,
    ) -> dict[str, Any] | None:
        """Store storage projection + incident form in a single transaction.

        This guarantees that the `incident_forms.file_id` always points to an
        existing `file.file_id` from the same commit.
        """

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
                        INSERT INTO incident_forms
                            (form_id, file_id, completed_at, status, category, priority,
                             caller_name, agent_name, sentiment, summary,
                             audio_filename, form_data)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (form_id) DO UPDATE
                        SET file_id = COALESCE(incident_forms.file_id, EXCLUDED.file_id)
                        """,
                        (
                            form.get("form_id"),
                            file_id,
                            form.get("completed_at"),
                            form.get("status", "completed"),
                            form.get("issue", {}).get("category"),
                            form.get("issue", {}).get("priority"),
                            form.get("caller_information", {}).get("name"),
                            form.get("call_details", {}).get("agent_name"),
                            form.get("customer_sentiment"),
                            form.get("call_summary"),
                            audio_filename,
                            psycopg2.extras.Json(form),
                        ),
                    )

                conn.commit()
            finally:
                conn.close()

            self._log.info(
                "Stored upload + form transaction for file %s (file_id=%s).",
                audio_filename,
                file_id,
            )
            return {
                "file_id": file_id,
                "recording_session_id": recording_session_id,
                "incident_form_stored": True,
            }
        except Exception as exc:
            self._log.error("Failed to store upload+form transaction: %s", exc)
            return None

    def list_forms(
        self, limit: int, category: str | None = None, priority: str | None = None
    ) -> list[dict[str, Any]]:
        conn = self.get_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            query = (
                """SELECT id, form_id, file_id, completed_at, status, category,
                          priority, caller_name, agent_name, sentiment,
                          summary, audio_filename, created_at
                   FROM incident_forms WHERE 1=1"""
            )
            params: list[Any] = []
            if category:
                query += " AND category = %s"
                params.append(category)
            if priority:
                query += " AND priority = %s"
                params.append(priority)
            query += " ORDER BY created_at DESC LIMIT %s"
            params.append(limit)
            cur.execute(query, params)
            rows = cur.fetchall()
        conn.close()

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
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM incident_forms WHERE form_id = %s", (form_id,))
            row = cur.fetchone()
        conn.close()

        if row is None:
            return None

        result = dict(row)
        for key in ("completed_at", "created_at"):
            if result.get(key):
                result[key] = result[key].isoformat()
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
    ) -> dict[str, int] | None:
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
            conn.close()
            self._log.info(
                "Stored upload in storage schema for file %s.", audio_filename
            )
            return {"file_id": file_id, "recording_session_id": recording_session_id}
        except Exception as exc:
            self._log.error("Failed to store upload in storage schema: %s", exc)
            return None
-- Per-user Outlook OAuth tokens.
-- Each dashboard account can connect their own Microsoft 365 mailbox
-- via the authorization code flow (delegated permissions).

CREATE TABLE IF NOT EXISTS outlook_token (
    id              SERIAL PRIMARY KEY,
    account_id      INT           NOT NULL UNIQUE,
    access_token    TEXT          NOT NULL,
    refresh_token   TEXT          NOT NULL,
    expires_at      TIMESTAMPTZ   NOT NULL,
    mailbox_email   VARCHAR(255)  NOT NULL,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_outlook_token_account
        FOREIGN KEY (account_id) REFERENCES account(id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_outlook_token_account ON outlook_token(account_id);

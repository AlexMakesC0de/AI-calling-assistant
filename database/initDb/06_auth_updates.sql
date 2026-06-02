-- Add role and name columns to the account table for authentication.
-- Applied automatically after earlier init scripts thanks to the 06_ prefix.

ALTER TABLE account ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'user';
ALTER TABLE account ADD COLUMN IF NOT EXISTS name VARCHAR(255);

-- Repak super-admin account (password: "admin" — change after first login)
INSERT INTO account (password, account_email, role, name)
VALUES (
  '$2b$10$x.HXZ8RxcDaGOJjoio7F8eSypoCKO.lt2jcDYcxIkSoXu1w4QL86O',
  'admin@repak.ie',
  'super_admin',
  'Repak Admin'
) ON CONFLICT (account_email) DO NOTHING;

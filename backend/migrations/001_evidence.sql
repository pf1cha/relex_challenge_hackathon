CREATE TABLE IF NOT EXISTS schema_migrations(version integer PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS users(
 id text PRIMARY KEY, email text NOT NULL UNIQUE, display_name text NOT NULL,
 password_hash text NOT NULL, active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS sessions(
 id text PRIMARY KEY, user_id text NOT NULL REFERENCES users(id), token_hash text NOT NULL UNIQUE,
 csrf_hash text NOT NULL, csrf_token text NOT NULL, expires_at timestamptz NOT NULL, revoked boolean NOT NULL DEFAULT false
);
CREATE TABLE IF NOT EXISTS projects(
 id text PRIMARY KEY, name text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 data jsonb NOT NULL CHECK(jsonb_typeof(data)='object')
);
-- A project row is the short transactional serialization boundary. Every canonical
-- object includes its project lineage; all writes enforce typed DTO/version references
-- before committing. Restricted preprocessing inventory is never projected publicly.
CREATE INDEX IF NOT EXISTS projects_data_gin ON projects USING gin(data jsonb_path_ops);
INSERT INTO schema_migrations(version) VALUES(1) ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS users (id text PRIMARY KEY, username text UNIQUE NOT NULL, password_hash text NOT NULL);
CREATE TABLE IF NOT EXISTS sessions (token_hash text PRIMARY KEY, user_id text REFERENCES users(id), expires timestamptz NOT NULL);
CREATE TABLE IF NOT EXISTS projects (id text PRIMARY KEY, name text NOT NULL, generation bigint NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS memberships (project_id text REFERENCES projects(id), user_id text REFERENCES users(id), role text CHECK(role IN ('admin','member')), PRIMARY KEY(project_id,user_id));
CREATE TABLE IF NOT EXISTS artifacts (id text PRIMARY KEY, project_id text REFERENCES projects(id), kind text NOT NULL, data jsonb NOT NULL);
CREATE INDEX IF NOT EXISTS artifacts_project_kind ON artifacts(project_id,kind);
CREATE INDEX IF NOT EXISTS artifacts_data ON artifacts USING gin(data);

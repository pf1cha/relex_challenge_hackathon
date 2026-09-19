-- Revision 2: normalized authority and a separately privilegeable raw/privacy schema.
CREATE SCHEMA IF NOT EXISTS {restricted};

CREATE TABLE IF NOT EXISTS project_state(
 project_id text PRIMARY KEY REFERENCES projects(id) ON DELETE RESTRICT,
 corpus_generation integer NOT NULL DEFAULT 0 CHECK(corpus_generation >= 0),
 privacy_generation integer NOT NULL DEFAULT 0 CHECK(privacy_generation >= 0),
 lifecycle_revision integer NOT NULL DEFAULT 0 CHECK(lifecycle_revision >= 0),
 reservation integer NOT NULL DEFAULT 0 CHECK(reservation >= 0),
 write_barrier boolean NOT NULL DEFAULT false,
 overview jsonb,
 updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS project_memberships(
 project_id text NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
 user_id text NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 role text NOT NULL CHECK(role IN ('member','admin')),
 access_revision integer NOT NULL CHECK(access_revision >= 0),
 granted_at timestamptz NOT NULL,
 PRIMARY KEY(project_id,user_id)
);
CREATE TABLE IF NOT EXISTS project_access_epochs(
 project_id text NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
 user_id text NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 access_revision integer NOT NULL CHECK(access_revision >= 0),
 PRIMARY KEY(project_id,user_id)
);
CREATE TABLE IF NOT EXISTS documents(
 id text PRIMARY KEY,
 project_id text NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
 title text NOT NULL,
 record_type text NOT NULL CHECK(record_type IN ('email','transcript','report','specification')),
 ai_status text NOT NULL CHECK(ai_status IN ('active','inactive')),
 processing_state text NOT NULL CHECK(processing_state IN ('pending','running','completed','failed')),
 latest_job_id text,
 deleted boolean NOT NULL DEFAULT false,
 created_at timestamptz NOT NULL,
 updated_at timestamptz NOT NULL,
 payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object')
);
CREATE TABLE IF NOT EXISTS records(
 id text PRIMARY KEY,
 project_id text NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
 document_id text NOT NULL REFERENCES documents(id) ON DELETE RESTRICT,
 current_version integer NOT NULL CHECK(current_version >= 1),
 record_type text NOT NULL,
 created_at timestamptz NOT NULL,
 UNIQUE(project_id,id)
);
CREATE TABLE IF NOT EXISTS record_versions(
 project_id text NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
 record_id text NOT NULL REFERENCES records(id) ON DELETE RESTRICT,
 version integer NOT NULL CHECK(version >= 1),
 title text NOT NULL,
 source_time jsonb NOT NULL,
 person_ids jsonb NOT NULL DEFAULT '[]',
 published boolean NOT NULL DEFAULT false,
 quarantined boolean NOT NULL DEFAULT true,
 duplicate_of text,
 payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
 created_at timestamptz NOT NULL,
 PRIMARY KEY(project_id,record_id,version)
);
CREATE TABLE IF NOT EXISTS record_spans(
 project_id text NOT NULL,
 record_id text NOT NULL,
 record_version integer NOT NULL,
 span_id text NOT NULL,
 ordinal integer NOT NULL CHECK(ordinal >= 0),
 text text NOT NULL,
 source_location jsonb NOT NULL,
 PRIMARY KEY(project_id,record_id,record_version,span_id),
 UNIQUE(project_id,record_id,record_version,ordinal),
 FOREIGN KEY(project_id,record_id,record_version) REFERENCES record_versions(project_id,record_id,version) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS jobs(
 id text PRIMARY KEY,
 project_id text NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
 kind text NOT NULL,
 state text NOT NULL,
 stage text NOT NULL,
 lifecycle_revision integer NOT NULL CHECK(lifecycle_revision >= 0),
 lease_token text,
 expires_at timestamptz,
 payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
 created_at timestamptz NOT NULL,
 updated_at timestamptz NOT NULL
);
CREATE TABLE IF NOT EXISTS index_operations(
 id text PRIMARY KEY,
 job_id text NOT NULL REFERENCES jobs(id) ON DELETE RESTRICT,
 project_id text NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
 action text NOT NULL CHECK(action IN ('upsert','delete')),
 state text NOT NULL,
 lifecycle_revision integer NOT NULL,
 entry_ids jsonb NOT NULL DEFAULT '[]',
 outcome jsonb,
 payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
 created_at timestamptz NOT NULL DEFAULT now()
);

-- Each named domain collection has independent row identity; JSON is bounded to
-- one entity rather than an authoritative project-wide graph.
CREATE TABLE IF NOT EXISTS memory_artifacts(project_id text NOT NULL REFERENCES projects(id),object_key text NOT NULL,payload jsonb NOT NULL,PRIMARY KEY(project_id,object_key));
CREATE TABLE IF NOT EXISTS source_chunks(project_id text NOT NULL REFERENCES projects(id),object_key text NOT NULL,payload jsonb NOT NULL,PRIMARY KEY(project_id,object_key));
CREATE TABLE IF NOT EXISTS index_entries(project_id text NOT NULL REFERENCES projects(id),object_key text NOT NULL,payload jsonb NOT NULL,PRIMARY KEY(project_id,object_key));
CREATE TABLE IF NOT EXISTS history_events(project_id text NOT NULL REFERENCES projects(id),object_key text NOT NULL,payload jsonb NOT NULL,PRIMARY KEY(project_id,object_key));
CREATE TABLE IF NOT EXISTS artifact_checkpoints(project_id text NOT NULL REFERENCES projects(id),object_key text NOT NULL,payload jsonb NOT NULL,PRIMARY KEY(project_id,object_key));
CREATE TABLE IF NOT EXISTS conversations(project_id text NOT NULL REFERENCES projects(id),object_key text NOT NULL,payload jsonb NOT NULL,PRIMARY KEY(project_id,object_key));
CREATE TABLE IF NOT EXISTS messages(project_id text NOT NULL REFERENCES projects(id),object_key text NOT NULL,payload jsonb NOT NULL,PRIMARY KEY(project_id,object_key));
CREATE TABLE IF NOT EXISTS chat_attempts(project_id text NOT NULL REFERENCES projects(id),object_key text NOT NULL,payload jsonb NOT NULL,PRIMARY KEY(project_id,object_key));
CREATE TABLE IF NOT EXISTS answers(project_id text NOT NULL REFERENCES projects(id),object_key text NOT NULL,payload jsonb NOT NULL,PRIMARY KEY(project_id,object_key));
CREATE TABLE IF NOT EXISTS rebuild_plans(project_id text NOT NULL REFERENCES projects(id),object_key text NOT NULL,payload jsonb NOT NULL,PRIMARY KEY(project_id,object_key));
CREATE TABLE IF NOT EXISTS job_capabilities(project_id text NOT NULL REFERENCES projects(id),object_key text NOT NULL,payload jsonb NOT NULL,PRIMARY KEY(project_id,object_key));
CREATE TABLE IF NOT EXISTS record_dependencies(
 project_id text NOT NULL REFERENCES projects(id),owner_id text NOT NULL,owner_kind text NOT NULL,
 record_id text NOT NULL REFERENCES records(id),record_version integer NOT NULL,span_ids jsonb NOT NULL,
 PRIMARY KEY(project_id,owner_id,owner_kind,record_id,record_version),
 FOREIGN KEY(project_id,record_id,record_version) REFERENCES record_versions(project_id,record_id,version)
);

CREATE TABLE IF NOT EXISTS {restricted}.restricted_document_inputs(
 document_id text PRIMARY KEY REFERENCES documents(id) ON DELETE RESTRICT,
 project_id text NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
 raw_filename text NOT NULL,raw_content text NOT NULL
);
CREATE TABLE IF NOT EXISTS {restricted}.restricted_record_inputs(
 project_id text NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
 record_id text NOT NULL REFERENCES records(id) ON DELETE RESTRICT,
 record_version integer NOT NULL,source_hash text NOT NULL,raw_spans jsonb NOT NULL,
 PRIMARY KEY(project_id,record_id,record_version),
 FOREIGN KEY(project_id,record_id,record_version) REFERENCES record_versions(project_id,record_id,version)
);
CREATE TABLE IF NOT EXISTS {restricted}.restricted_identities(
 id text PRIMARY KEY,project_id text NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
 display_name text NOT NULL,kind text NOT NULL,state text NOT NULL,contacts jsonb NOT NULL DEFAULT '[]',
 payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(project_id,id)
);
CREATE TABLE IF NOT EXISTS {restricted}.restricted_identity_aliases(
 alias_key text PRIMARY KEY,identity_id text NOT NULL REFERENCES {restricted}.restricted_identities(id) ON DELETE RESTRICT,
 project_id text NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,alias text NOT NULL,evidence jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS {restricted}.restricted_privacy_runs(
 id text PRIMARY KEY,project_id text NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
 job_id text REFERENCES jobs(id) ON DELETE RESTRICT,record_id text NOT NULL REFERENCES records(id) ON DELETE RESTRICT,
 record_version integer NOT NULL,source_hash text NOT NULL,policy_version text NOT NULL,prompt_version text NOT NULL,
 model_version text NOT NULL,state text NOT NULL,coverage jsonb NOT NULL,edit_plan jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(project_id,record_id,record_version) REFERENCES record_versions(project_id,record_id,version)
);
CREATE TABLE IF NOT EXISTS {restricted}.restricted_privacy_occurrences(
 id text PRIMARY KEY,run_id text NOT NULL REFERENCES {restricted}.restricted_privacy_runs(id) ON DELETE RESTRICT,
 project_id text NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,identity_id text,
 record_id text NOT NULL,record_version integer NOT NULL,span_id text NOT NULL,start_offset integer NOT NULL,
 end_offset integer NOT NULL,risk_kind text NOT NULL,resolution_state text NOT NULL DEFAULT 'pending',evidence jsonb NOT NULL,
 FOREIGN KEY(project_id,record_id,record_version,span_id) REFERENCES record_spans(project_id,record_id,record_version,span_id)
);
CREATE TABLE IF NOT EXISTS {restricted}.restricted_privacy_metadata_occurrences(
 id text PRIMARY KEY,run_id text NOT NULL REFERENCES {restricted}.restricted_privacy_runs(id) ON DELETE RESTRICT,
 project_id text NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,identity_id text,
 record_id text NOT NULL,record_version integer NOT NULL,field_name text NOT NULL,start_offset integer NOT NULL,
 end_offset integer NOT NULL,risk_kind text NOT NULL,resolution_state text NOT NULL DEFAULT 'pending',evidence jsonb NOT NULL,
 FOREIGN KEY(project_id,record_id,record_version) REFERENCES record_versions(project_id,record_id,version)
);
CREATE TABLE IF NOT EXISTS {restricted}.restricted_privacy_diagnostics(
 id text PRIMARY KEY,project_id text NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
 record_id text NOT NULL,record_version integer NOT NULL,span_id text NOT NULL,state text NOT NULL,payload jsonb NOT NULL,
 FOREIGN KEY(project_id,record_id,record_version,span_id) REFERENCES record_spans(project_id,record_id,record_version,span_id)
);
CREATE TABLE IF NOT EXISTS {restricted}.restricted_privacy_metadata_diagnostics(
 id text PRIMARY KEY,project_id text NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
 record_id text NOT NULL,record_version integer NOT NULL,field_name text NOT NULL,state text NOT NULL,payload jsonb NOT NULL,
 FOREIGN KEY(project_id,record_id,record_version) REFERENCES record_versions(project_id,record_id,version)
);
CREATE TABLE IF NOT EXISTS {restricted}.restricted_privacy_resolutions(
 id text PRIMARY KEY,project_id text NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
 occurrence_id text REFERENCES {restricted}.restricted_privacy_occurrences(id) ON DELETE RESTRICT,
 admin_user_id text NOT NULL REFERENCES users(id) ON DELETE RESTRICT,decision text NOT NULL,rationale text NOT NULL,
 source_version integer NOT NULL,payload jsonb NOT NULL,created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS erasure_tombstones(
 id text PRIMARY KEY,project_id text NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
 identity_id text NOT NULL,completed_at timestamptz NOT NULL,inventory jsonb NOT NULL
);

CREATE INDEX IF NOT EXISTS records_project_idx ON records(project_id,document_id,current_version);
CREATE INDEX IF NOT EXISTS jobs_project_state_idx ON jobs(project_id,state,stage);
CREATE INDEX IF NOT EXISTS restricted_privacy_runs_record_idx ON {restricted}.restricted_privacy_runs(project_id,record_id,record_version);
REVOKE ALL ON SCHEMA {restricted} FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA {restricted} FROM PUBLIC;
INSERT INTO schema_migrations(version) VALUES(2) ON CONFLICT DO NOTHING;

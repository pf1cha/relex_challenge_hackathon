-- Revision 4: typed scoped ownership/reference edges and dependency authority.
ALTER TABLE jobs ADD CONSTRAINT jobs_project_id_unique UNIQUE(project_id,id);
ALTER TABLE documents ADD CONSTRAINT documents_project_id_unique UNIQUE(project_id,id);
CREATE TABLE IF NOT EXISTS project_principals(
 project_id text NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
 user_id text NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 PRIMARY KEY(project_id,user_id)
);
INSERT INTO project_principals(project_id,user_id)
SELECT project_id,user_id FROM project_memberships ON CONFLICT DO NOTHING;
INSERT INTO project_principals(project_id,user_id)
SELECT project_id,user_id FROM project_access_epochs ON CONFLICT DO NOTHING;
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS owner_user_id text;
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS created_at timestamptz;
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS updated_at timestamptz;
UPDATE conversations SET owner_user_id=payload->>'owner_user_id',created_at=(payload->>'created_at')::timestamptz,
 updated_at=(payload->>'updated_at')::timestamptz WHERE owner_user_id IS NULL;
ALTER TABLE conversations ALTER COLUMN owner_user_id SET NOT NULL;
ALTER TABLE conversations ALTER COLUMN created_at SET NOT NULL;
ALTER TABLE conversations ALTER COLUMN updated_at SET NOT NULL;
ALTER TABLE conversations ADD CONSTRAINT conversations_owner_fk FOREIGN KEY(project_id,owner_user_id)
 REFERENCES project_principals(project_id,user_id) ON DELETE RESTRICT;

ALTER TABLE messages ADD COLUMN IF NOT EXISTS conversation_id text;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS role text;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS state text;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS answer_id text;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS created_at timestamptz;
UPDATE messages SET conversation_id=payload->>'conversation_id',role=payload->>'role',state=payload->>'state',
 answer_id=payload->>'answer_id',created_at=(payload->>'created_at')::timestamptz WHERE conversation_id IS NULL;
ALTER TABLE messages ALTER COLUMN conversation_id SET NOT NULL;
ALTER TABLE messages ALTER COLUMN role SET NOT NULL;
ALTER TABLE messages ALTER COLUMN state SET NOT NULL;
ALTER TABLE messages ALTER COLUMN created_at SET NOT NULL;
ALTER TABLE messages ADD CONSTRAINT messages_conversation_fk FOREIGN KEY(project_id,conversation_id)
 REFERENCES conversations(project_id,object_key) ON DELETE RESTRICT;

ALTER TABLE answers ADD COLUMN IF NOT EXISTS conversation_id text;
ALTER TABLE answers ADD COLUMN IF NOT EXISTS request_id text;
ALTER TABLE answers ADD COLUMN IF NOT EXISTS created_at timestamptz;
ALTER TABLE answers ADD COLUMN IF NOT EXISTS valid boolean;
UPDATE answers SET conversation_id=payload->'data'->>'conversation_id',request_id=payload->'data'->>'request_id',
 created_at=(payload->'data'->>'created_at')::timestamptz,valid=COALESCE((payload->>'valid')::boolean,false)
 WHERE conversation_id IS NULL;
ALTER TABLE answers ALTER COLUMN conversation_id SET NOT NULL;
ALTER TABLE answers ALTER COLUMN request_id SET NOT NULL;
ALTER TABLE answers ALTER COLUMN created_at SET NOT NULL;
ALTER TABLE answers ALTER COLUMN valid SET NOT NULL;
ALTER TABLE answers ADD CONSTRAINT answers_conversation_fk FOREIGN KEY(project_id,conversation_id)
 REFERENCES conversations(project_id,object_key) ON DELETE RESTRICT;
ALTER TABLE messages ADD CONSTRAINT messages_answer_fk FOREIGN KEY(project_id,answer_id)
 REFERENCES answers(project_id,object_key) ON DELETE RESTRICT;

ALTER TABLE chat_attempts ADD COLUMN IF NOT EXISTS conversation_id text;
ALTER TABLE chat_attempts ADD COLUMN IF NOT EXISTS message_id text;
ALTER TABLE chat_attempts ADD COLUMN IF NOT EXISTS owner_user_id text;
ALTER TABLE chat_attempts ADD COLUMN IF NOT EXISTS state text;
UPDATE chat_attempts SET conversation_id=payload->'attempt'->>'conversation_id',message_id=payload->>'message_id',
 owner_user_id=payload->>'owner',state=payload->>'state' WHERE conversation_id IS NULL;
ALTER TABLE chat_attempts ALTER COLUMN conversation_id SET NOT NULL;
ALTER TABLE chat_attempts ALTER COLUMN message_id SET NOT NULL;
ALTER TABLE chat_attempts ALTER COLUMN owner_user_id SET NOT NULL;
ALTER TABLE chat_attempts ALTER COLUMN state SET NOT NULL;
ALTER TABLE chat_attempts ADD CONSTRAINT attempts_conversation_fk FOREIGN KEY(project_id,conversation_id)
 REFERENCES conversations(project_id,object_key) ON DELETE RESTRICT;
ALTER TABLE chat_attempts ADD CONSTRAINT attempts_message_fk FOREIGN KEY(project_id,message_id)
 REFERENCES messages(project_id,object_key) ON DELETE RESTRICT;
ALTER TABLE chat_attempts ADD CONSTRAINT attempts_owner_fk FOREIGN KEY(project_id,owner_user_id)
 REFERENCES project_principals(project_id,user_id) ON DELETE RESTRICT;

ALTER TABLE artifact_checkpoints ADD COLUMN IF NOT EXISTS job_id text;
ALTER TABLE artifact_checkpoints ADD COLUMN IF NOT EXISTS artifact_key text;
UPDATE artifact_checkpoints SET job_id=payload->'batch'->>'job_id',artifact_key=payload->>'artifact_key' WHERE job_id IS NULL;
ALTER TABLE artifact_checkpoints ALTER COLUMN job_id SET NOT NULL;
ALTER TABLE artifact_checkpoints ALTER COLUMN artifact_key SET NOT NULL;
ALTER TABLE artifact_checkpoints ADD CONSTRAINT checkpoints_job_fk FOREIGN KEY(project_id,job_id)
 REFERENCES jobs(project_id,id) ON DELETE RESTRICT;

CREATE TABLE IF NOT EXISTS job_documents(
 project_id text NOT NULL,job_id text NOT NULL,document_id text NOT NULL,
 PRIMARY KEY(project_id,job_id,document_id),
 FOREIGN KEY(project_id,job_id) REFERENCES jobs(project_id,id) ON DELETE RESTRICT,
 FOREIGN KEY(project_id,document_id) REFERENCES documents(project_id,id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS job_record_versions(
 project_id text NOT NULL,job_id text NOT NULL,record_id text NOT NULL,record_version integer NOT NULL,
 PRIMARY KEY(project_id,job_id,record_id,record_version),
 FOREIGN KEY(project_id,job_id) REFERENCES jobs(project_id,id) ON DELETE RESTRICT,
 FOREIGN KEY(project_id,record_id,record_version) REFERENCES record_versions(project_id,record_id,version) ON DELETE RESTRICT
);
INSERT INTO job_documents(project_id,job_id,document_id)
SELECT j.project_id,j.id,value #>> '{}' FROM jobs j
CROSS JOIN LATERAL jsonb_array_elements(j.payload->'work'->'document_ids') value
JOIN documents d ON d.project_id=j.project_id AND d.id=value #>> '{}'
ON CONFLICT DO NOTHING;
INSERT INTO job_record_versions(project_id,job_id,record_id,record_version)
SELECT j.project_id,j.id,value->>'record_id',(value->>'record_version')::integer
FROM jobs j CROSS JOIN LATERAL jsonb_array_elements(j.payload->'work'->'record_versions') value
JOIN record_versions r ON r.project_id=j.project_id AND r.record_id=value->>'record_id' AND r.version=(value->>'record_version')::integer
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS receipts(
 project_id text NOT NULL,receipt_id text NOT NULL,answer_id text NOT NULL,record_id text NOT NULL,
 record_version integer NOT NULL,span_ids jsonb NOT NULL,
 PRIMARY KEY(project_id,receipt_id),
 FOREIGN KEY(project_id,answer_id) REFERENCES answers(project_id,object_key) ON DELETE RESTRICT,
 FOREIGN KEY(project_id,record_id,record_version) REFERENCES record_versions(project_id,record_id,version) ON DELETE RESTRICT
);
INSERT INTO receipts(project_id,receipt_id,answer_id,record_id,record_version,span_ids)
SELECT a.project_id,r->>'id',a.object_key,r->'evidence_ref'->>'record_id',
 (r->'evidence_ref'->>'record_version')::integer,r->'evidence_ref'->'span_ids'
FROM answers a CROSS JOIN LATERAL jsonb_array_elements(COALESCE(a.payload->'data'->'receipts','[]')) r
ON CONFLICT DO NOTHING;

INSERT INTO record_dependencies(project_id,owner_id,owner_kind,record_id,record_version,span_ids)
SELECT a.project_id,a.object_key,'answer',d->>'record_id',(d->>'record_version')::integer,d->'span_ids'
FROM answers a CROSS JOIN LATERAL jsonb_array_elements(COALESCE(a.payload->'dependencies','[]')) d
ON CONFLICT DO NOTHING;
INSERT INTO record_dependencies(project_id,owner_id,owner_kind,record_id,record_version,span_ids)
SELECT m.project_id,m.object_key,'memory',d->>'record_id',(d->>'record_version')::integer,d->'span_ids'
FROM memory_artifacts m CROSS JOIN LATERAL jsonb_array_elements(COALESCE(m.payload->'data'->'dependencies','[]')) d
ON CONFLICT DO NOTHING;
INSERT INTO record_dependencies(project_id,owner_id,owner_kind,record_id,record_version,span_ids)
SELECT c.project_id,c.object_key,'artifact',d->>'record_id',(d->>'record_version')::integer,d->'span_ids'
FROM artifact_checkpoints c CROSS JOIN LATERAL jsonb_array_elements(COALESCE(c.payload->'batch'->'dependencies','[]')) d
ON CONFLICT DO NOTHING;
INSERT INTO record_dependencies(project_id,owner_id,owner_kind,record_id,record_version,span_ids)
SELECT p.project_id,p.object_key,'rebuild_plan',d->>'record_id',(d->>'record_version')::integer,d->'span_ids'
FROM rebuild_plans p CROSS JOIN LATERAL jsonb_array_elements(COALESCE(p.payload->'dependencies','[]')) d
ON CONFLICT DO NOTHING;
INSERT INTO record_dependencies(project_id,owner_id,owner_kind,record_id,record_version,span_ids)
SELECT r.project_id,r.receipt_id,'receipt',r.record_id,r.record_version,r.span_ids FROM receipts r
ON CONFLICT DO NOTHING;
ALTER TABLE record_dependencies ADD CONSTRAINT record_dependencies_owner_kind_check
 CHECK(owner_kind IN ('answer','memory','artifact','receipt','rebuild_plan'));
ALTER TABLE record_dependencies ADD COLUMN IF NOT EXISTS answer_id text;
ALTER TABLE record_dependencies ADD COLUMN IF NOT EXISTS memory_id text;
ALTER TABLE record_dependencies ADD COLUMN IF NOT EXISTS artifact_id text;
ALTER TABLE record_dependencies ADD COLUMN IF NOT EXISTS receipt_id text;
ALTER TABLE record_dependencies ADD COLUMN IF NOT EXISTS rebuild_plan_id text;
UPDATE record_dependencies SET
 answer_id=CASE WHEN owner_kind='answer' THEN owner_id END,
 memory_id=CASE WHEN owner_kind='memory' THEN owner_id END,
 artifact_id=CASE WHEN owner_kind='artifact' THEN owner_id END,
 receipt_id=CASE WHEN owner_kind='receipt' THEN owner_id END,
 rebuild_plan_id=CASE WHEN owner_kind='rebuild_plan' THEN owner_id END;
ALTER TABLE record_dependencies ADD CONSTRAINT record_dependencies_one_owner_check CHECK(
 num_nonnulls(answer_id,memory_id,artifact_id,receipt_id,rebuild_plan_id)=1 AND
 (owner_kind='answer' AND answer_id=owner_id OR owner_kind='memory' AND memory_id=owner_id OR
  owner_kind='artifact' AND artifact_id=owner_id OR owner_kind='receipt' AND receipt_id=owner_id OR
  owner_kind='rebuild_plan' AND rebuild_plan_id=owner_id));
ALTER TABLE record_dependencies ADD CONSTRAINT dependencies_answer_fk FOREIGN KEY(project_id,answer_id)
 REFERENCES answers(project_id,object_key) ON DELETE RESTRICT;
ALTER TABLE record_dependencies ADD CONSTRAINT dependencies_memory_fk FOREIGN KEY(project_id,memory_id)
 REFERENCES memory_artifacts(project_id,object_key) ON DELETE RESTRICT;
ALTER TABLE record_dependencies ADD CONSTRAINT dependencies_artifact_fk FOREIGN KEY(project_id,artifact_id)
 REFERENCES artifact_checkpoints(project_id,object_key) ON DELETE RESTRICT;
ALTER TABLE record_dependencies ADD CONSTRAINT dependencies_receipt_fk FOREIGN KEY(project_id,receipt_id)
 REFERENCES receipts(project_id,receipt_id) ON DELETE RESTRICT;
ALTER TABLE record_dependencies ADD CONSTRAINT dependencies_rebuild_plan_fk FOREIGN KEY(project_id,rebuild_plan_id)
 REFERENCES rebuild_plans(project_id,object_key) ON DELETE RESTRICT;

INSERT INTO schema_migrations(version) VALUES(4) ON CONFLICT DO NOTHING;

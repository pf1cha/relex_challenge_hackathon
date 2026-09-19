-- Revision 3: idempotent backfill. Run on a restored clone before live cutover.
INSERT INTO project_state(project_id,corpus_generation,privacy_generation,lifecycle_revision,reservation,write_barrier,overview)
SELECT id,COALESCE((data->>'corpus_generation')::integer,0),COALESCE((data->>'privacy_generation')::integer,0),
 COALESCE((data->>'lifecycle_revision')::integer,0),COALESCE((data->>'reservation')::integer,0),
 COALESCE((data->>'write_barrier')::boolean,false),data->'overview' FROM projects
ON CONFLICT(project_id) DO NOTHING;

INSERT INTO project_memberships(project_id,user_id,role,access_revision,granted_at)
SELECT p.id,x.key,x.value->>'role',COALESCE((x.value->>'revision')::integer,0),COALESCE((x.value->>'granted_at')::timestamptz,p.created_at)
FROM projects p CROSS JOIN LATERAL jsonb_each(COALESCE(p.data->'members','{}')) x
ON CONFLICT(project_id,user_id) DO NOTHING;
INSERT INTO project_access_epochs(project_id,user_id,access_revision)
SELECT p.id,x.key,(x.value #>> '{}')::integer FROM projects p CROSS JOIN LATERAL jsonb_each(COALESCE(p.data->'access_epochs','{}')) x
ON CONFLICT(project_id,user_id) DO NOTHING;

INSERT INTO documents(id,project_id,title,record_type,ai_status,processing_state,latest_job_id,deleted,created_at,updated_at,payload)
SELECT x.value->>'id',p.id,COALESCE(x.value->>'title',''),COALESCE(x.value->>'record_type','report'),
 COALESCE(x.value->>'ai_status','active'),COALESCE(x.value->>'processing_state','pending'),x.value->>'latest_job_id',
 COALESCE((x.value->>'deleted')::boolean,false),COALESCE((x.value->>'created_at')::timestamptz,p.created_at),
 COALESCE((x.value->>'updated_at')::timestamptz,p.created_at),x.value-'raw'-'raw_filename'
FROM projects p CROSS JOIN LATERAL jsonb_each(COALESCE(p.data->'documents','{}')) x
ON CONFLICT(id) DO NOTHING;
INSERT INTO {restricted}.restricted_document_inputs(document_id,project_id,raw_filename,raw_content)
SELECT x.value->>'id',p.id,COALESCE(x.value->>'raw_filename',x.value->>'title'),x.value->>'raw'
FROM projects p CROSS JOIN LATERAL jsonb_each(COALESCE(p.data->'documents','{}')) x WHERE x.value ? 'raw'
ON CONFLICT(document_id) DO NOTHING;

INSERT INTO records(id,project_id,document_id,current_version,record_type,created_at)
SELECT x.value->>'record_id',p.id,x.value->>'original_doc_id',COALESCE((x.value->>'record_version')::integer,1),
 COALESCE(x.value->>'record_type','report'),COALESCE((x.value->>'created_at')::timestamptz,p.created_at)
FROM projects p CROSS JOIN LATERAL jsonb_each(COALESCE(p.data->'records','{}')) x
ON CONFLICT(id) DO NOTHING;
INSERT INTO record_versions(project_id,record_id,version,title,source_time,person_ids,published,quarantined,duplicate_of,payload,created_at)
SELECT p.id,x.value->>'record_id',COALESCE((x.value->>'record_version')::integer,1),COALESCE(x.value->>'title',''),
 COALESCE(x.value->'source_time','{}'),COALESCE(x.value->'person_ids','[]'),COALESCE((x.value->>'published')::boolean,false),
 COALESCE((x.value->>'quarantined')::boolean,true),x.value->>'duplicate_of',x.value-'raw_spans'-'source_hash',
 COALESCE((x.value->>'created_at')::timestamptz,p.created_at)
FROM projects p CROSS JOIN LATERAL jsonb_each(COALESCE(p.data->'records','{}')) x
ON CONFLICT(project_id,record_id,version) DO NOTHING;
INSERT INTO record_spans(project_id,record_id,record_version,span_id,ordinal,text,source_location)
SELECT r.project_id,r.id,r.current_version,s.value->>'span_id',COALESCE((s.value->>'ordinal')::integer,0),
 COALESCE(s.value->>'text',''),COALESCE(s.value->'source_location','{}')
FROM records r JOIN record_versions v ON v.project_id=r.project_id AND v.record_id=r.id AND v.version=r.current_version
CROSS JOIN LATERAL jsonb_array_elements(COALESCE(v.payload->'spans','[]')) s
ON CONFLICT(project_id,record_id,record_version,span_id) DO NOTHING;
INSERT INTO {restricted}.restricted_record_inputs(project_id,record_id,record_version,source_hash,raw_spans)
SELECT p.id,x.value->>'record_id',COALESCE((x.value->>'record_version')::integer,1),x.value->>'source_hash',x.value->'raw_spans'
FROM projects p CROSS JOIN LATERAL jsonb_each(COALESCE(p.data->'records','{}')) x
WHERE x.value ? 'raw_spans' AND x.value ? 'source_hash'
ON CONFLICT(project_id,record_id,record_version) DO NOTHING;

INSERT INTO jobs(id,project_id,kind,state,stage,lifecycle_revision,lease_token,expires_at,payload,created_at,updated_at)
SELECT x.value->'public'->>'id',p.id,x.value->'public'->>'kind',x.value->'public'->>'state',x.value->'public'->>'stage',
 COALESCE((x.value->>'lifecycle_revision')::integer,0),x.value->>'lease_token',(x.value->>'expires_at')::timestamptz,x.value,
 (x.value->'public'->>'created_at')::timestamptz,(x.value->'public'->>'updated_at')::timestamptz
FROM projects p CROSS JOIN LATERAL jsonb_each(COALESCE(p.data->'jobs','{}')) x
ON CONFLICT(id) DO NOTHING;
INSERT INTO index_operations(id,job_id,project_id,action,state,lifecycle_revision,entry_ids,outcome,payload)
SELECT x.value->'public'->>'id',x.value->'public'->>'job_id',p.id,x.value->'public'->>'action',x.value->'public'->>'state',
 COALESCE((x.value->'public'->>'lifecycle_revision')::integer,0),COALESCE(x.value->'public'->'entry_ids','[]'),x.value->'outcome',x.value
FROM projects p CROSS JOIN LATERAL jsonb_each(COALESCE(p.data->'operations','{}')) x
ON CONFLICT(id) DO NOTHING;

INSERT INTO memory_artifacts SELECT p.id,x.key,x.value FROM projects p CROSS JOIN LATERAL jsonb_each(COALESCE(p.data->'memories','{}')) x ON CONFLICT DO NOTHING;
INSERT INTO source_chunks SELECT p.id,x.key,x.value FROM projects p CROSS JOIN LATERAL jsonb_each(COALESCE(p.data->'chunks','{}')) x ON CONFLICT DO NOTHING;
INSERT INTO index_entries SELECT p.id,x.key,x.value FROM projects p CROSS JOIN LATERAL jsonb_each(COALESCE(p.data->'entries','{}')) x ON CONFLICT DO NOTHING;
INSERT INTO history_events SELECT p.id,x.key,x.value FROM projects p CROSS JOIN LATERAL jsonb_each(COALESCE(p.data->'history','{}')) x ON CONFLICT DO NOTHING;
INSERT INTO artifact_checkpoints SELECT p.id,x.key,x.value FROM projects p CROSS JOIN LATERAL jsonb_each(COALESCE(p.data->'checkpoints','{}')) x ON CONFLICT DO NOTHING;
INSERT INTO conversations SELECT p.id,x.key,x.value FROM projects p CROSS JOIN LATERAL jsonb_each(COALESCE(p.data->'conversations','{}')) x ON CONFLICT DO NOTHING;
INSERT INTO messages SELECT p.id,x.key,x.value FROM projects p CROSS JOIN LATERAL jsonb_each(COALESCE(p.data->'messages','{}')) x ON CONFLICT DO NOTHING;
INSERT INTO chat_attempts SELECT p.id,x.key,x.value FROM projects p CROSS JOIN LATERAL jsonb_each(COALESCE(p.data->'attempts','{}')) x ON CONFLICT DO NOTHING;
INSERT INTO answers SELECT p.id,x.key,x.value FROM projects p CROSS JOIN LATERAL jsonb_each(COALESCE(p.data->'answers','{}')) x ON CONFLICT DO NOTHING;
INSERT INTO rebuild_plans SELECT p.id,x.key,x.value FROM projects p CROSS JOIN LATERAL jsonb_each(COALESCE(p.data->'plans','{}')) x ON CONFLICT DO NOTHING;
INSERT INTO job_capabilities SELECT p.id,x.key,x.value FROM projects p CROSS JOIN LATERAL jsonb_each(COALESCE(p.data->'capabilities','{}')) x ON CONFLICT DO NOTHING;

INSERT INTO {restricted}.restricted_identities(id,project_id,display_name,kind,state,contacts,payload)
SELECT x.value->>'id',p.id,x.value->>'display_name',COALESCE(x.value->>'kind','client'),
 COALESCE(x.value->>'state','active'),COALESCE(x.value->'contacts','[]'),x.value
FROM projects p CROSS JOIN LATERAL jsonb_each(COALESCE(p.data->'people','{}')) x
ON CONFLICT(id) DO NOTHING;
INSERT INTO {restricted}.restricted_privacy_runs(id,project_id,record_id,record_version,source_hash,policy_version,prompt_version,model_version,state,coverage,edit_plan)
SELECT x.value->>'plan_id',p.id,x.value->>'record_id',(x.value->>'record_version')::integer,x.value->>'source_hash',
 x.value->>'policy_version',x.value->>'prompt_version',COALESCE(x.value->>'model_version','configured-model'),'completed',
 jsonb_build_object('covered_span_ids',x.value->'covered_span_ids','complete',x.value->'complete'),x.value
FROM projects p CROSS JOIN LATERAL jsonb_each(COALESCE(p.data->'privacy_plans','{}')) x
ON CONFLICT(id) DO NOTHING;
INSERT INTO {restricted}.restricted_privacy_diagnostics(id,project_id,record_id,record_version,span_id,state,payload)
SELECT x.value->>'id',p.id,x.value->>'record_id',(x.value->>'record_version')::integer,x.value->>'span_id',x.value->>'state',x.value
FROM projects p CROSS JOIN LATERAL jsonb_each(COALESCE(p.data->'privacy_diagnostics','{}')) x
ON CONFLICT(id) DO NOTHING;

INSERT INTO schema_migrations(version) VALUES(3) ON CONFLICT DO NOTHING;

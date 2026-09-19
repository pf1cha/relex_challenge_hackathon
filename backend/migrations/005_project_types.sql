ALTER TABLE project_state ADD COLUMN IF NOT EXISTS project_types jsonb NOT NULL DEFAULT $${"email":true,"transcript":true,"report":true,"specification":true}$$::jsonb;
ALTER TABLE documents DROP CONSTRAINT IF EXISTS documents_record_type_check;

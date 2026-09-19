// =========================================================================
// RELEX AGENT PLATFORM: RBAC & DECISION LEDGER SCHEMA (DBML)
// Visualizer: https://dbdiagram.io/d
// =========================================================================

Enum role_scope {
  SYSTEM
  PROJECT
}

Enum doc_type {
  MEETING
  EMAILS
  REPORTS
  SPECIFICATION
}

Enum doc_status {
  ACTIVE
  INACTIVE
  DELETED
}

Enum decision_status {
  PROPOSED
  AGREED
  REJECTED
  SUPERSEDED
  UNOWNED_RISK
}

Enum message_sender {
  USER
  ASSISTANT
  SYSTEM
}

Table organizations {
  id uuid [pk, default: `gen_random_uuid()`]
  name varchar(255) [not null]
  created_at timestamptz [default: `now()`]
}

Table projects {
  id uuid [pk, default: `gen_random_uuid()`]
  code varchar(50) [unique, not null]
  name varchar(255) [not null]
  description text
  organization_id uuid [ref: > organizations.id]
  created_at timestamptz [default: `now()`]
}

Table roles {
  id uuid [pk, default: `gen_random_uuid()`]
  code varchar(50) [unique, not null, note: "e.g. SYS_ADMIN, PRJ_LEAD, PRJ_VIEWER"]
  name varchar(100) [not null]
  scope role_scope [not null, note: "SYSTEM or PROJECT"]
  project_id uuid [ref: > projects.id, note: "NULL for global/system; Set for project-specific custom roles"]
  can_view_documents boolean [default: true]
  can_chat_ai boolean [default: true]
  can_view_visualizations boolean [default: true]
  can_manage_documents boolean [default: false]
  can_manage_roles boolean [default: false]
  description text
  created_at timestamptz [default: `now()`]
}

Table users {
  id uuid [pk, default: `gen_random_uuid()`]
  full_name varchar(255) [not null]
  initials varchar(10) [not null, note: "e.g. Ivanov Petr -> IP"]
  email varchar(255) [unique, not null]
  organization_id uuid [ref: > organizations.id]
  system_role_id uuid [not null, ref: > roles.id, note: "Points to SYSTEM scope role (Admin or Basic)"]
  is_active boolean [default: true]
  created_at timestamptz [default: `now()`]
}

Table user_project_roles {
  id uuid [pk, default: `gen_random_uuid()`]
  user_id uuid [not null, ref: > users.id]
  project_id uuid [not null, ref: > projects.id]
  role_id uuid [not null, ref: > roles.id, note: "Points to PROJECT scope role"]
  granted_by uuid [ref: > users.id]
  granted_at timestamptz [default: `now()`]

  indexes {
    (user_id, project_id, role_id) [unique]
  }
}

Table documents {
  id uuid [pk, default: `gen_random_uuid()`]
  project_id uuid [not null, ref: > projects.id]
  file_name varchar(255) [not null]
  document_link text [not null]
  summarised_version text [not null]
  type doc_type [not null]
  ai_status doc_status [default: "ACTIVE", note: "Admin/Lead controlled AI availability"]
  total_lines int [default: 0]
  created_at timestamptz [default: `now()`]
  updated_at timestamptz [default: `now()`]
}

Table document_chunks {
  id uuid [pk, default: `gen_random_uuid()`]
  document_id uuid [not null, ref: > documents.id]
  chunk_index int [not null]
  chunk_text text [not null]
  line_start int [not null]
  line_end int [not null]
  embedding vector(1536)
  created_at timestamptz [default: `now()`]
}

Table decision_ledger {
  id uuid [pk, default: `gen_random_uuid()`]
  document_id uuid [not null, ref: > documents.id]
  topic varchar(255) [not null]
  proposed_by_name varchar(255) [not null]
  proposed_date date [not null]
  approved_by_name varchar(255)
  approved_date date
  status decision_status [default: "PROPOSED"]
  superseded_by_id uuid [ref: > decision_ledger.id]
  verbatim_quote text [not null]
  line_start int [not null]
  line_end int [not null]
}

Table chat_conversations {
  id uuid [pk, default: `gen_random_uuid()`]
  user_id uuid [not null, ref: > users.id]
  project_id uuid [ref: > projects.id]
  title varchar(255) [default: "New Chat"]
  created_at timestamptz [default: `now()`]
  updated_at timestamptz [default: `now()`]
}

Table chat_messages {
  id uuid [pk, default: `gen_random_uuid()`]
  conversation_id uuid [not null, ref: > chat_conversations.id]
  sender message_sender [not null]
  content text [not null]
  unasked_initiative jsonb
  honesty_box text
  created_at timestamptz [default: `now()`]
}

Table chat_citations {
  id uuid [pk, default: `gen_random_uuid()`]
  message_id uuid [not null, ref: > chat_messages.id]
  document_id uuid [not null, ref: > documents.id]
  chunk_id uuid [ref: > document_chunks.id]
  line_start int [not null]
  line_end int [not null]
  verbatim_quote text [not null]
  attribution_type varchar(50)
}

Table gdpr_purge_audit_logs {
  id uuid [pk, default: `gen_random_uuid()`]
  purged_name varchar(255) [not null]
  executed_by uuid [not null, ref: > users.id]
  affected_chunks_count int [not null]
  affected_decisions_count int [not null]
  executed_at timestamptz [default: `now()`]
}
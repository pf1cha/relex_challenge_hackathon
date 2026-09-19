# Project administration

The running manual_demo database previously contained the registered kai account but no projects. The account 63e9b9ac-532a-478e-8869-27707398fe2f is now administrator of Manual demo (27a7f5a1-38de-43bf-8525-eb44882ecb74). Its existing password is unchanged. Refresh or sign in again at http://127.0.0.1:18080.

Open Administration, enter a registered email or account ID, choose Member or Admin, and select Grant or update access. Remove membership revokes access. Users must register first. This is project-scoped administration, not a global bypass or automatic access to other projects. The last administrator cannot be removed or demoted.

POST /api/projects/{p}/members now accepts exactly one of email or user_id plus role. Email lookup requires current project-admin authorization; the final membership mutation revalidates that authorization. Email comparison trims surrounding whitespace and is case-insensitive.

Actual Chromium/FastAPI/PostgreSQL verification passed email-based grant, member project discovery on reload, denial of admin UI/API to members, and browser revocation. Safe report: .runtime/manual/admin-verification.json. Isolated synthetic admin-verification accounts/project remain for inspection; private fixture credentials are in .runtime/manual/admin-check.json and are not published.

Unused backend/app/agents, db, ingestion and services placeholder packages were removed after checking references. Active implementations remain under evidence and intelligence; api remains an active package.

Corpus verification is separate from access management. All45 original files reached parsing but were quarantined with privacy_unresolved before publication. Organization names and metadata such as Acme Org, Phase: Implementation and Attendees trigger broad identity/speaker heuristics. The15 roster names were associated, but email/phone aliases were not, producing legitimate unresolved-contact cases as well as metadata false positives. Neither case was bypassed. Separate model and embedding probes returned429 project_spend_limit_exceeded. Thus zero documents published and none of the nine practice questions or Kwame erasure scenario has passed. See corpus-verification.md for file-level evidence and next steps.

Frontend build/typecheck and git diff --check passed. HTTP remains on127.0.0.1:18080, PostgreSQL on15432, Qdrant on16333, with a separate durable worker. Existing provider credentials and unrelated .env.example edits were preserved.

"""Normalized PostgreSQL authority and restricted preprocessing storage.

The project JSON column is migration input only. Runtime readers reconstruct the
graph from relational rows, and every mutation updates those rows in the same
transaction. Raw uploads, identity mappings, and privacy plans are loaded only
for explicitly restricted worker/admin paths.
"""
from __future__ import annotations

import hashlib
import json

from psycopg.types.json import Jsonb


STATE_KEYS = (
    "members", "project_types", "documents", "records", "people", "jobs", "memories",
    "chunks", "entries", "history", "checkpoints", "operations",
    "conversations", "messages", "attempts", "answers", "plans",
    "capabilities", "privacy_plans", "privacy_diagnostics",
    "privacy_resolutions", "access_epochs",
)

OBJECT_TABLES = {
    "memories": "memory_artifacts",
    "chunks": "source_chunks",
    "entries": "index_entries",
    "history": "history_events",
    "conversations": "conversations",
    "answers": "answers",
    "messages": "messages",
    "attempts": "chat_attempts",
    "checkpoints": "artifact_checkpoints",
    "plans": "rebuild_plans",
    "capabilities": "job_capabilities",
}


def empty_state():
    state = {key: {} for key in STATE_KEYS}
    state.update(corpus_generation=0, privacy_generation=0,
                 lifecycle_revision=0, reservation=0,
                 write_barrier=False, overview=None)
    return state


async def _rows(conn, query, params):
    return await (await conn.execute(query, params)).fetchall()


async def _prune(conn, table, project_id, keys, column="object_key"):
    rows = await _rows(conn, f"SELECT {column} FROM {table} WHERE project_id=%s", (project_id,))
    stale = [row[column] for row in rows if row[column] not in keys]
    if stale:
        await conn.execute(f"DELETE FROM {table} WHERE project_id=%s AND {column}=ANY(%s)",
                           (project_id, stale))


async def load_membership(conn, project_id, user_id):
    return await (await conn.execute(
        "SELECT role,access_revision,granted_at FROM project_memberships "
        "WHERE project_id=%s AND user_id=%s", (project_id, user_id))).fetchone()


async def load_project(conn, project_id, *, restricted=False, for_update=False):
    lock = " FOR UPDATE" if for_update else ""
    row = await (await conn.execute(
        "SELECT * FROM project_state WHERE project_id=%s" + lock,
        (project_id,))).fetchone()
    if row is None:
        return None
    state = empty_state()
    for key in ("corpus_generation", "privacy_generation", "lifecycle_revision", "reservation", "write_barrier", "overview"):
        state[key] = row[key]
    state["project_types"] = row.get("project_types") or {x: True for x in ("email", "transcript", "report", "specification")}

    for member in await _rows(conn,
            "SELECT user_id,role,access_revision,granted_at FROM project_memberships WHERE project_id=%s",
            (project_id,)):
        state["members"][member["user_id"]] = {
            "role": member["role"], "revision": member["access_revision"],
            "granted_at": member["granted_at"].isoformat(),
        }
    for epoch in await _rows(conn,
            "SELECT user_id,access_revision FROM project_access_epochs WHERE project_id=%s", (project_id,)):
        state["access_epochs"][epoch["user_id"]] = epoch["access_revision"]

    for document in await _rows(conn, "SELECT id,payload FROM documents WHERE project_id=%s", (project_id,)):
        state["documents"][document["id"]] = document["payload"]
    for record in await _rows(conn,
            "SELECT r.id,v.payload FROM records r JOIN record_versions v ON "
            "v.project_id=r.project_id AND v.record_id=r.id AND v.version=r.current_version "
            "WHERE r.project_id=%s", (project_id,)):
        state["records"][record["id"]] = record["payload"]
    for job in await _rows(conn, "SELECT id,payload FROM jobs WHERE project_id=%s", (project_id,)):
        state["jobs"][job["id"]] = job["payload"]
    for operation in await _rows(conn, "SELECT id,payload FROM index_operations WHERE project_id=%s", (project_id,)):
        state["operations"][operation["id"]] = operation["payload"]
    for state_key, table in OBJECT_TABLES.items():
        for item in await _rows(conn, f"SELECT object_key,payload FROM {table} WHERE project_id=%s", (project_id,)):
            state[state_key][item["object_key"]] = item["payload"]

    if restricted:
        for item in await _rows(conn,
                "SELECT document_id,raw_filename,raw_content FROM restricted_document_inputs WHERE project_id=%s",
                (project_id,)):
            document = state["documents"].get(item["document_id"])
            if document is not None:
                document["raw_filename"] = item["raw_filename"]
                document["raw"] = item["raw_content"]
        for item in await _rows(conn,
                "SELECT record_id,record_version,raw_spans,source_hash FROM restricted_record_inputs WHERE project_id=%s",
                (project_id,)):
            record = state["records"].get(item["record_id"])
            if record is not None and record.get("record_version") == item["record_version"]:
                record["raw_spans"] = item["raw_spans"]
                record["source_hash"] = item["source_hash"]
        for person in await _rows(conn,
                "SELECT id,payload FROM restricted_identities WHERE project_id=%s", (project_id,)):
            state["people"][person["id"]] = person["payload"]
        for run in await _rows(conn,
                "SELECT record_id,record_version,edit_plan FROM restricted_privacy_runs WHERE project_id=%s AND state='completed'",
                (project_id,)):
            state["privacy_plans"][f"{run['record_id']}:{run['record_version']}"] = run["edit_plan"]
        for diagnostic in await _rows(conn,
                "SELECT id,payload FROM restricted_privacy_diagnostics WHERE project_id=%s", (project_id,)):
            state["privacy_diagnostics"][diagnostic["id"]] = diagnostic["payload"]
        for diagnostic in await _rows(conn,
                "SELECT id,payload FROM restricted_privacy_metadata_diagnostics WHERE project_id=%s", (project_id,)):
            state["privacy_diagnostics"][diagnostic["id"]] = diagnostic["payload"]
        for resolution in await _rows(conn,
                "SELECT id,payload FROM restricted_privacy_resolutions WHERE project_id=%s", (project_id,)):
            state["privacy_resolutions"][str(resolution["id"])] = resolution["payload"]
    return state


def _public_document(document):
    return {key: value for key, value in document.items() if key not in ("raw", "raw_filename")}


def _public_record(record):
    return {key: value for key, value in record.items() if key not in ("raw_spans", "source_hash")}


async def _sync_objects(conn, project_id, state):
    # Clear dependent edges inside the transaction before pruning/reinserting
    # authoritative object rows.
    await conn.execute("DELETE FROM record_dependencies WHERE project_id=%s",(project_id,))
    await conn.execute("DELETE FROM receipts WHERE project_id=%s",(project_id,))
    await conn.execute("DELETE FROM chat_attempts WHERE project_id=%s",(project_id,))
    await conn.execute("UPDATE messages SET answer_id=NULL WHERE project_id=%s",(project_id,))
    for state_key, table in OBJECT_TABLES.items():
        values = state.get(state_key, {})
        for object_key, payload in values.items():
            if state_key=="conversations":
                await conn.execute(
                    "INSERT INTO conversations(project_id,object_key,payload,owner_user_id,created_at,updated_at) VALUES(%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT(project_id,object_key) DO UPDATE SET payload=excluded.payload,owner_user_id=excluded.owner_user_id,updated_at=excluded.updated_at",
                    (project_id,object_key,Jsonb(payload),payload["owner_user_id"],payload["created_at"],payload["updated_at"]))
            elif state_key=="answers":
                data=payload["data"]
                await conn.execute(
                    "INSERT INTO answers(project_id,object_key,payload,conversation_id,request_id,created_at,valid) VALUES(%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT(project_id,object_key) DO UPDATE SET payload=excluded.payload,valid=excluded.valid",
                    (project_id,object_key,Jsonb(payload),data["conversation_id"],data["request_id"],data["created_at"],payload["valid"]))
            elif state_key=="messages":
                await conn.execute(
                    "INSERT INTO messages(project_id,object_key,payload,conversation_id,role,state,answer_id,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT(project_id,object_key) DO UPDATE SET payload=excluded.payload,state=excluded.state,answer_id=excluded.answer_id",
                    (project_id,object_key,Jsonb(payload),payload["conversation_id"],payload["role"],payload["state"],payload.get("answer_id"),payload["created_at"]))
            elif state_key=="attempts":
                await conn.execute(
                    "INSERT INTO chat_attempts(project_id,object_key,payload,conversation_id,message_id,owner_user_id,state) VALUES(%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT(project_id,object_key) DO UPDATE SET payload=excluded.payload,state=excluded.state",
                    (project_id,object_key,Jsonb(payload),payload["attempt"]["conversation_id"],payload["message_id"],payload["owner"],payload["state"]))
            elif state_key=="checkpoints":
                await conn.execute(
                    "INSERT INTO artifact_checkpoints(project_id,object_key,payload,job_id,artifact_key) VALUES(%s,%s,%s,%s,%s) "
                    "ON CONFLICT(project_id,object_key) DO UPDATE SET payload=excluded.payload",
                    (project_id,object_key,Jsonb(payload),payload["batch"]["job_id"],payload["artifact_key"]))
            else:
                await conn.execute(
                    f"INSERT INTO {table}(project_id,object_key,payload) VALUES(%s,%s,%s) "
                    "ON CONFLICT(project_id,object_key) DO UPDATE SET payload=excluded.payload",
                    (project_id, object_key, Jsonb(payload)))
        await _prune(conn, table, project_id, set(values))


async def _sync_references(conn, project_id, state):
    jobs=state.get("jobs",{})
    await conn.execute("DELETE FROM job_documents WHERE project_id=%s",(project_id,))
    await conn.execute("DELETE FROM job_record_versions WHERE project_id=%s",(project_id,))
    for job_id,job in jobs.items():
        for document_id in job["work"].get("document_ids",[]):
            if document_id in state.get("documents",{}):
                await conn.execute("INSERT INTO job_documents(project_id,job_id,document_id) VALUES(%s,%s,%s)",
                                   (project_id,job_id,document_id))
        for ref in job["work"].get("record_versions",[]):
            record=state.get("records",{}).get(ref["record_id"])
            if record and record["record_version"]==ref["record_version"]:
                await conn.execute("INSERT INTO job_record_versions(project_id,job_id,record_id,record_version) VALUES(%s,%s,%s,%s)",
                                   (project_id,job_id,ref["record_id"],ref["record_version"]))
    dependencies=[]
    for owner_id,value in state.get("answers",{}).items():
        dependencies.extend((owner_id,"answer",dep) for dep in value.get("dependencies",[]))
    for owner_id,value in state.get("memories",{}).items():
        dependencies.extend((owner_id,"memory",dep) for dep in value.get("data",{}).get("dependencies",[]))
    for owner_id,value in state.get("checkpoints",{}).items():
        dependencies.extend((owner_id,"artifact",dep) for dep in value.get("batch",{}).get("dependencies",[]))
    for owner_id,value in state.get("plans",{}).items():
        dependencies.extend((owner_id,"rebuild_plan",dep) for dep in value.get("dependencies",[]))
    await conn.execute("DELETE FROM record_dependencies WHERE project_id=%s",(project_id,))
    for owner_id,owner_kind,dep in dependencies:
        owner_column={"answer":"answer_id","memory":"memory_id","artifact":"artifact_id",
                      "rebuild_plan":"rebuild_plan_id"}[owner_kind]
        await conn.execute(
            f"INSERT INTO record_dependencies(project_id,owner_id,owner_kind,record_id,record_version,span_ids,{owner_column}) VALUES(%s,%s,%s,%s,%s,%s,%s)",
            (project_id,owner_id,owner_kind,dep["record_id"],dep["record_version"],Jsonb(dep["span_ids"]),owner_id))
    await conn.execute("DELETE FROM receipts WHERE project_id=%s",(project_id,))
    for answer_id,value in state.get("answers",{}).items():
        for receipt in value.get("data",{}).get("receipts",[]):
            ref=receipt["evidence_ref"]
            await conn.execute(
                "INSERT INTO receipts(project_id,receipt_id,answer_id,record_id,record_version,span_ids) VALUES(%s,%s,%s,%s,%s,%s)",
                (project_id,receipt["id"],answer_id,ref["record_id"],ref["record_version"],Jsonb(ref["span_ids"])))
            await conn.execute(
                "INSERT INTO record_dependencies(project_id,owner_id,owner_kind,record_id,record_version,span_ids,receipt_id) VALUES(%s,%s,'receipt',%s,%s,%s,%s)",
                (project_id,receipt["id"],ref["record_id"],ref["record_version"],Jsonb(ref["span_ids"]),receipt["id"]))


async def sync_project(conn, project_id, state, *, restricted=False, scrub_legacy=True):
    """Synchronize a complete in-memory transaction into normalized authority."""
    await conn.execute(
        "INSERT INTO project_state(project_id,corpus_generation,privacy_generation,lifecycle_revision,reservation,write_barrier,overview,project_types,updated_at) "
        "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,now()) ON CONFLICT(project_id) DO UPDATE SET "
        "corpus_generation=excluded.corpus_generation,privacy_generation=excluded.privacy_generation,"
        "lifecycle_revision=excluded.lifecycle_revision,reservation=excluded.reservation,"
        "write_barrier=excluded.write_barrier,overview=excluded.overview,project_types=excluded.project_types,updated_at=now()",
        (project_id, state["corpus_generation"], state["privacy_generation"],
         state["lifecycle_revision"], state["reservation"], state["write_barrier"],
         Jsonb(state.get("overview")), Jsonb(state.get("project_types", {}))))

    members = state.get("members", {})
    for user_id, member in members.items():
        await conn.execute(
            "INSERT INTO project_principals(project_id,user_id) VALUES(%s,%s) ON CONFLICT DO NOTHING",
            (project_id,user_id))
        await conn.execute(
            "INSERT INTO project_memberships(project_id,user_id,role,access_revision,granted_at) VALUES(%s,%s,%s,%s,%s) "
            "ON CONFLICT(project_id,user_id) DO UPDATE SET role=excluded.role,access_revision=excluded.access_revision,granted_at=excluded.granted_at",
            (project_id, user_id, member["role"], member.get("revision", 0), member["granted_at"]))
    await _prune(conn, "project_memberships", project_id, set(members), "user_id")
    epochs = state.get("access_epochs", {})
    for user_id, revision in epochs.items():
        await conn.execute(
            "INSERT INTO project_principals(project_id,user_id) VALUES(%s,%s) ON CONFLICT DO NOTHING",
            (project_id,user_id))
        await conn.execute(
            "INSERT INTO project_access_epochs(project_id,user_id,access_revision) VALUES(%s,%s,%s) "
            "ON CONFLICT(project_id,user_id) DO UPDATE SET access_revision=excluded.access_revision",
            (project_id, user_id, revision))
    await _prune(conn, "project_access_epochs", project_id, set(epochs), "user_id")

    documents = state.get("documents", {})
    for document_id, document in documents.items():
        public = _public_document(document)
        await conn.execute(
            "INSERT INTO documents(id,project_id,title,record_type,ai_status,processing_state,latest_job_id,deleted,created_at,updated_at,payload) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(id) DO UPDATE SET "
            "title=excluded.title,record_type=excluded.record_type,ai_status=excluded.ai_status,processing_state=excluded.processing_state,"
            "latest_job_id=excluded.latest_job_id,deleted=excluded.deleted,updated_at=excluded.updated_at,payload=excluded.payload",
            (document_id, project_id, document["title"], document["record_type"], document["ai_status"],
             document["processing_state"], document.get("latest_job_id"), document.get("deleted", False),
             document["created_at"], document["updated_at"], Jsonb(public)))
        if restricted and "raw" in document:
            await conn.execute(
                "INSERT INTO restricted_document_inputs(document_id,project_id,raw_filename,raw_content) VALUES(%s,%s,%s,%s) "
                "ON CONFLICT(document_id) DO UPDATE SET raw_filename=excluded.raw_filename,raw_content=excluded.raw_content",
                (document_id, project_id, document.get("raw_filename", document["title"]), document["raw"]))
        elif restricted:
            await conn.execute("DELETE FROM restricted_document_inputs WHERE document_id=%s", (document_id,))
    records = state.get("records", {})
    for record_id, record in records.items():
        version = record["record_version"]
        public = _public_record(record)
        await conn.execute(
            "INSERT INTO records(id,project_id,document_id,current_version,record_type,created_at) VALUES(%s,%s,%s,%s,%s,%s) "
            "ON CONFLICT(id) DO UPDATE SET document_id=excluded.document_id,current_version=excluded.current_version,record_type=excluded.record_type",
            (record_id, project_id, record["original_doc_id"], version, record["record_type"], record["created_at"]))
        await conn.execute(
            "INSERT INTO record_versions(project_id,record_id,version,title,source_time,person_ids,published,quarantined,duplicate_of,payload,created_at) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(project_id,record_id,version) DO UPDATE SET "
            "title=excluded.title,source_time=excluded.source_time,person_ids=excluded.person_ids,published=excluded.published,"
            "quarantined=excluded.quarantined,duplicate_of=excluded.duplicate_of,payload=excluded.payload",
            (project_id, record_id, version, record["title"], Jsonb(record["source_time"]),
             Jsonb(record.get("person_ids", [])), record.get("published", False), record.get("quarantined", False),
             record.get("duplicate_of"), Jsonb(public), record["created_at"]))
        for span in record.get("spans", []):
            await conn.execute(
                "INSERT INTO record_spans(project_id,record_id,record_version,span_id,ordinal,text,source_location) VALUES(%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT(project_id,record_id,record_version,span_id) DO UPDATE SET ordinal=excluded.ordinal,text=excluded.text,source_location=excluded.source_location",
                (project_id, record_id, version, span["span_id"], span["ordinal"], span["text"], Jsonb(span["source_location"])))
        if restricted and "raw_spans" in record:
            await conn.execute(
                "INSERT INTO restricted_record_inputs(project_id,record_id,record_version,source_hash,raw_spans) VALUES(%s,%s,%s,%s,%s) "
                "ON CONFLICT(project_id,record_id,record_version) DO UPDATE SET source_hash=excluded.source_hash,raw_spans=excluded.raw_spans",
                (project_id, record_id, version, record["source_hash"], Jsonb(record["raw_spans"])))
    existing_records=await _rows(conn,"SELECT id FROM records WHERE project_id=%s",(project_id,))
    stale_records=[row["id"] for row in existing_records if row["id"] not in records]
    if stale_records:
        await conn.execute("DELETE FROM restricted_privacy_resolutions WHERE project_id=%s AND payload->>'record_id'=ANY(%s)",(project_id,stale_records))
        await conn.execute("DELETE FROM restricted_privacy_diagnostics WHERE project_id=%s AND record_id=ANY(%s)",(project_id,stale_records))
        await conn.execute("DELETE FROM restricted_privacy_metadata_diagnostics WHERE project_id=%s AND record_id=ANY(%s)",(project_id,stale_records))
        await conn.execute("DELETE FROM restricted_privacy_metadata_occurrences WHERE project_id=%s AND record_id=ANY(%s)",(project_id,stale_records))
        await conn.execute("DELETE FROM restricted_privacy_occurrences WHERE project_id=%s AND record_id=ANY(%s)",(project_id,stale_records))
        await conn.execute("DELETE FROM restricted_privacy_runs WHERE project_id=%s AND record_id=ANY(%s)",(project_id,stale_records))
        await conn.execute("DELETE FROM restricted_record_inputs WHERE project_id=%s AND record_id=ANY(%s)",(project_id,stale_records))
        await conn.execute("DELETE FROM record_dependencies WHERE project_id=%s AND record_id=ANY(%s)",(project_id,stale_records))
        await conn.execute("DELETE FROM record_spans WHERE project_id=%s AND record_id=ANY(%s)",(project_id,stale_records))
        await conn.execute("DELETE FROM record_versions WHERE project_id=%s AND record_id=ANY(%s)",(project_id,stale_records))
        await conn.execute("DELETE FROM records WHERE project_id=%s AND id=ANY(%s)",(project_id,stale_records))
    await _prune(conn, "documents", project_id, set(documents), "id")

    jobs = state.get("jobs", {})
    for job_id, job in jobs.items():
        public = job["public"]
        await conn.execute(
            "INSERT INTO jobs(id,project_id,kind,state,stage,lifecycle_revision,lease_token,expires_at,payload,created_at,updated_at) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(id) DO UPDATE SET state=excluded.state,stage=excluded.stage,"
            "lifecycle_revision=excluded.lifecycle_revision,lease_token=excluded.lease_token,expires_at=excluded.expires_at,payload=excluded.payload,updated_at=excluded.updated_at",
            (job_id, project_id, public["kind"], public["state"], public["stage"], job["lifecycle_revision"],
             job.get("lease_token"), job.get("expires_at"), Jsonb(job), public["created_at"], public["updated_at"]))
    await conn.execute("DELETE FROM job_documents WHERE project_id=%s",(project_id,))
    await conn.execute("DELETE FROM job_record_versions WHERE project_id=%s",(project_id,))
    await _prune(conn, "jobs", project_id, set(jobs), "id")

    operations = state.get("operations", {})
    for operation_id, operation in operations.items():
        public = operation["public"]
        await conn.execute(
            "INSERT INTO index_operations(id,job_id,project_id,action,state,lifecycle_revision,entry_ids,outcome,payload) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(id) DO UPDATE SET state=excluded.state,entry_ids=excluded.entry_ids,outcome=excluded.outcome,payload=excluded.payload",
            (operation_id, public["job_id"], project_id, public["action"], public["state"],
             public["lifecycle_revision"], Jsonb(public["entry_ids"]), Jsonb(operation.get("outcome")), Jsonb(operation)))
    await _prune(conn, "index_operations", project_id, set(operations), "id")
    await _sync_objects(conn, project_id, state)
    await _sync_references(conn, project_id, state)

    if restricted:
        people = state.get("people", {})
        for identity_id, identity in people.items():
            await conn.execute(
                "INSERT INTO restricted_identities(id,project_id,display_name,kind,state,contacts,payload) VALUES(%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT(id) DO UPDATE SET display_name=excluded.display_name,kind=excluded.kind,state=excluded.state,contacts=excluded.contacts,payload=excluded.payload",
                (identity_id, project_id, identity["display_name"], identity["kind"], identity.get("state", "active"),
                 Jsonb(identity.get("contacts", [])), Jsonb(identity)))
            aliases = {identity["display_name"]}
            aliases.update(contact["value"] for contact in identity.get("contacts", []))
            for alias in aliases:
                alias_key = hashlib.sha256((identity_id + "\0" + alias.casefold()).encode()).hexdigest()
                await conn.execute(
                    "INSERT INTO restricted_identity_aliases(alias_key,identity_id,project_id,alias,evidence) VALUES(%s,%s,%s,%s,%s) "
                    "ON CONFLICT(alias_key) DO UPDATE SET alias=excluded.alias,evidence=excluded.evidence",
                    (alias_key, identity_id, project_id, alias, Jsonb({"source": "admin_or_validated_plan"})))
        existing_people=await _rows(conn,"SELECT id FROM restricted_identities WHERE project_id=%s",(project_id,))
        erased={row["id"] for row in existing_people if row["id"] not in people}
        for identity_id in erased:
            tombstone_id=hashlib.sha256((project_id+":"+identity_id).encode()).hexdigest()
            counts=await (await conn.execute(
                "SELECT (SELECT count(*) FROM restricted_privacy_occurrences WHERE project_id=%s AND identity_id=%s)+"
                "(SELECT count(*) FROM restricted_privacy_metadata_occurrences WHERE project_id=%s AND identity_id=%s) AS occurrences",
                (project_id,identity_id,project_id,identity_id))).fetchone()
            await conn.execute(
                "INSERT INTO erasure_tombstones(id,project_id,identity_id,completed_at,inventory) VALUES(%s,%s,%s,now(),%s) "
                "ON CONFLICT(id) DO UPDATE SET completed_at=excluded.completed_at,inventory=excluded.inventory",
                (tombstone_id,project_id,identity_id,Jsonb({"privacy_occurrences":counts["occurrences"]})))
        if erased:
            await conn.execute("UPDATE restricted_privacy_occurrences SET identity_id=NULL WHERE project_id=%s AND identity_id=ANY(%s)",
                               (project_id,list(erased)))
            await conn.execute("UPDATE restricted_privacy_metadata_occurrences SET identity_id=NULL WHERE project_id=%s AND identity_id=ANY(%s)",
                               (project_id,list(erased)))
        if people:
            await conn.execute("DELETE FROM restricted_identity_aliases WHERE project_id=%s AND NOT(identity_id=ANY(%s))",
                               (project_id, list(people)))
        else:
            await conn.execute("DELETE FROM restricted_identity_aliases WHERE project_id=%s", (project_id,))
        await _prune(conn, "restricted_identities", project_id, set(people), "id")

        plans = state.get("privacy_plans", {})
        for plan_key, plan in plans.items():
            job_id = next((jid for jid, job in jobs.items() if any(
                ref["record_id"] == plan["record_id"] and ref["record_version"] == plan["record_version"]
                for ref in job.get("work", {}).get("record_versions", []))), None)
            await conn.execute(
                "INSERT INTO restricted_privacy_runs(id,project_id,job_id,record_id,record_version,source_hash,policy_version,prompt_version,model_version,state,coverage,edit_plan) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,'completed',%s,%s) ON CONFLICT(id) DO UPDATE SET "
                "job_id=excluded.job_id,state=excluded.state,coverage=excluded.coverage,edit_plan=excluded.edit_plan",
                (plan["plan_id"], project_id, job_id, plan["record_id"], plan["record_version"], plan["source_hash"],
                 plan["policy_version"], plan["prompt_version"], plan.get("model_version", "configured-model"),
                 Jsonb({"covered_span_ids": plan["covered_span_ids"], "complete": plan["complete"]}), Jsonb(plan)))
        run_ids = {plan["plan_id"] for plan in plans.values()}
        occurrence_ids = set()
        metadata_occurrence_ids = set()
        for plan in plans.values():
            for entity in plan.get("entities", []):
                occurrence_id = hashlib.sha256(json.dumps([
                    plan["plan_id"], entity["span_id"], entity["start"], entity["end"], entity["kind"]
                ], ensure_ascii=False).encode()).hexdigest()
                identity_id = entity.get("identity_hint")
                if identity_id not in people:
                    identity_id = None
                if entity["span_id"].startswith("title:"):
                    metadata_occurrence_ids.add(occurrence_id)
                    await conn.execute(
                        "INSERT INTO restricted_privacy_metadata_occurrences(id,run_id,project_id,identity_id,record_id,record_version,field_name,start_offset,end_offset,risk_kind,resolution_state,evidence) "
                        "VALUES(%s,%s,%s,%s,%s,%s,'title',%s,%s,%s,%s,%s) ON CONFLICT(id) DO UPDATE SET "
                        "identity_id=excluded.identity_id,resolution_state=excluded.resolution_state,evidence=excluded.evidence",
                        (occurrence_id,plan["plan_id"],project_id,identity_id,plan["record_id"],plan["record_version"],
                         entity["start"],entity["end"],entity["kind"],
                         "pending" if entity["confidence"]=="uncertain" else "validated",Jsonb(entity)))
                else:
                    occurrence_ids.add(occurrence_id)
                    await conn.execute(
                        "INSERT INTO restricted_privacy_occurrences(id,run_id,project_id,identity_id,record_id,record_version,span_id,start_offset,end_offset,risk_kind,resolution_state,evidence) "
                        "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(id) DO UPDATE SET "
                        "identity_id=excluded.identity_id,resolution_state=excluded.resolution_state,evidence=excluded.evidence",
                        (occurrence_id, plan["plan_id"], project_id, identity_id, plan["record_id"], plan["record_version"],
                         entity["span_id"], entity["start"], entity["end"], entity["kind"],
                         "pending" if entity["confidence"] == "uncertain" else "validated", Jsonb(entity)))
        await _prune(conn, "restricted_privacy_occurrences", project_id, occurrence_ids, "id")
        await _prune(conn,"restricted_privacy_metadata_occurrences",project_id,metadata_occurrence_ids,"id")
        await _prune(conn, "restricted_privacy_runs", project_id, run_ids, "id")

        diagnostics = state.get("privacy_diagnostics", {})
        body_diagnostic_ids=set();metadata_diagnostic_ids=set()
        for diagnostic_id, diagnostic in diagnostics.items():
            if diagnostic["span_id"].startswith("title:"):
                metadata_diagnostic_ids.add(diagnostic_id)
                await conn.execute(
                    "INSERT INTO restricted_privacy_metadata_diagnostics(id,project_id,record_id,record_version,field_name,state,payload) VALUES(%s,%s,%s,%s,'title',%s,%s) "
                    "ON CONFLICT(id) DO UPDATE SET state=excluded.state,payload=excluded.payload",
                    (diagnostic_id,project_id,diagnostic["record_id"],diagnostic["record_version"],diagnostic["state"],Jsonb(diagnostic)))
            else:
                body_diagnostic_ids.add(diagnostic_id)
                await conn.execute(
                    "INSERT INTO restricted_privacy_diagnostics(id,project_id,record_id,record_version,span_id,state,payload) VALUES(%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT(id) DO UPDATE SET state=excluded.state,payload=excluded.payload",
                    (diagnostic_id, project_id, diagnostic["record_id"], diagnostic["record_version"],
                     diagnostic["span_id"], diagnostic["state"], Jsonb(diagnostic)))
        await _prune(conn,"restricted_privacy_diagnostics",project_id,body_diagnostic_ids,"id")
        await _prune(conn,"restricted_privacy_metadata_diagnostics",project_id,metadata_diagnostic_ids,"id")

        resolutions = state.get("privacy_resolutions", {})
        for resolution_id, resolution in resolutions.items():
            await conn.execute(
                "INSERT INTO restricted_privacy_resolutions(id,project_id,admin_user_id,decision,rationale,source_version,payload) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",
                (resolution_id, project_id, resolution["admin_user_id"], resolution["decision"],
                 resolution.get("rationale", resolution["decision"]), resolution["record_version"], Jsonb(resolution)))
        await _prune(conn, "restricted_privacy_resolutions", project_id, set(resolutions), "id")

    if scrub_legacy:
        marker = {"authority": "relational-v3", "project_id": project_id,
                  "state_hash": hashlib.sha256(json.dumps({
                      "corpus_generation": state["corpus_generation"],
                      "privacy_generation": state["privacy_generation"],
                      "lifecycle_revision": state["lifecycle_revision"],
                  }, sort_keys=True).encode()).hexdigest()}
        await conn.execute("UPDATE projects SET data=%s WHERE id=%s", (Jsonb(marker), project_id))

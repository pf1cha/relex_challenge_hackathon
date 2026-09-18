# Memory With a Receipt

## Production behavior specification

**Status:** Draft for team review  
**Audience:** Product, engineering, and demo reviewers  
**Source brief:** `RELEX challenge presentation - Memory With a Receipt (1).pdf`

## 1. Purpose

The product helps a user recover what was decided from a changing body of material: transcripts, email threads, status reports, and similar records. It returns useful answers together with enough evidence for the user to verify them.

The product must preserve the difference between what someone suggested, what people agreed to, what was later changed, and what was never true. A fluent summary without evidence is not a successful result.

This document describes externally observable behavior. It deliberately does not prescribe a model, database, retrieval algorithm, or UI framework.

## 2. Terms

- **Record:** An ingested source item, such as a transcript, email thread, or status report.
- **Claim:** A factual statement the system presents about the project or its history.
- **Receipt:** The citation attached to a claim: record identity plus a precise location in that record.
- **Suggestion:** An idea or proposal that has not been established as accepted.
- **Commitment:** An explicit agreement or obligation, including who agreed and any owner, date, or condition.
- **Current:** The latest supported state after considering later changes and corrections.
- **Stale:** Once supported, but superseded by a later record.
- **Never true:** A statement that is contradicted, retracted, or unsupported by the available records.
- **Deleted:** Removed from the searchable and answerable evidence set.
- **Unasked action:** A useful action the system performs without the user spelling out that exact action.

## 3. Primary user journey

1. The user provides or opens a workspace containing source records.
2. The system indexes the records and makes their provenance visible.
3. The user asks a question in ordinary language.
4. The system identifies the relevant claims, evaluates their status and chronology, and returns an answer.
5. Every factual claim has a receipt. The user can open the cited record at the cited location.
6. If evidence is insufficient or conflicting, the system says so and asks a focused follow-up or presents the conflict.
7. The user can delete a person or record. Subsequent answers no longer use deleted material.

## 4. Required behaviors

### 4.1 Evidence and provenance

For every factual statement, the response MUST include a receipt containing:

- source title or stable record identifier;
- source type and date when available;
- a precise location, such as page, paragraph, message, timestamp, or line range;
- a short quoted or otherwise inspectable excerpt.

The receipt MUST point to the evidence that supports the claim, rather than merely to a related document. If no source supports a statement, the system MUST label it as an inference or say that it cannot establish it. It MUST NOT present an unsupported statement as fact.

If multiple records support materially different versions, the answer MUST show the conflict and identify the records. The system MUST NOT silently select a convenient version.

### 4.2 Suggestion versus commitment

The system MUST classify decision language by its evidentiary status. A proposal, option, question, or consultant recommendation is a **suggestion** until the records contain an explicit acceptance or equivalent commitment.

When reporting a commitment, the response SHOULD include proposer, agreeing party or parties, owner, due date, scope, and conditions when those details are supported. Missing details MUST be shown as unknown rather than invented.

Example behavior:

> “We could move the launch to October” is reported as a suggestion.  
> “Everyone agreed to move the launch to October; Alex owns the rollout” is reported as a commitment, with separate receipts for the agreement and ownership if needed.

### 4.3 Currency and chronology

The system MUST evaluate relevant records in chronological context. A later record may revise, cancel, or supersede an earlier decision.

Answers MUST distinguish:

- current decision;
- prior decision and what changed;
- stale information;
- contradicted or never-true information.

Sorting or filtering only by document date is insufficient when the content explicitly refers to another event or decision. If chronology cannot be established, the response MUST state the uncertainty.

### 4.4 Deletion and forgetting

The user MUST be able to delete a person and the associated evidence. Deletion covers the source records, extracted claims, embeddings or indexes, cached summaries, and other derived answer material that could reproduce the deleted information.

After deletion completes:

- new searches and answers MUST exclude the deleted material;
- cached answers MUST be invalidated or recomputed;
- the system MUST report what was deleted and any remaining evidence that does not belong to that person;
- a citation to deleted material MUST no longer open or be returned.

The system MUST provide a clear failure state if deletion is incomplete. It MUST NOT claim the person is forgotten while derived data remains queryable.

### 4.5 Unasked useful action

The product MUST demonstrate at least one safe, useful action it can perform from the evidence without an exact user command. The action MUST be understandable, reversible where applicable, and grounded in cited records.

Acceptable examples include preparing a decision timeline, flagging an unresolved conflict, identifying an owner and overdue commitment, or drafting a follow-up question. The system MUST distinguish a prepared suggestion from an action that changed external state. It MUST report what it did, why it did it, and what evidence triggered it.

## 5. Answer contract

Every answer follows this shape, adapted to the question:

1. **Answer:** direct response in plain language.
2. **Status:** current, stale, suggested, committed, contradicted, unknown, or mixed.
3. **Receipts:** one or more inspectable citations attached to each material claim.
4. **Changes/conflicts:** later revisions, disagreements, or missing evidence.
5. **Next step:** a focused clarification or safe unasked action when useful.

The system MUST avoid a single clean summary when the evidence does not support one. It SHOULD prefer a concise uncertainty statement over fabricated precision.

## 6. Ingestion and record behavior

On ingest, the system MUST preserve the original record, source identity, ingestion time, and any available author/date metadata. It MUST make indexing status visible: processing, ready, failed, or partially indexed.

If a record cannot be read, is ambiguous, or is only partially indexed, the system MUST say so. It MUST NOT imply complete coverage. Re-ingesting an updated record MUST preserve enough version information to explain why an answer changed.

## 7. Failure and edge cases

- **No relevant evidence:** say that no supporting record was found; do not answer from general knowledge as if it came from the workspace.
- **Conflicting evidence:** present both sides, dates, and receipts; ask which source should govern if the user needs a final state.
- **Ambiguous identity:** ask for clarification before attributing a claim to a person.
- **Missing location:** cite the record and explain that a precise location is unavailable; treat the claim as lower confidence.
- **Deleted source during a query:** discard the affected result and return a deletion-in-progress or unavailable state.
- **External action unavailable:** provide a draft or preview and state that no external change was made.

## 8. Acceptance scenarios

### Scenario A: reversed decision

Given an earlier record says “use vendor A” and a later record says “we will use vendor B,” when the user asks which vendor was chosen, the system reports vendor B as current, cites both records, and explains the reversal.

### Scenario B: suggestion mistaken for agreement

Given a consultant proposes a date and no one accepts it, when the user asks what date was agreed, the system says no date is established and cites the proposal as a suggestion.

### Scenario C: never-true record

Given a status report repeats a claim later shown to be false, when the user asks about it, the system identifies it as contradicted or never true and does not repeat it as current fact.

### Scenario D: deletion

Given a person appears in records, extracted claims, and cached summaries, when the user deletes that person, subsequent search and answer results exclude those materials and the system reports completion or a concrete failure.

### Scenario E: unasked action

Given the records contain an owner and an overdue commitment, when the workspace is opened, the system offers a grounded follow-up or overdue flag with a receipt and makes clear whether anything was actually sent or changed.

## 9. Non-goals for this draft

- Defining the AI model or prompt.
- Defining the storage, vector database, or indexing technology.
- Guaranteeing truth outside the supplied records.
- Sending messages, changing project systems, or taking irreversible actions without an explicit product policy and user-visible confirmation.

## 10. Open questions for review

1. What record types and maximum workspace size must the first demo support?
2. What counts as explicit acceptance in the target organization’s language?
3. Which timestamp wins when record metadata and message content disagree?
4. Is deletion scoped to a person, a record, a workspace, or all three?
5. Which unasked action will be demonstrated, and what approval boundary does it have?
6. What citation formats can the demo reliably open (page, timestamp, message, paragraph, or line)?
7. What is the minimum acceptable behavior when indexing or deletion is only partial?

## 11. Traceability to the challenge brief

| Brief requirement | This specification |
| --- | --- |
| “Cite everything” | 4.1, 5 |
| “Suggestion != commitment” | 4.2 |
| “Know stale from wrong” | 4.3 |
| “Delete a person” | 4.4 |
| “Do one thing unasked” | 4.5 |
| Provenance 25% | 4.1, 5 |
| Attribution 20% | 4.2 |
| Currency 20% | 4.3 |
| Deletion 20% | 4.4 |
| Initiative 15% | 4.5 |
| URL submission and live questions | 8, 9, and the acceptance scenarios |


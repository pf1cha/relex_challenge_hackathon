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
8. The documents are organized in "projects". When a user is granted access in a project, it has access to the documents.
9. Users have different roles and permissions. For example, a manager can decide what documents are activated for use in a project.
10. Each project has a useful visualization page. The specific content of the visualization is TBD.
11. Users roles:
Admin who controls the document visibility (activate/diactivate/delete it)
Each project should have its own role, which can be granted to a basic user.
Basic user - basic user can’t have access to any documents from projects.

If a basic user is granted access to a project, then the user will have abilities to see documents and interact with them and the AI for that project. 

## 4. Required behaviors

### 4.1 Evidence and provenance

For every factual statement, the response MUST include:

- Source link and short quote displayed with a small icon. The quote appears when the mouse is hovered above the icon. When clicked, the icon directs the user to the document.

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

The user MUST be able to delete a person’s personal information. This includes information like name, contact, etc. The key point is being GDPR compliant. Deletion covers the source records, extracted claims, embeddings or indexes, cached summaries, and other derived answer material that could reproduce the deleted information.

One way to approach this is to store the personal information separately from the main data. For example, in vector databases they can be metadata, in summarizations they can be mappings (im not sure if this is the correct word), so that we don’t have to compute everything after a deletion.


After deletion completes:

- The personal information of that individual cannot be retrieved anywhere
- But the relevant actions and other information should be preserved. For example, person A did something to B. When A is deleted, the information should be [deleted user] did something to B.

The system MUST provide a clear failure state if deletion is incomplete. It MUST NOT claim the person is forgotten while derived data remains queryable.



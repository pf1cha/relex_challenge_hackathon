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

1. Documents are organized into projects. A user opens a project they have been granted access to.
2. The system indexes the project's active documents and makes their provenance visible.
3. The user asks a question in ordinary language about that project.
4. The system identifies the relevant claims, evaluates their status and chronology, and returns an answer using only evidence available to that user in the project.
5. Every factual claim has a receipt. The user can inspect the supporting quote and open the document at the cited location.
6. If evidence is insufficient or conflicting, the system says so and asks a focused follow-up or presents the conflict. It does not generate unsupported factual claims.
7. Project admins can activate, deactivate, or delete documents. The product also supports removing a selected person's names and contact information while preserving project actions and decisions.
8. Each project has a visualization page. Its specific content is TBD. The proposed v1 delivery includes the project selector and status information described in user-features.md; the specific visualization remains deferred and is not fulfilled by status information alone.

### 3.1 Roles and project access

| Role | Permissions |
| --- | --- |
| Basic user without project membership | Cannot access that project's documents, answers, or visualizations. |
| Project member | Can read active documents and interact with the AI within that project. |
| Project admin | Can manage project membership and activate, deactivate, or delete documents, in addition to project member permissions. |

Membership and admin permissions are scoped to each project. Access to one project does not grant access to another.

Access restrictions MUST apply to documents, AI answers, citation quotes, cached summaries, and visualizations. The system MUST NOT reveal inaccessible project information through any of these surfaces.

Whether a separate system-wide admin role is needed remains open.

### 3.2 Document activation

Deactivating a document excludes it from subsequent AI answers and project visualizations without permanently deleting it. Reactivating it makes it eligible again.

Cached material used for subsequent answers or visualizations MUST respect the current activation state.

Whether members can browse inactive documents, and how previously displayed answers and their citations behave after deactivation, remain open decisions.

## 4. Required behaviors

### 4.1 Evidence and provenance

Every factual claim MUST be supported by a source document and a precise location within it. The system MUST NOT generate unsupported factual claims. If the available evidence cannot answer the question, the system states that it cannot establish an answer from the available records.

Each citation is displayed with a small icon next to the claim:

- Hovering over, focusing on, or tapping the icon displays a short supporting quote.
- Selecting the source link opens the document at the cited location.
- The citation identifies the source document and the location supporting the claim, such as a page, paragraph, message, or timestamp.

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

The deletion feature is motivated by GDPR compliance needs. The scope of this draft is removal of a selected person's **names and contact information**, such as email addresses, phone numbers, and postal addresses. This scope does not by itself establish full GDPR compliance.

Deletion MUST remove that information from source documents, extracted claims, citations and quoted excerpts, embeddings or indexes, cached summaries, and other derived answer material. Hiding it only when a query is answered is insufficient.

After deletion completes:

- The person's names and contact information MUST no longer be retrievable from the system's documents or derived data.
- Relevant project actions, decisions, and other information MUST remain available, with the person's attribution replaced by `[deleted user]`.
- For example, “Alice agreed to the October launch” becomes “[deleted user] agreed to the October launch.” The agreed date remains answerable.
- Citations and source views MUST show the updated content without exposing the removed names or contact information.

The system MUST provide a clear failure state if deletion is incomplete. It MUST NOT report completion while the names or contact information remain retrievable from source or derived material.

The role authorized to request personal-information deletion, and whether that deletion applies to one project or all projects, remain open decisions.

## 5. Implementation idea for later review

One possible approach is to store names and contact information separately from project facts and use references to that information in summaries and other derived material. This is a design idea, not a required implementation. Whatever approach is chosen must satisfy the deletion behavior above, including removing information already present in source text or derived data.

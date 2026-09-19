# Pseudonymization reference notes

**Status: Background reference only; not the implementation contract.**

The material below is preserved as supplied design input. Its mapping-only deletion approach, broader identifier/generalization scope, vault/HSM prescriptions, and legal assertions are not adopted requirements or validated compliance conclusions.

For the selected implementation, follow `production-behavior.md`, `ai-agent-architecture.md`, and the confirmed delivery spec. Deletion targets names/contact information, replaces the selected person's pseudonyms with `[deleted user]`, and recomputes affected embeddings. Do not infer anonymity from mapping deletion alone.

---

To implement pseudonymization for meeting transcripts and project notes, simple search-and-replace is not enough. Under GDPR (Art. 4(5)), pseudonymization requires replacing direct identifiers with pseudonyms while keeping the lookup key strictly separated, and—as Acme’s DPO Katarina Voss highlighted—neutralizing quasi-identifiers (job titles or descriptions that single out exactly one person).
Here is a practical, production-ready architecture for a Pseudonymization Agent designed for corporate transcripts.

1. The Three Layers of Pseudonymization
Tier
Target Data
Strategy
Example Transformation
Tier 1: Direct Identifiers
Names, corporate emails, personal phone numbers, Employee IDs (OP_ID: 447102).
Consistent Tokenization / Synthetic Aliases backed by a secure key vault.
Sofia Almeida

User_C8F2 (or synthetic name Morgan Reed)<br>+49 151 8890 4471

[PHONE_01]
Tier 2: Quasi-Identifiers (Singling Out)
Unique titles, shifts, store locations with small teams ("Store 118 Vantaa, nights").
Generalization & K-Anonymity: Coarsen titles and locations to prevent deducing identity.
"Category Manager Fresh (sole owner)"

"Category Management"<br>"Store 118 Vantaa, nights"

"Retail Store Staff"
Tier 3: Contextual Circumstances
Personal life events tied to work capacity (medical leaves, court dates, divorces).
Functional Masking: Decouple the person from the private cause while preserving the operational constraint.
"Sofia is out for surgery"

"User_C8F2 has scheduled leave (operational capacity constraint)"


2. Architecture: Secure Pseudonymization Agent (SPA)
The architecture ensures that the text is readable for business and AI agents, but cannot be attributed to individuals without access to an isolated, encrypted Key Vault.
codeCode
[ Raw Dialogue Turn / Transcript ]
                    	│
                    	▼
  	┌────────────────────────────────────┐
  	│   1. Identification Engine     	│
  	│   - Regex / NER (Presidio)         │  Detects names, emails, phone numbers,
  	│   - LLM Quasi-Identifier Detector  │  unique role descriptions, dates, locations
  	└─────────────────┬──────────────────┘
                    	│
                    	▼
  	┌────────────────────────────────────┐
  	│   2. Secure Tokenization Vault     │  <-- Encrypted KMS / HSM (Air-gapped)
  	│   - Salted HMAC / UUID Generator   │  - Stores { Real_ID <-> Pseudo_ID }
  	│   - Role-Based Access Control  	│  - Separate encryption keys per project
      └─────────────────┬──────────────────┘  - Access restricted to DPO / Legal
                    	│
                    	▼
  	┌────────────────────────────────────┐
  	│   3. Role & Semantic Generalizer   │
  	│   - Coarsens unique titles         │  Suppresses "sole knowledge holder",
  	│   - Generalizes locations/shifts   │  transforms hyper-specific descriptions
  	└─────────────────┬──────────────────┘
                    	│
     	               ▼
  	┌────────────────────────────────────┐
  	│   4. Output Generator          	│
  	│   - Pseudonymized Transcript       │  Ready for RAG, Summaries, Vector DBs,
  	│   - Reversible only via Token Key  │  and Jira/Project Tracking
  	└────────────────────────────────────┘

3. Detailed Component Design
Component 1: Deterministic & Semantic Identification Engine
NER & Rule Matcher: Detects formal PII (names, emails, phones, internal codes like MARA-MHDHB vs. personal OP_ID: 447102).
Quasi-Identifier Extractor (LLM Prompting): Identifies phrases where unique role attributes act as a signature.
Pattern detected: "The person who runs dairy and produce alone since Tobias left."
Classification: Singling out

Flag for generalization.
Component 2: The Isolated Tokenization Vault (Key Management)
GDPR mandates that the attribution key must be kept separately under organizational and technical safeguards:
Mechanism: Uses a keyed hash (HMAC-SHA256) with a secret rotation salt stored in a dedicated Hardware Security Module (HSM / AWS KMS / Azure Key Vault):







Referential Integrity: Within the same project or meeting series, Sofia Almeida consistently maps to Customer_Lead_Fresh (or Actor_A), so downstream RAG systems maintain conversational continuity and speaker attribution.
Separation of Concerns: Developers, analysts, and project managers have zero read access to the Token Vault. Only the Data Protection Officer or an automated re-identification workflow under legal hold can query the table.
Component 3: Role & Context Generalizer (Katarina Voss Compliance)
To solve the problem raised in the steering review ("Removing a name is not anonymisation if one person fits the description"):
The agent detects single-occupant roles and applies hierarchical generalization:
Level 0 (Raw): "Category Manager Fresh, sole knowledge holder"
Level 1 (Coarsened): "Category Management Lead"
Level 2 (Generalized): "Customer Commercial Team"
Specific metadata like store IDs linked with shift times (Store 118 Vantaa, nights, Osman Yildirim) are replaced with regional aggregated tags: [Store_Region_Nordics, Retail_Associate].

4. Concrete Example: Before and After
Raw Transcript Turn:
Priya Nair (11:26): "The write-off records carry OP_ID 447102, which is Marika Lindqvist at store 118 Vantaa on nights. If someone reads that table, Marika has the highest write-offs because she works the reduction shift, not because she is careless. And Sofia Almeida is out until November for surgery, so Jonas Weiss cannot approve the produce logic."
Agent Processing:
Marika Lindqvist, 447102

Map to User_M52 via Token Vault.
store 118 Vantaa, nights

Generalize to [Retail Store, Reduction Shift].
Sofia Almeida

Map to User_S14.
out until November for surgery

Mask to unavailable until mid-November (availability constraint).
Jonas Weiss

Map to User_J09.
Pseudonymized Output:
[Customer_IT_Lead] (11:26): "The write-off records carry Operator ID [User_M52], an associate at [Store_Location_B] on [Reduction_Shift]. If someone reads that table, [User_M52] has the highest write-offs because they work the reduction shift, not because of error. Furthermore, [User_S14] is unavailable until mid-November (scheduled availability constraint), so [User_J09] cannot validate the produce ordering logic."

5. Re-Identification Protocol (Audit & Erasure)
Right to Erasure (GDPR Art. 17):
If an employee files a deletion request, you do not need to rewrite hundreds of transcripts and meeting notes manually.
You simply delete their entry in the Token Vault (cryptographic shredding). Once the key linking Sofia Almeida

[User_S14] is destroyed, the remaining transcripts become irreversibly anonymized.
Controlled De-pseudonymization:
If a project escalation requires knowing who agreed to a specific contractual baseline, an audit request can be submitted to the DPO to temporarily re-link [Customer_PM] to Lena Fischer with an immutable log entry.


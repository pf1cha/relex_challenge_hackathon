import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.contracts.errors import DomainError
from app.evidence.jobs import (RECONCILIATION_REASONS, _known_person_matches,
                               _proposed_person_id, _remove_affected_raw_sources)
from app.evidence.parsing import parse
from app.evidence.privacy import PrivacyAgent, validate_sanitized


class CorrectingProvider:
    settings = SimpleNamespace(model="privacy-test")

    def __init__(self):
        self.calls = 0

    async def generate(self, role, system, payload, **kwargs):
        self.calls += 1
        schema = kwargs["json_schema"]
        entity = schema["schema"]["properties"]["entities"]["items"]
        assert schema["strict"] is True
        assert set(entity["required"]) == {"span_id", "kind", "expected_text", "identity_hint"}
        assert entity["properties"]["kind"]["enum"] == [
            "person", "contact", "personal_identifier"]
        span = payload["spans"][0]
        name = "Åsa Öberg"
        return {
            "complete": True,
            "covered_span_ids": [span["span_id"]],
            "entities": [
                {"span_id": span["span_id"], "expected_text": name, "kind": "person"},
            ],
            "unresolved_reasons": [],
        }


class FailedProvider:
    settings = SimpleNamespace(model="privacy-test")

    async def generate(self, *args, **kwargs):
        raise RuntimeError("raw provider detail must not escape")


class TokenBudgetProvider:
    settings = SimpleNamespace(model="privacy-test")

    async def generate(self, role, system, payload, **kwargs):
        assert kwargs["max_tokens"] == 2048
        return {"entities": []}


class CapturingProvider:
    settings = SimpleNamespace(model="privacy-test")

    def __init__(self):
        self.payloads = []

    async def generate(self, role, system, payload, **kwargs):
        self.payloads.append(payload)
        return {"entities": []}


class VariantBindingProvider:
    settings = SimpleNamespace(model="privacy-test")

    async def generate(self, role, system, payload, **kwargs):
        assert payload["known_identities"][0]["id"] == "PERSON_tomas"
        assert payload["known_identities"][0]["name_variants"] == [
            "Tomas Lindholm", "TL", "T. Lindholm", "Tomas L."]
        return {"entities": [{"span_id": "s1", "kind": "person",
                              "expected_text": "T. Lindholm",
                              "identity_hint": "PERSON_tomas"}]}


class InitialAndRoleProvider:
    settings = SimpleNamespace(model="privacy-test")

    async def generate(self, role, system, payload, **kwargs):
        assert payload["known_identities"][0]["name_variants"] == [
            "Lena Fischer", "LF", "L. Fischer", "Lena F."]
        return {"entities": [
            {"span_id": "s1", "kind": "person", "expected_text": "LF",
             "identity_hint": "PERSON_lena"},
            {"span_id": "s2", "kind": "person", "expected_text": "Acme CFO",
             "identity_hint": None},
        ]}


class UneditedContactProvider:
    settings = SimpleNamespace(model="privacy-test")

    def __init__(self):
        self.calls = 0

    async def generate(self, role, system, payload, **kwargs):
        self.calls += 1
        return {"entities": []}


class SystemCodeProvider:
    settings = SimpleNamespace(model="privacy-test")

    async def generate(self, role, system, payload, **kwargs):
        return {"entities": []}


class OverclassifyingProvider:
    settings = SimpleNamespace(model="privacy-test")

    async def generate(self, role, system, payload, **kwargs):
        span = payload["spans"][0]
        return {"entities": [
            {"span_id": span["span_id"], "expected_text": "Katarina Voss", "kind": "person"},
            {"span_id": span["span_id"], "expected_text": "Data Protection Officer", "kind": "person"},
            {"span_id": span["span_id"], "expected_text": "Thursday, 30 April 2026", "kind": "personal_identifier"},
            {"span_id": span["span_id"], "expected_text": "Thank you, that is a good response", "kind": "personal_identifier"},
            {"span_id": span["span_id"], "expected_text": "Hansaring 82, 50670 Koln", "kind": "contact"},
        ]}


def test_corpus_parser_is_lossless_and_preserves_known_boundaries():
    root = Path(__file__).resolve().parents[3] / "corpus" / "acme"
    files = sorted(root.glob("*/*.txt"))
    assert len(files) == 45
    counts = {}
    hashes = []
    for path in files:
        kind = {"emails": "email", "transcripts": "transcript", "reports": "report"}[path.parent.name]
        source = path.read_text()
        records = parse(source, kind)
        assert [span.text for spans, _, _ in records for span in spans] == source.splitlines()
        counts[path.name] = len(records)
        hashes.extend(source_hash for _, _, source_hash in records)
    assert counts["16_dc2-hypercare-incidents.txt"] == 5
    assert len(hashes) == len(set(hashes))


def test_transcript_disclaimer_is_not_a_turn():
    path = Path(__file__).resolve().parents[3] / "corpus" / "acme" / "transcripts" / "15_2025-09-12_fresh-phase2-escalation.txt"
    spans = parse(path.read_text(), "transcript")[0][0]
    first = next(span for span in spans if span.source_location.turn_ordinal)
    assert first.source_location.line_start == 15
    assert first.source_location.speaker_label == "Marco Rossi"


def test_identity_proposal_is_reused_across_records_in_one_upload():
    batch_ids = {}
    first = _proposed_person_id("plan-a", "NEW_katarina", "Katarina Voss", {}, batch_ids)
    second = _proposed_person_id(
        "plan-b", "NEW_katarina", "Katarina Voss", {"katarina voss": {first}}, batch_ids)
    assert second == first


def test_existing_same_name_outside_upload_still_requires_review():
    assert _proposed_person_id(
        "plan-b", "NEW_alex", "Alex Smith", {"alex smith": {"PERSON_existing"}}, {}) is None


def test_unique_first_name_binding_matches_privacy_planner():
    assert _known_person_matches(
        "Marco", {"marco rossi": {"PERSON_marco"}}, {"marco": {"PERSON_marco"}}) == {"PERSON_marco"}
    assert _known_person_matches(
        "Alex", {}, {"alex": {"PERSON_one", "PERSON_two"}}) == {"PERSON_one", "PERSON_two"}


def test_erasure_retains_unaffected_original_documents():
    state = {
        "documents": {
            "affected": {"raw": "Kwame source", "raw_filename": "affected.txt"},
            "unaffected": {"raw": "Other source", "raw_filename": "unaffected.txt"},
        },
        "records": {
            "affected-record": {"original_doc_id": "affected", "raw_spans": ["private"]},
            "unaffected-record": {"original_doc_id": "unaffected", "raw_spans": ["retained"]},
        },
    }
    _remove_affected_raw_sources(state,{"affected"})
    assert "raw" not in state["documents"]["affected"]
    assert "raw_filename" not in state["documents"]["affected"]
    assert state["documents"]["unaffected"]["raw"] == "Other source"
    assert "raw_spans" not in state["records"]["affected-record"]
    assert state["records"]["unaffected-record"]["raw_spans"] == ["retained"]


def test_retry_recomputes_derived_identity_failures():
    cached = {"unsupported identity binding", "provider-authored unresolved reason"}
    assert cached - RECONCILIATION_REASONS == {"provider-authored unresolved reason"}


@pytest.mark.asyncio
async def test_privacy_plan_derives_unicode_codepoint_ranges():
    text = "Åsa Öberg owns OP_ID 447102 until November."
    provider = CorrectingProvider()
    plan = await PrivacyAgent(provider).plan("project", "record", 1, [{"span_id": "s1", "text": text}],
        hashlib.sha256(text.encode()).hexdigest())
    assert provider.calls == 1
    assert plan.corrections_used == 0
    assert plan.entities[0].expected_text == "Åsa Öberg"
    assert text[plan.entities[0].start:plan.entities[0].end] == "Åsa Öberg"


def test_privacy_derives_offsets_from_unique_expected_text_and_ignores_model_ranges():
    spans = [{"span_id": "s1", "text": "IT Integration Lead"}]
    result = {"entities": [{"span_id": "s1", "start": 0, "end": 21,
                            "expected_text": "IT Integration Lead"}], "edits": []}
    fixed = PrivacyAgent._resolve_entity_offsets(result, spans)
    assert fixed["entities"][0]["start"] == 0
    assert fixed["entities"][0]["end"] == 19

    repeated = [{"span_id": "s1", "text": "Alex met Alex."}]
    ambiguous = {"entities": [{"span_id": "s1", "start": 0, "end": 4,
                                "expected_text": "Alex"}]}
    assert PrivacyAgent._resolve_entity_offsets(ambiguous, repeated)["entities"] == []


@pytest.mark.asyncio
async def test_privacy_provider_failure_is_visible_and_safe():
    text = "No deterministic trigger is present."
    with pytest.raises(DomainError) as failure:
        await PrivacyAgent(FailedProvider()).plan("project", "record", 1, [{"span_id": "s1", "text": text}],
            hashlib.sha256(text.encode()).hexdigest())
    assert failure.value.code == "provider_unavailable"


@pytest.mark.asyncio
async def test_privacy_generation_has_bounded_output_budget():
    text = "No deterministic trigger is present."
    plan = await PrivacyAgent(TokenBudgetProvider()).plan(
        "project", "record", 1, [{"span_id": "s1", "text": text}],
        hashlib.sha256(text.encode()).hexdigest())
    assert plan.complete is True


def test_privacy_batches_bound_structured_output_size():
    assert PrivacyAgent.max_batch_codepoints == 800


@pytest.mark.asyncio
async def test_privacy_masks_deterministically_protected_values_from_model_only():
    text = "Tomas Lindholm contacted owner@example.test about Alice Unknown."
    provider = CapturingProvider()
    people = {"PERSON_tomas": {"display_name": "Tomas Lindholm", "contacts": [], "state": "active"}}
    plan = await PrivacyAgent(provider).plan(
        "project", "record", 1, [{"span_id": "s1", "text": text}],
        hashlib.sha256(text.encode()).hexdigest(), people=people)
    model_text = provider.payloads[0]["spans"][0]["text"]
    assert "Tomas Lindholm" in model_text
    assert "owner@example.test" not in model_text
    assert "Alice Unknown" in model_text
    assert {(entity.kind, entity.expected_text) for entity in plan.entities} == {
        ("person", "Tomas Lindholm"),
        ("personal_identifier", "owner@example.test"),
    }


@pytest.mark.asyncio
async def test_model_can_bind_name_variant_to_supplied_identity():
    text = "T. Lindholm approved the plan."
    people = {"PERSON_tomas": {"display_name": "Tomas Lindholm", "contacts": [], "state": "active"}}
    plan = await PrivacyAgent(VariantBindingProvider()).plan(
        "project", "record", 1, [{"span_id": "s1", "text": text}],
        hashlib.sha256(text.encode()).hexdigest(), people=people)
    assert [(entity.expected_text, entity.identity_hint) for entity in plan.entities] == [
        ("T. Lindholm", "PERSON_tomas")]


@pytest.mark.asyncio
async def test_model_binds_initials_and_role_title_cannot_become_person():
    spans = [{"span_id": "s1", "text": "LF"},
             {"span_id": "s2", "text": "Robert Kahn (Acme CFO)"}]
    text = "\n".join(span["text"] for span in spans)
    people = {"PERSON_lena": {"display_name": "Lena Fischer", "contacts": [], "state": "active"}}
    plan = await PrivacyAgent(InitialAndRoleProvider()).plan(
        "project", "record", 1, spans, hashlib.sha256(text.encode()).hexdigest(), people=people)
    assert [(entity.expected_text, entity.identity_hint) for entity in plan.entities] == [
        ("LF", "PERSON_lena")]



@pytest.mark.asyncio
async def test_privacy_compiles_contact_entity_to_source_bound_edit():
    text = "Contact owner@example.test for the handoff."
    provider = UneditedContactProvider()
    plan = await PrivacyAgent(provider).plan("project", "record", 1, [{"span_id": "s1", "text": text}],
        hashlib.sha256(text.encode()).hexdigest())
    assert [(edit.reason, edit.expected_text, edit.replacement) for edit in plan.edits] == [
        ("personal_identifier", "owner@example.test", "[personal identifier removed]")]
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_privacy_rejects_model_overclassification_of_roles_dates_and_prose():
    text = ("Katarina Voss\nData Protection Officer\nThursday, 30 April 2026\n"
            "Thank you, that is a good response\nHansaring 82, 50670 Koln")
    plan = await PrivacyAgent(OverclassifyingProvider()).plan(
        "project", "record", 1, [{"span_id": "s1", "text": text}],
        hashlib.sha256(text.encode()).hexdigest())
    assert [(entity.kind, entity.expected_text) for entity in plan.entities] == [
        ("person", "Katarina Voss"),
        ("contact", "Hansaring 82, 50670 Koln"),
    ]
    assert {edit.expected_text for edit in plan.edits} == {
        "Katarina Voss", "Hansaring 82, 50670 Koln"}


@pytest.mark.asyncio
async def test_system_code_exemption_is_exact_and_other_personal_id_still_fails():
    text = "System OP_ID SYS-447."
    source_hash = hashlib.sha256(text.encode()).hexdigest()
    start = text.index("OP_ID SYS-447")
    resolution = {
        "diagnostic_id": "diagnostic", "record_id": "record", "record_version": 1,
        "source_hash": source_hash, "span_id": "s1", "start": start,
        "end": start + len("OP_ID SYS-447"), "expected_text": "OP_ID SYS-447",
        "kind": "personal_identifier", "reason": "system identifier", "decision": "system_code",
    }
    plan = await PrivacyAgent(SystemCodeProvider()).plan(
        "project", "record", 1, [{"span_id": "s1", "text": text}], source_hash,
        resolutions=[resolution])
    raw = plan.model_dump(mode="json")
    validate_sanitized(raw, {"s1": "System OP_ID SYS-447."}, [resolution])
    with pytest.raises(ValueError, match="direct_identifier_survived"):
        validate_sanitized(raw, {"s1": "System OP_ID SYS-447; operator OP_ID PERSON-9."}, [resolution])

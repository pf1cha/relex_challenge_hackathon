import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.contracts.errors import DomainError
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
        assert "confidence" in entity["required"]
        assert entity["properties"]["kind"]["enum"] == [
            "person", "organization", "role", "contact", "personal_identifier",
            "contextual_circumstance", "uncertain"]
        if self.calls == 1:
            return {"complete": False, "covered_span_ids": [], "entities": [], "unresolved_reasons": []}
        span = payload["spans"][0]
        name = "Åsa Öberg"
        personal_id = "OP_ID 447102"
        a = span["text"].index(name)
        b = span["text"].index(personal_id)
        return {
            "complete": True,
            "covered_span_ids": [span["span_id"]],
            "entities": [
                {"span_id": span["span_id"], "start": a, "end": a + len(name), "expected_text": name,
                 "kind": "person", "identity_hint": "NEW_1", "evidence_span_ids": [span["span_id"]], "confidence": "certain"},
                {"span_id": span["span_id"], "start": b, "end": b + len(personal_id), "expected_text": personal_id,
                 "kind": "personal_identifier", "identity_hint": "NEW_1", "evidence_span_ids": [span["span_id"]], "confidence": "certain"},
            ],
            "unresolved_reasons": [],
        }


class FailedProvider:
    settings = SimpleNamespace(model="privacy-test")

    async def generate(self, *args, **kwargs):
        raise RuntimeError("raw provider detail must not escape")


class UneditedContactProvider:
    settings = SimpleNamespace(model="privacy-test")

    def __init__(self):
        self.calls = 0

    async def generate(self, role, system, payload, **kwargs):
        self.calls += 1
        span = payload["spans"][0]
        value = "owner@example.test"
        start = span["text"].index(value)
        return {
            "complete": True,
            "covered_span_ids": [span["span_id"]],
            "entities": [{"span_id": span["span_id"], "start": start, "end": start + len(value),
                          "expected_text": value, "kind": "contact", "identity_hint": None,
                          "evidence_span_ids": [span["span_id"]], "confidence": "certain"}],
            "edits": [],
            "unresolved_reasons": [],
        }


class SystemCodeProvider:
    settings = SimpleNamespace(model="privacy-test")

    async def generate(self, role, system, payload, **kwargs):
        span = payload["spans"][0]
        value = "OP_ID SYS-447"
        start = span["text"].index(value)
        return {
            "complete": True,
            "covered_span_ids": [span["span_id"]],
            "entities": [{"span_id": span["span_id"], "start": start, "end": start + len(value),
                          "expected_text": value, "kind": "personal_identifier", "identity_hint": None,
                          "evidence_span_ids": [span["span_id"]], "confidence": "certain"}],
            "edits": [],
            "unresolved_reasons": [],
        }


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


@pytest.mark.asyncio
async def test_privacy_plan_uses_one_correction_and_unicode_codepoint_ranges():
    text = "Åsa Öberg owns OP_ID 447102 until November."
    provider = CorrectingProvider()
    plan = await PrivacyAgent(provider).plan("project", "record", 1, [{"span_id": "s1", "text": text}],
        hashlib.sha256(text.encode()).hexdigest())
    assert provider.calls == 2
    assert plan.corrections_used == 1
    assert plan.entities[0].expected_text == "Åsa Öberg"
    assert text[plan.entities[0].start:plan.entities[0].end] == "Åsa Öberg"


def test_privacy_canonicalizes_only_unique_exact_expected_text_offsets():
    spans = [{"span_id": "s1", "text": "Call +358 40 123 4567 now."}]
    result = {
        "entities": [{"span_id": "s1", "start": 5, "end": 12,
                      "expected_text": "+358 40 123 4567"}],
        "edits": [],
    }
    fixed = PrivacyAgent._canonicalize_unique_offsets(result, spans)
    assert fixed["entities"][0]["start"] == 5
    assert fixed["entities"][0]["end"] == 21

    repeated = [{"span_id": "s1", "text": "Alex met Alex."}]
    ambiguous = {"entities": [{"span_id": "s1", "start": 1, "end": 2,
                                "expected_text": "Alex"}]}
    unchanged = PrivacyAgent._canonicalize_unique_offsets(ambiguous, repeated)
    assert (unchanged["entities"][0]["start"], unchanged["entities"][0]["end"]) == (1, 2)


@pytest.mark.asyncio
async def test_privacy_provider_failure_is_visible_and_safe():
    text = "No deterministic trigger is present."
    with pytest.raises(DomainError) as failure:
        await PrivacyAgent(FailedProvider()).plan("project", "record", 1, [{"span_id": "s1", "text": text}],
            hashlib.sha256(text.encode()).hexdigest())
    assert failure.value.code == "provider_unavailable"


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

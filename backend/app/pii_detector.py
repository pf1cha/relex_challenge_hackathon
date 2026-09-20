"""Local GPU GLiNER2 service for source-bound PII candidate detection."""
from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict


LABELS = [
    "person", "full_name", "first_name", "middle_name", "last_name",
    "email", "phone_number", "address", "street_address", "postal_code",
    "government_id", "national_id_number", "passport_number",
    "drivers_license_number", "tax_id", "bank_account", "account_number",
    "iban", "payment_card", "card_number", "username", "account_id",
    "sensitive_account_id", "ip_address",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SpanInput(StrictModel):
    span_id: str
    text: str


class DetectInput(StrictModel):
    spans: list[SpanInput]


class Candidate(StrictModel):
    span_id: str
    start: int
    end: int
    expected_text: str
    label: str
    confidence: float


class Detector:
    def __init__(self):
        self.model = None
        self.lock = asyncio.Lock()

    def load(self):
        from gliner2 import GLiNER2
        self.model = GLiNER2.from_pretrained(
            os.environ.get("RELEX_GLINER_MODEL", "fastino/gliner2-privacy-filter-PII-multi"),
            map_location=os.environ.get("RELEX_GLINER_DEVICE", "cuda"),
        )

    def infer(self, spans: list[SpanInput]):
        threshold=float(os.environ.get("RELEX_GLINER_THRESHOLD", "0.35"))
        results=self.model.batch_extract_entities(
            [span.text for span in spans], LABELS, batch_size=min(16,max(1,len(spans))),
            threshold=threshold,include_confidence=True,include_spans=True)
        candidates=[]
        for span,result in zip(spans,results):
            raw=[]
            for label,values in result.get("entities",{}).items():
                for value in values:
                    start=value["start"];end=value["end"]
                    if span.text[start:end]!=value["text"]:
                        continue
                    raw.append(Candidate(span_id=span.span_id,start=start,end=end,
                        expected_text=value["text"],label=label,confidence=float(value["confidence"])))
            # GLiNER emits full names and their component names. Keep maximal
            # overlapping spans so the mapper receives one coherent candidate.
            for value in sorted(raw,key=lambda item:(item.start,-(item.end-item.start),-item.confidence)):
                if any(value.start>=saved.start and value.end<=saved.end for saved in candidates
                       if saved.span_id==value.span_id):
                    continue
                candidates.append(value)
        return candidates


detector=Detector()


@asynccontextmanager
async def lifespan(app):
    await asyncio.to_thread(detector.load)
    yield


def create_app():
    app=FastAPI(lifespan=lifespan)

    @app.get("/healthz")
    async def healthz():
        return {"state":"ready","model":os.environ.get(
            "RELEX_GLINER_MODEL","fastino/gliner2-privacy-filter-PII-multi")}

    @app.post("/detect",response_model=list[Candidate])
    async def detect(request: DetectInput):
        async with detector.lock:
            return await asyncio.to_thread(detector.infer,request.spans)

    return app


app=create_app()

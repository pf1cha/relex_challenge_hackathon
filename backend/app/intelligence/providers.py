"""OpenAI-compatible transports. No environment reads or connections at import."""
from __future__ import annotations
import json
import math
import time
from dataclasses import dataclass
from typing import Any
import httpx

@dataclass(frozen=True)
class ProviderSettings:
    base_url: str
    model: str
    api_key: str = ""
    embedding_base_url: str = ""
    embedding_model: str = ""
    embedding_api_key: str = ""
    timeout_seconds: float = 60

class ProviderFailure(Exception):
    """Safe transport failure; never contains remote response bodies."""

class ModelProvider:
    def __init__(self, settings: ProviderSettings, *, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self.client = client or httpx.AsyncClient(timeout=settings.timeout_seconds)
        self.events: list[dict[str, Any]] = []
        self.dimension: int | None = None

    @property
    def embedding_model(self):
        return self.settings.embedding_model

    async def close(self):
        await self.client.aclose()

    async def _post(self, base, path, key, body):
        if not base:
            raise ProviderFailure("provider_unavailable")
        try:
            response = await self.client.post(base.rstrip("/") + path,
                headers={"Authorization": "Bearer " + key} if key else {}, json=body)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderFailure("provider_unavailable") from None

    async def generate(self, role: str, system: str, payload: dict, *, max_tokens=4096,
                       json_schema: dict[str, Any] | None = None) -> dict:
        started = time.monotonic()
        response_format = ({"type":"json_schema","json_schema":json_schema}
                           if json_schema is not None else {"type":"json_object"})
        result = await self._post(self.settings.base_url, "/chat/completions", self.settings.api_key,
            {"model": self.settings.model, "messages": [{"role":"system","content":system},
             {"role":"user","content":json.dumps(payload, ensure_ascii=False)}],
             "response_format":response_format, "max_completion_tokens":max_tokens})
        try:
            content = result["choices"][0]["message"]["content"]
            value = json.loads(content)
            if not isinstance(value, dict):
                raise ValueError()
        except (KeyError, IndexError, TypeError, ValueError):
            raise ProviderFailure("provider_unavailable") from None
        usage = result.get("usage", {})
        self.events.append({"role":role,"model":self.settings.model,
            "latency_ms":int((time.monotonic()-started)*1000),
            "prompt_tokens":usage.get("prompt_tokens"), "completion_tokens":usage.get("completion_tokens")})
        return value

    async def embed(self, texts: list[str], *, model: str | None = None, dimension: int | None = None):
        expected = model or self.embedding_model
        if expected != self.embedding_model or not expected:
            raise ProviderFailure("dependency_unavailable")
        result = await self._post(self.settings.embedding_base_url, "/embeddings",
            self.settings.embedding_api_key, {"model":expected,"input":texts})
        try:
            rows = sorted(result["data"], key=lambda row: row["index"])
            vectors = [row["embedding"] for row in rows]
            size = len(vectors[0])
            if len(vectors)!=len(texts) or size < 1 or any(len(v)!=size or any(
                isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in v) for v in vectors):
                raise ValueError()
            if (dimension is not None and dimension != size) or (self.dimension is not None and self.dimension != size):
                raise ValueError()
        except (KeyError, TypeError, IndexError, ValueError):
            raise ProviderFailure("dependency_unavailable") from None
        self.dimension = size
        self.events.append({"role":"embedding","model":expected,"dimension":size,"inputs":len(texts)})
        return vectors

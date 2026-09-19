"""Qdrant is a candidate index. No text from its payload is returned as evidence."""
from __future__ import annotations
from typing import Any
import httpx
from .providers import ProviderFailure

class IndexFailure(Exception):
    def __init__(self, unknown=False):
        self.unknown = unknown
        super().__init__("index_outcome_unknown" if unknown else "dependency_unavailable")

class QdrantIndex:
    def __init__(self, url: str, collection: str, api_key: str = "", *, client=None):
        if not collection or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in collection):
            raise ValueError("Invalid collection name")
        self.url, self.collection = url.rstrip("/"), collection
        self.client = client or httpx.AsyncClient(timeout=60, headers={"api-key":api_key} if api_key else {})

    async def close(self):
        await self.client.aclose()

    async def _call(self, method, path, body=None, *, write=False, allow_missing=False):
        try:
            result=await self.client.request(method, self.url + path, json=body)
            if allow_missing and result.status_code==404:
                return None
            result.raise_for_status()
            return result.json().get("result")
        except (httpx.HTTPError, ValueError):
            raise IndexFailure(unknown=write) from None

    @property
    def path(self):
        return "/collections/"+self.collection

    async def ensure(self, dimension: int):
        info=await self._call("GET",self.path,allow_missing=True)
        if info is None:
            await self._call("PUT",self.path,{"vectors":{"size":dimension,"distance":"Cosine"}},write=True)
            info=await self._call("GET",self.path)
        try:
            vectors=info["config"]["params"]["vectors"]
            if vectors["size"]!=dimension or vectors["distance"]!="Cosine":
                raise ValueError()
        except (KeyError, TypeError, ValueError):
            raise IndexFailure() from None

    async def search(self, vector, project_id, limit=100):
        info=await self._call("POST",self.path+"/points/query",{
            "query":vector,"limit":limit,"with_payload":True,
            "filter":{"must":[{"key":"project_id","match":{"value":project_id}}]}})
        return info.get("points",[])

    async def fetch(self, ids):
        if not ids:return {}
        rows=await self._call("POST",self.path+"/points",{"ids":ids,"with_payload":True,"with_vector":False})
        return {str(row["id"]):row.get("payload",{}) for row in rows}

    async def upsert(self, entries, vectors):
        await self._call("PUT",self.path+"/points?wait=true",{"points":[
            {"id":entry.id,"vector":vector,"payload":entry.model_dump(mode="json")}
            for entry,vector in zip(entries,vectors,strict=True)]},write=True)
        return await self.verify(entries)

    async def verify(self, entries):
        found=await self.fetch([e.id for e in entries])
        return all(found.get(e.id)==e.model_dump(mode="json") for e in entries)

    async def delete(self, ids):
        if not ids:return True
        await self._call("POST",self.path+"/points/delete?wait=true",{"points":ids},write=True)
        return not await self.fetch(ids)

    async def scan(self, project_id, offset=None):
        return await self._call("POST",self.path+"/points/scroll",{
            "filter":{"must":[{"key":"project_id","match":{"value":project_id}}]},
            "limit":100,"offset":offset,"with_payload":True,"with_vector":False})

"""Test-only pauses around actual B work; no canned service responses."""
import asyncio,json
from pathlib import Path

class PausedIntelligence:
    def __init__(self,real,directory):
        self.real=real;self.directory=Path(directory)
    def __getattr__(self,name):return getattr(self.real,name)
    async def answer(self,ctx,input):
        candidate=await self.real.answer(ctx,input)
        if (self.directory/"pause-answer").exists():
            (self.directory/"answer-ready").write_text(json.dumps({"request_id":input.request_id,"claims":len(candidate.claims)}))
            while not (self.directory/"release-answer").exists():await asyncio.sleep(.05)
        return candidate

def pause_index(index,directory):
    directory=Path(directory);original=index.upsert
    async def upsert(entries,vectors):
        if (directory/"pause-index").exists():
            (directory/"pause-index").unlink()
            (directory/"index-ready").write_text(json.dumps({"entry_ids":[e.id for e in entries]}))
            while not (directory/"release-index").exists():await asyncio.sleep(.05)
        return await original(entries,vectors)
    index.upsert=upsert

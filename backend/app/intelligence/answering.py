from __future__ import annotations
import asyncio
from datetime import datetime,timezone,timedelta
from pathlib import Path
from uuid import uuid4
from pydantic import ValidationError
from app.contracts.models import *
from app.contracts.hashing import candidate_digest
from app.contracts.errors import DomainError
from .tools import ToolSession,BudgetExhausted
from .retrieval import snapshot
from .providers import ProviderFailure

PROMPTS=Path(__file__).with_name("prompts")
def prompt(name):return (PROMPTS/(name+".txt")).read_text()

class Answers:
    async def _generate(self,role,system,payload,deadline):
        remaining=(deadline-datetime.now(timezone.utc)).total_seconds()
        if remaining<=0:raise DomainError("provider_unavailable")
        try:
            async with asyncio.timeout(remaining):
                return await self.provider.generate(role,system,payload)
        except (ProviderFailure,TimeoutError):raise DomainError("provider_unavailable") from None

    async def _agent(self,role,session,payload):
        while True:
            result=await self._generate(role,prompt("reviewer" if role=="review" else "answer"),
                {**(payload() if callable(payload) else payload),"tool_results":session.results,"coverage":session.coverage().model_dump(mode="json"),
                "remaining_search_rounds":max(0,session.round_limit-session.searches)},session.deadline)
            if "tools" not in result:return result
            if not isinstance(result["tools"],list) or not result["tools"]:raise DomainError("contract_violation")
            try:
                for tool in result["tools"]:
                    if set(tool)!={"name","arguments"}:raise DomainError("contract_violation")
                    await session.call(tool["name"],tool["arguments"])
            except BudgetExhausted:
                # One final provider response with explicit exhausted coverage, no new tools.
                result=await self._generate(role,prompt("reviewer" if role=="review" else "answer"),
                    {**(payload() if callable(payload) else payload),"tool_results":session.results,"coverage":session.coverage().model_dump(mode="json"),"tools_exhausted":True},session.deadline)
                if "tools" in result:return {"results":[]} if role=="review" else {"claims":[],"cannot_establish":"incomplete_coverage"}
                return result

    def _empty(self,ctx,reason,coverage=None):
        payload=ReviewedPayload(claims=[],receipts=[],dependencies=[],coverage=coverage or Coverage(state="insufficient",records=[],limitations=[]),
            cannot_establish=reason,snapshot=snapshot(ctx))
        return ReviewedCandidate(**payload.model_dump(),review_results=[],candidate_digest=candidate_digest(payload),omission_proof=None)

    async def _draft(self,ctx,raw,session):
        if set(raw)-{"claims","cannot_establish"}:raise DomainError("contract_violation")
        claims=[];receipts=[]
        for value in raw.get("claims",[]):
            if set(value)-{"text","status","scope","effective_at","evidence"}:raise DomainError("contract_violation")
            references=value.get("evidence",[])
            if not references:raise DomainError("contract_violation")
            receipt_ids=[]
            for source in references:
                if set(source)!={"record_id","record_version","span_ids"}:raise DomainError("contract_violation")
                key=(source["record_id"],source["record_version"])
                known=session.spans.get(key,{})
                ids=source["span_ids"]
                if not ids or any(s not in known for s in ids):raise DomainError("contract_violation")
                ordinals=[known[s].ordinal for s in ids]
                if ordinals!=list(range(ordinals[0],ordinals[0]+len(ordinals))):raise DomainError("contract_violation")
                record=session.records[key]["summary"]
                ref=EvidenceRef(project_id=ctx.project_id,original_doc_id=record.original_doc_id,**source)
                receipt=await self.reader.make_receipt(ctx,ref)
                if receipt.evidence_ref!=ref or receipt.quote!="\n".join(known[s].text for s in ids):raise DomainError("contract_violation")
                receipts.append(receipt);receipt_ids.append(receipt.id)
            claims.append(Claim(id=str(uuid4()),text=value["text"],receipt_ids=list(dict.fromkeys(receipt_ids)),
                status=value.get("status"),scope=value.get("scope"),effective_at=value.get("effective_at")))
        receipts=list({r.id:r for r in receipts}.values())
        return ReviewedPayload(claims=claims,receipts=receipts,dependencies=session.deps(),coverage=session.coverage(),
            cannot_establish=raw.get("cannot_establish") or (None if claims else "no_evidence"),snapshot=snapshot(ctx))

    async def _review(self,ctx,question,payload,deadline):
        session=ToolSession(self,ctx,self.limits,deadline,self.limits.reviewer_search_rounds)
        try:
            await session.discover(question)
            if session.searches<session.round_limit:
                await session.discover(question+" corrections replacements cancellations conditions")
        except BudgetExhausted:pass
        # Independent discovery may add counterevidence; include it before fixing review digest.
        dependencies={(d.record_id,d.record_version):set(d.span_ids) for d in payload.dependencies}
        for dep in session.deps():dependencies.setdefault((dep.record_id,dep.record_version),set()).update(dep.span_ids)
        payload.dependencies=[Dependency(record_id=k[0],record_version=k[1],span_ids=sorted(v)) for k,v in sorted(dependencies.items())]
        def review_input():
            for dep in session.deps():
                dependencies.setdefault((dep.record_id,dep.record_version),set()).update(dep.span_ids)
            payload.dependencies=[Dependency(record_id=k[0],record_version=k[1],span_ids=sorted(v)) for k,v in sorted(dependencies.items())]
            return {"question":question,"candidate":payload.model_dump(mode="json"),
                "candidate_digest":candidate_digest(payload),"tool_schema":prompt("answer").split("Search arguments:")[-1]}
        raw=await self._agent("review",session,review_input)
        digest=candidate_digest(payload)
        if set(raw)!={"results"}:raise DomainError("contract_violation")
        results=[]
        by_id={c.id:c for c in payload.claims}
        for value in raw["results"]:
            if "candidate_digest" in value:raise DomainError("contract_violation")
            result=ReviewResult(**value,candidate_digest=digest)
            if result.claim_id not in by_id or set(result.receipt_ids)!=set(by_id[result.claim_id].receipt_ids):raise DomainError("contract_violation")
            # A reviewer unable to read the discovered records cannot attest completeness.
            if session.coverage().state!="complete" and result.verdict=="pass":
                result.verdict="fail";result.reason_code="incomplete_coverage";result.repair_request="Read missing source context within budget."
            results.append(result)
        if len(results)!=len(by_id) or {r.claim_id for r in results}!=set(by_id):
            results=[ReviewResult(claim_id=c.id,verdict="fail",reason_code="incomplete_coverage",receipt_ids=c.receipt_ids,
                repair_request="Reviewer did not establish every claim.",candidate_digest=digest) for c in payload.claims]
        self.traces.append({"phase":"review","tools":session.trace,"verdicts":[{"claim_id":r.claim_id,"verdict":r.verdict,"reason_code":r.reason_code,"receipt_ids":r.receipt_ids,"candidate_digest":r.candidate_digest} for r in results]})
        return payload,results

    async def answer(self,ctx,input):
        if input.question.ambiguous:return self._empty(ctx,"ambiguous_person")
        deadline=min(input.deadline,datetime.now(timezone.utc)+timedelta(seconds=self.limits.request_deadline_seconds))
        # Inputs arrive normalized from A; subsequent generated searches are normalized again in retrieval.
        session=ToolSession(self,ctx,self.limits,deadline,self.limits.answer_search_rounds)
        try:
            await session.discover(input.question.text)
            if session.searches<session.round_limit:
                await session.discover(input.question.text+" corrections replacements conditions")
        except BudgetExhausted:pass
        request={"question":input.question.text,"history":[h.model_dump(mode="json") for h in input.history]}
        try:
            raw=await self._agent("answer",session,request)
            payload=await self._draft(ctx,raw,session)
            self.traces.append({"phase":"answer","tools":session.trace})
            if not payload.claims:return self._empty(ctx,payload.cannot_establish,payload.coverage)
            payload,results=await self._review(ctx,input.question.text,payload,deadline)
            if any(r.verdict=="fail" for r in results) and self.limits.reviewer_passes>1 and self.limits.repair_search_rounds>0:
                repair=ToolSession(self,ctx,self.limits,deadline,self.limits.repair_search_rounds)
                # Reuse supplied evidence without resetting the initial phase budget; repair has its own caps.
                repair.records=dict(session.records);repair.spans=dict(session.spans);repair.dependencies=dict(session.dependencies)
                repair.results=list(session.results)
                try:await repair.discover(input.question.text+" "+" ".join(r.repair_request or "" for r in results if r.verdict=="fail"))
                except BudgetExhausted:pass
                raw=await self._agent("repair",repair,{**request,"failed_review":[r.model_dump(mode="json") for r in results],"prior_claims":[c.model_dump(mode="json") for c in payload.claims]})
                payload=await self._draft(ctx,raw,repair)
                self.traces.append({"phase":"repair","tools":repair.trace})
                if not payload.claims:return self._empty(ctx,payload.cannot_establish,payload.coverage)
                payload,results=await self._review(ctx,input.question.text,payload,deadline)
            passed={r.claim_id for r in results if r.verdict=="pass"}
            if len(passed)==len(payload.claims):
                return ReviewedCandidate(**payload.model_dump(),review_results=results,candidate_digest=candidate_digest(payload),omission_proof=None)
            if not passed:return self._empty(ctx,"review_rejected",payload.coverage)
            proof=OmissionProof(reviewed=payload.model_copy(deep=True),review_results=results,reviewed_digest=candidate_digest(payload))
            payload.claims=[c for c in payload.claims if c.id in passed]
            used={r for c in payload.claims for r in c.receipt_ids};payload.receipts=[r for r in payload.receipts if r.id in used]
            return ReviewedCandidate(**payload.model_dump(),review_results=[r for r in results if r.claim_id in passed],
                candidate_digest=candidate_digest(payload),omission_proof=proof)
        except (ValidationError,KeyError,TypeError,ValueError):raise DomainError("contract_violation") from None

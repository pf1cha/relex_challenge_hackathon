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
        guidance=None;shallow_retries=0;tool_retries=0;evidence_retries=0
        while True:
            request={**(payload() if callable(payload) else payload),"tool_results":session.results,
                "coverage":session.coverage().model_dump(mode="json"),"retrieval_state":session.retrieval_state()}
            if guidance:request["retrieval_guidance"]=guidance
            result=await self._generate(role,prompt("answer"),request,session.deadline)
            if "tools" not in result:
                needs_source_search=bool(session.discovered_records) and session.source_searches==0 and session.searches<session.round_limit
                needs_source_read=bool(session.source_records) and not session.spans
                feedback=request.get("review_feedback",{}).get("retrieval",{})
                needs_repair_retrieval=role=="repair" and feedback.get("verdict")=="insufficient" and not session.trace and session.searches<session.round_limit
                if role in {"answer","repair"} and (needs_source_search or needs_source_read or needs_repair_retrieval) and shallow_retries<2:
                    shallow_retries+=1
                    guidance={"code":"deeper_retrieval_available",
                        "message":"Discovery-level context cannot support factual claims. Continue with read_memory when useful and search_sources/read_record for canonical evidence before finalizing.",
                        "requires_source_search":needs_source_search or needs_repair_retrieval,"requires_source_read":needs_source_read,
                        "review_missing_context":feedback.get("missing_context",[]),
                        "suggested_queries":feedback.get("suggested_queries",[]),
                        "suggested_record_ids":feedback.get("suggested_record_ids",[])}
                    continue
                unread=set()
                for claim in result.get("claims",[]) if isinstance(result.get("claims"),list) else []:
                    for source in claim.get("evidence",[]) if isinstance(claim,dict) and isinstance(claim.get("evidence"),list) else []:
                        if not isinstance(source,dict):continue
                        key=(source.get("record_id"),source.get("record_version"))
                        known=session.spans.get(key,{})
                        ids=source.get("span_ids",[])
                        if key[0] and (not known or not isinstance(ids,list) or any(span_id not in known for span_id in ids)):
                            unread.add(key[0])
                if role in {"answer","repair"} and unread and evidence_retries<3:
                    evidence_retries+=1
                    guidance={"code":"unread_evidence",
                        "message":"The final answer cites evidence that has not been loaded with read_record. Read every suggested record returned by search_sources, then cite only span IDs present in those read_record results.",
                        "requires_source_search":any(record_id not in session.source_records for record_id in unread),
                        "suggested_record_ids":sorted(unread)}
                    continue
                return result
            if not isinstance(result["tools"],list) or not result["tools"]:raise DomainError("contract_violation")
            tool=None
            try:
                for tool in result["tools"]:
                    if set(tool)!={"name","arguments"}:raise DomainError("contract_violation")
                    await session.call(tool["name"],tool["arguments"])
            except (DomainError,ValidationError,KeyError,TypeError,ValueError) as error:
                if isinstance(error,DomainError) and error.code not in {"invalid_input","not_found"}:raise
                if tool_retries>=4:raise DomainError("contract_violation") from None
                tool_retries+=1
                name=tool.get("name") if isinstance(tool,dict) else None
                arguments=tool.get("arguments",{}) if isinstance(tool,dict) else {}
                requires_source_search=name=="read_record" and arguments.get("record_id") not in session.source_records
                guidance={"code":"invalid_tool_sequence",
                    "message":"The requested tool call is not valid for the current retrieval state. Follow the progressive retrieval order, do not repeat an identical call, and use only IDs returned by prior tools.",
                    "rejected_tool":name,"requires_source_search":requires_source_search,
                    "allowed_search_filters":["date_from","date_to","record_type","original_doc_id","topic_id","person_id"],
                    "suggested_record_ids":[arguments["record_id"]] if requires_source_search and arguments.get("record_id") else []}
                continue
            except BudgetExhausted:
                # One final provider response with explicit exhausted coverage, no new tools.
                result=await self._generate(role,prompt("reviewer" if role=="review" else "answer"),
                    {**(payload() if callable(payload) else payload),"tool_results":session.results,
                    "coverage":session.coverage().model_dump(mode="json"),"retrieval_state":session.retrieval_state(),"tools_exhausted":True},session.deadline)
                if "tools" in result:return {"claims":[],"cannot_establish":"incomplete_coverage"}
                return result

    def _empty(self,ctx,reason,coverage=None):
        payload=ReviewedPayload(claims=[],receipts=[],dependencies=[],coverage=coverage or Coverage(state="insufficient",records=[],limitations=[]),
            cannot_establish=reason,snapshot=snapshot(ctx))
        return ReviewedCandidate(**payload.model_dump(),review_results=[],candidate_digest=candidate_digest(payload),omission_proof=None)

    def _require_human_review(self,status,references,session):
        if status not in {"superseded","corrected"}:return
        kinds={"corrected":{"correction"},"superseded":{"replacement","cancellation","reinstatement"}}[status]
        cited={(ref["record_id"],ref["record_version"]) for ref in references}
        approved=False
        for event in session.approved_history_events:
            evidence={(ref.record_id,ref.record_version) for ref in event.evidence}
            if event.kind in kinds and cited and cited<=evidence:
                approved=True;break
        if not approved:raise DomainError("contract_violation")

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
                # Each receipt is contiguous; separate nonadjacent supports instead of inventing a joined quote.
                ordered=sorted(set(ids),key=lambda sid:known[sid].ordinal)
                groups=[]
                for sid in ordered:
                    if not groups or known[sid].ordinal!=known[groups[-1][-1]].ordinal+1:groups.append([])
                    groups[-1].append(sid)
                record=session.records[key]["summary"]
                for group in groups:
                    ref=EvidenceRef(project_id=ctx.project_id,original_doc_id=record.original_doc_id,
                        record_id=key[0],record_version=key[1],span_ids=group)
                    receipt=await self.reader.make_receipt(ctx,ref)
                    if receipt.evidence_ref!=ref or receipt.quote!="\n".join(known[s].text for s in group):raise DomainError("contract_violation")
                    receipts.append(receipt);receipt_ids.append(receipt.id)
            effective=value.get("effective_at")
            if effective is not None:
                try:effective=SourceTime.model_validate(effective)
                except (ValidationError,TypeError,ValueError):effective=SourceTime(value=None,precision="unknown",timezone=None)
            self._require_human_review(value.get("status"),references,session)
            claims.append(Claim(id=str(uuid4()),text=value["text"],receipt_ids=list(dict.fromkeys(receipt_ids)),
                status=value.get("status"),scope=value.get("scope"),effective_at=effective))
        receipts=list({r.id:r for r in receipts}.values())
        return ReviewedPayload(claims=claims,receipts=receipts,dependencies=session.deps(),coverage=session.coverage(),
            cannot_establish=raw.get("cannot_establish") or (None if claims else "no_evidence"),snapshot=snapshot(ctx))

    async def _review(self,question,payload,session,deadline):
        raw=await self._generate("review",prompt("reviewer"),{"question":question,
            "candidate":payload.model_dump(mode="json"),"candidate_digest":candidate_digest(payload),
            "retrieval_packet":{"tool_results":session.results,"coverage":session.coverage().model_dump(mode="json"),
                "retrieval_state":session.retrieval_state()}},deadline)
        digest=candidate_digest(payload)
        if set(raw)!={"retrieval","results"}:raise DomainError("contract_violation")
        assessment=RetrievalAssessment.model_validate(raw["retrieval"])
        results=[]
        by_id={c.id:c for c in payload.claims}
        for value in raw["results"]:
            if "candidate_digest" in value:raise DomainError("contract_violation")
            result=ReviewResult(**value,candidate_digest=digest)
            if result.claim_id not in by_id or not set(result.receipt_ids)<=set(by_id[result.claim_id].receipt_ids):raise DomainError("contract_violation")
            if result.verdict=="pass" and set(result.receipt_ids)!=set(by_id[result.claim_id].receipt_ids):raise DomainError("contract_violation")
            if assessment.verdict=="insufficient" and result.verdict=="pass":
                result.verdict="fail";result.reason_code="incomplete_coverage"
                result.repair_request="; ".join(assessment.missing_context) or "Retrieve additional source context."
            results.append(result)
        if len(results)!=len(by_id) or {r.claim_id for r in results}!=set(by_id):
            results=[ReviewResult(claim_id=c.id,verdict="fail",reason_code="incomplete_coverage",receipt_ids=c.receipt_ids,
                repair_request="Reviewer did not establish every claim.",candidate_digest=digest) for c in payload.claims]
        self.traces.append({"phase":"review","retrieval":assessment.model_dump(mode="json"),
            "reviewed_answer_tools":[x["tool"] for x in session.trace],
            "verdicts":[{"claim_id":r.claim_id,"verdict":r.verdict,"reason_code":r.reason_code,"receipt_ids":r.receipt_ids,"candidate_digest":r.candidate_digest} for r in results]})
        return payload,assessment,results

    def _new_repair_session(self,ctx,deadline,session):
        repair=ToolSession(self,ctx,self.limits,deadline,self.limits.repair_search_rounds)
        repair.records=dict(session.records);repair.spans=dict(session.spans);repair.dependencies=dict(session.dependencies)
        repair.results=list(session.results);repair.tokens=session.tokens
        repair.discovered_records=set(session.discovered_records);repair.level2_records=set(session.level2_records)
        repair.source_records=set(session.source_records);repair.source_searches=session.source_searches
        repair.pending_searches=set(session.pending_searches);repair.pending_histories=set(session.pending_histories)
        repair.approved_history_events=list(session.approved_history_events)
        repair.completed_calls=set(session.completed_calls)
        return repair

    async def answer(self,ctx,input):
        if input.question.ambiguous:return self._empty(ctx,"ambiguous_person")
        deadline=min(input.deadline,datetime.now(timezone.utc)+timedelta(seconds=self.limits.request_deadline_seconds))
        # Inputs arrive normalized from A; subsequent generated searches are normalized again in retrieval.
        session=ToolSession(self,ctx,self.limits,deadline,self.limits.answer_search_rounds)
        try:
            await session.discover(input.question.text)
        except BudgetExhausted:pass
        request={"question":input.question.text,"history":[h.model_dump(mode="json") for h in input.history]}
        try:
            raw=await self._agent("answer",session,request)
            payload=await self._draft(ctx,raw,session)
            self.traces.append({"phase":"answer","tools":session.trace})
            if not payload.claims:return self._empty(ctx,payload.cannot_establish,payload.coverage)
            active_session=session;assessment=None;results=[]
            for review_index in range(self.limits.reviewer_passes):
                payload,assessment,results=await self._review(input.question.text,payload,active_session,deadline)
                if assessment.verdict=="sufficient" and all(r.verdict=="pass" for r in results):break
                if review_index+1>=self.limits.reviewer_passes or self.limits.repair_search_rounds<=0:break
                repair=self._new_repair_session(ctx,deadline,active_session)
                feedback={"retrieval":assessment.model_dump(mode="json"),
                    "claims":[r.model_dump(mode="json") for r in results]}
                raw=await self._agent("repair",repair,{**request,"review_feedback":feedback,
                    "prior_claims":[c.model_dump(mode="json") for c in payload.claims]})
                payload=await self._draft(ctx,raw,repair)
                self.traces.append({"phase":"repair","attempt":review_index+1,"tools":repair.trace})
                if not payload.claims:return self._empty(ctx,payload.cannot_establish,payload.coverage)
                active_session=repair
            passed={r.claim_id for r in results if r.verdict=="pass"}
            if assessment and assessment.verdict=="sufficient" and len(passed)==len(payload.claims):
                return ReviewedCandidate(**payload.model_dump(),review_results=results,candidate_digest=candidate_digest(payload),
                    omission_proof=None,retrieval_review=assessment)
            if assessment and assessment.verdict=="insufficient":passed=set()
            if not passed:return self._empty(ctx,"review_rejected",payload.coverage)
            proof=OmissionProof(reviewed=payload.model_copy(deep=True),review_results=results,reviewed_digest=candidate_digest(payload))
            payload.claims=[c for c in payload.claims if c.id in passed]
            used={r for c in payload.claims for r in c.receipt_ids};payload.receipts=[r for r in payload.receipts if r.id in used]
            return ReviewedCandidate(**payload.model_dump(),review_results=[r for r in results if r.claim_id in passed],
                candidate_digest=candidate_digest(payload),omission_proof=proof,retrieval_review=assessment)
        except (ValidationError,KeyError,TypeError,ValueError):raise DomainError("contract_violation") from None

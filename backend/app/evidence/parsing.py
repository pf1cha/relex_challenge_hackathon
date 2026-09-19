"""Lossless line spans with explicit email bundle separators and original locations."""
import re, uuid, hashlib
from email.utils import parsedate_to_datetime
from ..contracts.models import SourceTime, Span, SourceLocation

def parse(text, kind):
    if not text.strip() or "\x00" in text: raise ValueError("invalid text")
    lines=text.splitlines()
    starts=[0]
    if kind=="email":
        # Only an unquoted header at start or after a bundle delimiter opens a record.
        for i,line in enumerate(lines):
            if i and line.startswith("From:"):
                explicit = re.fullmatch(r"[-=]{5,}|From \S+.*",lines[i-1])
                double_blank = i >= 2 and not lines[i-1].strip() and not lines[i-2].strip()
                header_block = "\n".join(lines[i:i+8])
                complete_headers = re.search(r"^Date:",header_block,re.M) and re.search(r"^Subject:",header_block,re.M)
                forwarded = any("forwarded" in previous.casefold() or "original message" in previous.casefold() for previous in lines[max(0,i-3):i])
                if explicit or double_blank and complete_headers and not forwarded: starts.append(i)
    starts.append(len(lines));records=[]
    for n,(start,end) in enumerate(zip(starts,starts[1:])):
        section=lines[start:end];time=SourceTime(value=None,precision="unknown",timezone=None)
        for line in section[:12]:
            match=re.match(r"(?:Date|Sent|Meeting date):\s*(.*)",line,re.I)
            if match:
                val=match[1].strip()
                if re.fullmatch(r"\d{4}(?:-\d{2}){0,2}",val):
                    precision={4:"year",7:"month",10:"day"}[len(val)]
                    time=SourceTime(value=val,precision=precision,timezone=None)
                else:
                    try:
                        dt=parsedate_to_datetime(val)
                        if dt.tzinfo:time=SourceTime(value=dt.isoformat(),precision="instant",timezone=str(dt.tzinfo))
                    except (ValueError,TypeError):pass
                break
        spans=[]
        for ordinal,line in enumerate(section):
            spans.append(Span(span_id=str(uuid.uuid4()),ordinal=ordinal,text=line,source_location=SourceLocation(line_start=start+ordinal+1,line_end=start+ordinal+1,paragraph=ordinal+1,message_ordinal=n+1 if kind=="email" else None,turn_ordinal=ordinal+1 if kind=="transcript" else None,timestamp_label=None)))
        records.append((spans,time,hashlib.sha256("\n".join(section).encode()).hexdigest()))
    return records

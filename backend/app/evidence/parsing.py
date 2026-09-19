"""Lossless line spans with explicit email bundle separators and original locations."""
import re, uuid, hashlib
from email.utils import parsedate_to_datetime
from ..contracts.models import SourceTime, Span, SourceLocation

def parse(text, kind):
    if not text.strip() or "\x00" in text: raise ValueError("invalid text")
    lines=text.splitlines()
    starts=[0]
    if kind=="email":
        header=re.compile(r"^(?:From|Från|Date|Datum|Sent|Skickat|To|Till|Cc|Kopia|Subject|Ämne):\s*",re.I)
        for i,line in enumerate(lines):
            if not re.match(r"^(?:From|Från):\s*",line,re.I) or i==0: continue
            previous="\n".join(lines[max(0,i-3):i]).casefold()
            if "forwarded message" in previous or "vidarebeford" in previous or "original message" in previous: continue
            block="\n".join(lines[i:i+12])
            if re.search(r"^(?:Date|Datum|Sent|Skickat):",block,re.I|re.M) and re.search(r"^(?:Subject|Ämne):",block,re.I|re.M): starts.append(i)
    starts.append(len(lines)); records=[]
    for n,(start,end) in enumerate(zip(starts,starts[1:])):
        section=lines[start:end]; time=SourceTime(value=None,precision="unknown",timezone=None)
        for line in section[:20]:
            match=re.match(r"(?:Date|Datum|Sent|Skickat|Meeting date|Mötesdatum):\s*(.*)",line,re.I)
            if not match: continue
            val=match[1].strip()
            if re.fullmatch(r"\d{4}(?:-\d{2}){0,2}",val):
                precision={4:"year",7:"month",10:"day"}[len(val)]; time=SourceTime(value=val,precision=precision,timezone=None)
            else:
                try:
                    dt=parsedate_to_datetime(val)
                    if dt.tzinfo: time=SourceTime(value=dt.isoformat(),precision="instant",timezone=str(dt.tzinfo))
                except (ValueError,TypeError): pass
            break
        spans=[]; turn=0; in_body=False
        for ordinal,line in enumerate(section):
            if kind=="transcript" and line.strip():
                in_body=True
                if re.match(r"^(?:\[[^]]+\]\s*)?[A-Za-zÅÄÖåäö][^:]{0,80}:\s*",line): turn += 1
            speaker = turn if kind=="transcript" and in_body else None
            spans.append(Span(span_id=str(uuid.uuid4()),ordinal=ordinal,text=line,source_location=SourceLocation(line_start=start+ordinal+1,line_end=start+ordinal+1,paragraph=None,message_ordinal=n+1 if kind=="email" else None,turn_ordinal=speaker,timestamp_label=None)))
        records.append((spans,time,hashlib.sha256("\n".join(section).encode()).hexdigest()))
    return records

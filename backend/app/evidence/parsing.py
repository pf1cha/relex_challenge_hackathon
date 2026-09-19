"""Lossless corpus-aware boundaries with explicit message/turn provenance."""
from __future__ import annotations

import hashlib
import re
import uuid
from email.utils import parsedate_to_datetime

from ..contracts.models import SourceLocation, SourceTime, Span


EMAIL_FIELDS = {
    "from": r"From|Från|Von|De",
    "date": r"Date|Datum|Sent|Skickat|Gesendet|Envoyé|Fecha",
    "to": r"To|Till|An|À|Para",
    "cc": r"Cc|Kopia",
    "subject": r"Subject|Ämne|Betreff|Objet|Asunto",
}
FIELD = re.compile(r"^(?P<name>"+"|".join(EMAIL_FIELDS.values())+r"):\s*(?P<value>.*)$",re.I)
FROM = re.compile(r"^(?:"+EMAIL_FIELDS["from"]+r"):\s*",re.I)
DATE = re.compile(r"^(?:"+EMAIL_FIELDS["date"]+r"):\s*(.*)$",re.I)
SUBJECT = re.compile(r"^(?:"+EMAIL_FIELDS["subject"]+r"):\s*",re.I)
FORWARD = re.compile(r"forwarded message|original message|vidarebeford|weitergeleitete nachricht|message transféré",re.I)
TRANSCRIPT_TIME = re.compile(r"^(?:(\d+):)?(\d{1,2}):(\d{2})(?:(\d+):(\d{2}))?$|^(\d+):(\d{2})$")
SPOKEN = re.compile(r"^(?P<speaker>[\w .,'’\-ÅÄÖåäöØøÆæÉéÜü]{2,80})\s+(?P<time>\d+\s+(?:seconds?|minutes?(?:\s+\d+\s+seconds?)?))$",re.I)
COLON_TURN = re.compile(r"^(?:\[(?P<stamp>[^]]+)\]\s*)?(?P<speaker>[\w .,'’\-ÅÄÖåäöØøÆæÉéÜü]{2,80}):\s*(?P<body>.*)$")
REPORT_BOUNDARY = re.compile(r"^(?:={5,}|-{5,}|#{1,3}\s+|Report(?:ing)?\s+(?:date|period):|Status\s+report:)",re.I)


def _source_time(lines):
    for line in lines[:24]:
        match=DATE.match(line) or re.match(r"^(?:Meeting date|Mötesdatum|Date):\s*(.*)$",line,re.I)
        if not match:continue
        value=match.group(1).strip()
        if re.fullmatch(r"\d{4}(?:-\d{2}){0,2}",value):
            return SourceTime(value=value,precision={4:"year",7:"month",10:"day"}[len(value)],timezone=None)
        try:
            parsed=parsedate_to_datetime(value)
            if parsed.tzinfo:return SourceTime(value=parsed.isoformat(),precision="instant",timezone=str(parsed.tzinfo))
        except (ValueError,TypeError,OverflowError):pass
    return SourceTime(value=None,precision="unknown",timezone=None)


def _email_starts(lines):
    candidates=[]
    for index,line in enumerate(lines):
        if not FROM.match(line):continue
        block=lines[max(0,index-4):min(len(lines),index+12)]
        if any(DATE.match(value) for value in block) and any(SUBJECT.match(value) for value in block):
            candidates.append(index)
    if not candidates:return [0]
    return [0,*candidates[1:]]


def _email_provenance(lines,start):
    provenance="original"
    values=[]
    for offset,line in enumerate(lines):
        if offset and FROM.match(line):
            previous="\n".join(lines[max(0,offset-4):offset])
            if FORWARD.search(previous):provenance="forwarded"
            elif any(DATE.match(value) for value in lines[offset:offset+12]) and any(SUBJECT.match(value) for value in lines[offset:offset+12]):
                provenance="quoted"
        values.append(provenance)
    return values


def _transcript_locations(lines):
    locations=[];turn=0;speaker=None;stamp=None
    for index,line in enumerate(lines):
        stripped=line.strip();spoken=SPOKEN.match(stripped);colon=COLON_TURN.match(stripped)
        if spoken:
            turn+=1;speaker=spoken.group("speaker").strip();stamp=spoken.group("time")
        elif colon and not FIELD.match(stripped) and (colon.group("stamp") or index>10):
            turn+=1;speaker=colon.group("speaker").strip();stamp=colon.group("stamp")
        elif index+3<len(lines) and stripped and TRANSCRIPT_TIME.match(lines[index+1].strip()) and re.fullmatch(r"[A-ZÅÄÖ]{1,5}",lines[index+2].strip()):
            speaker=stripped
        locations.append((turn or None,speaker if turn else None,stamp if turn else None))
    return locations


def parse(text,kind):
    if not text.strip() or "\x00" in text:raise ValueError("invalid text")
    lines=text.splitlines()
    if kind=="email":starts=_email_starts(lines)
    elif kind=="report":starts=[0]+[i for i,line in enumerate(lines[1:],1) if REPORT_BOUNDARY.match(line) and i>1 and not lines[i-1].strip()]
    else:starts=[0]
    starts=sorted(set(starts));starts.append(len(lines));records=[]
    transcript_locations=_transcript_locations(lines) if kind=="transcript" else None
    paragraph=0
    for message_ordinal,(start,end) in enumerate(zip(starts,starts[1:]),1):
        section=lines[start:end];provenance=_email_provenance(section,start) if kind=="email" else ["original"]*len(section)
        spans=[]
        for relative,line in enumerate(section):
            if line.strip() and (relative==0 or not section[relative-1].strip()):paragraph+=1
            turn,speaker,stamp=transcript_locations[start+relative] if transcript_locations else (None,None,None)
            spans.append(Span(span_id=str(uuid.uuid4()),ordinal=relative,text=line,source_location=SourceLocation(
                line_start=start+relative+1,line_end=start+relative+1,paragraph=paragraph if line.strip() else None,
                message_ordinal=message_ordinal if kind=="email" else None,turn_ordinal=turn,
                timestamp_label=stamp,speaker_label=speaker,provenance=provenance[relative])))
        source_hash=hashlib.sha256("\n".join(section).encode()).hexdigest()
        records.append((spans,_source_time(section),source_hash))
    return records

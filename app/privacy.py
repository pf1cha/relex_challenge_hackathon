"""Identify privacy data before summaries/embeddings; fail ambiguous attribution."""
import re
from . import provider,store
PROMPT='''Extract every person's names (including abbreviated speaker names) and contact information from this record. Return {"people":[{"name":"canonical full name","aliases":["exact name variants in text"],"contacts":["exact email/phone strings"]}],"private_lines":[line numbers consisting of home address or personal-life discussion],"ambiguous":false,"reason":""}. Include all email/phone strings as contacts. Work decisions must not be dropped. If a line mixes private and work details, return "private_spans":[{"line":1,"text":"exact private substring"}] instead of private_lines. Do not classify office address as personal residence. If attribution cannot be determined, ambiguous=true. Line numbers are one-based. Do not invent people. Quoted/forwarded speakers remain separate from sender. A name is not proof two people are identical.'''
def clean(c,p,text):
    lines=text.splitlines()
    data=provider.structured(PROMPT,'\n'.join(f'{i+1}: {line}' for i,line in enumerate(lines)))
    if data.get('ambiguous'):raise ValueError('Ambiguous privacy extraction; correct and re-upload')
    known=store.items(c,p,'person'); resolved=[]
    for person in data.get('people',[]):
        name=person['name'].strip(); aliases=set(person.get('aliases',[])+[name]); contacts=set(person.get('contacts',[]))
        if not any(x and x in text for x in aliases|contacts):continue
        contact_matches=[k for k in known if set(k.get('contacts',[])) & contacts and not k.get('deleted')]
        same=[k for k in known if name in k.get('aliases',[]) and not k.get('deleted')]
        if len(contact_matches)>1:raise ValueError('Ambiguous matching contacts; correct and re-upload')
        if contact_matches:target=contact_matches[0]
        elif same and not contacts:
            if len(same)>1:raise ValueError('Ambiguous shared name; add distinguishing contacts and re-upload')
            target=same[0]
        else:
            target={'id':store.uid(),'name':name,'aliases':[],'contacts':[],'category':'employee','deleted':False}
            known.append(target)
        target['aliases']=sorted(set(target['aliases'])|aliases);target['contacts']=sorted(set(target['contacts'])|contacts)
        store.put(c,p,'person',target);resolved.append(target)
    replacements={}
    for person in resolved:
        for s in person['aliases']+person['contacts']:
            if s in text:
                if s in replacements and replacements[s]!=person['id']:raise ValueError('Ambiguous name occurrence inside record; correct and re-upload')
                replacements[s]=person['id']
    private=set(data.get('private_lines',[]));spans=data.get('private_spans',[])
    for i,line in enumerate(lines):
        if i+1 in private:lines[i]='[private discussion removed]';continue
        for span in spans:
            if span['line']==i+1:
                if not span['text'] or span['text'] not in line:raise ValueError('Invalid privacy source span')
                line=line.replace(span['text'],'[private detail removed]')
        for s in sorted(replacements,key=len,reverse=True):
            line=re.sub(r'(?<!\w)'+re.escape(s)+r'(?!\w)',lambda m:'PERSON_'+replacements[s].replace('-',''),line)
        lines[i]=line
    result='\n'.join(lines)
    if re.search(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',result):raise ValueError('Unattributed contact remains; correct and re-upload')
    return result,sorted({x['id'] for x in resolved})
def token(id):return 'PERSON_'+id.replace('-','')
def display(c,p,value):
    if isinstance(value,str):
        for person in store.items(c,p,'person'):
            value=value.replace(token(person['id']),'[deleted user]' if person.get('deleted') else person['name'])
        return value
    if isinstance(value,list):return [display(c,p,x) for x in value]
    if isinstance(value,dict):return {k:display(c,p,v) for k,v in value.items()}
    return value

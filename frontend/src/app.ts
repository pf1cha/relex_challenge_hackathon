import {api,ApiError,clearProject,clearSession,setCsrf,type Models} from "./api/client";
import "./style.css";
type Me=Models["Me"]; type Project=Models["Project"]; type Answer=Models["Answer"];
type Job=Models["Job"]; type Receipt=Models["Receipt"]; type SourcePage=Models["SourcePage"];
type PrivacyDiagnostic={id:string;record_id:string;record_version:number;span_id:string;start:number|null;end:number|null;kind:string;reason:string;state:"open"|"resolved";resolution:string|null;updated_at:string};
type Page<T>={items:T[];next_cursor:string|null};
const root=document.querySelector<HTMLDivElement>("#app")!;
let registering=false;
let me:Me|null=null, projects:Project[]=[], project:Project|null=null, view="documents";
let conversation:string|null=null, pending:{question:string;conversation_id:string;request_id:string}|null=null;
let questionDraft="", epoch=0, poll:number|undefined;
function el<K extends keyof HTMLElementTagNameMap>(tag:K,text?:string,cls?:string):HTMLElementTagNameMap[K]{
 const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(cls)node.className=cls;return node;
}
function button(text:string, action:()=>unknown, cls=""){const n=el("button",text,cls);n.onclick=()=>{Promise.resolve(action()).catch(showError)};return n;}
function input(label:string,type="text",value=""){const n=el("input");n.type=type;n.value=value;n.setAttribute("aria-label",label);n.placeholder=label;return n;}
function select(label:string, values:[string,string][], value=""){const n=el("select");n.setAttribute("aria-label",label);for(const [v,t]of values){const o=el("option",t);o.value=v;n.append(o);}if(values.some(([v])=>v===value))n.value=value;return n;}
function field(label:string,node:HTMLElement){const wrap=el("label",label,"field");wrap.append(node);return wrap;}
function locationLabel(location:Models["SourceLocation"]){return [
 location.line_start!==null?"Line "+location.line_start+(location.line_end!==location.line_start?"–"+location.line_end:""):"",
 location.paragraph!==null?"Paragraph "+location.paragraph:"",
 location.message_ordinal!==null?"Message "+location.message_ordinal:"",
 location.turn_ordinal!==null?"Turn "+location.turn_ordinal:"",
 location.timestamp_label||""].filter(Boolean).join(" · ");}
function sourceLink(receipt:Receipt){return receipt.source_url+"#spans="+receipt.evidence_ref.span_ids.map(encodeURIComponent).join(",");}
function base(){if(!project)throw new Error("Select a project");return "/api/projects/"+encodeURIComponent(project.id);}
function showError(error:unknown,target:HTMLElement=root.querySelector("#notice")||root){
 if(error instanceof DOMException&&error.name==="AbortError")return;
 if(error instanceof ApiError&&error.status===401){me=null;clearSession();render();target=root.querySelector("#notice")||root;}
 target.replaceChildren(el("p",error instanceof Error?error.message:"Request failed","error"));
}
async function list<T>(path:string){let items:T[]=[],cursor:string|null=null;do{
 const page:Page<T>=await api(path+(path.includes("?")?"&":"?")+"limit=100"+(cursor?"&cursor="+encodeURIComponent(cursor):""));
 items.push(...page.items);cursor=page.next_cursor;
 }while(cursor);return items;}
function reset(){epoch++;clearProject();conversation=null;pending=null;questionDraft="";if(poll)window.clearInterval(poll);document.querySelector("#receipt")?.remove();}
function render(skipView=false){
 root.className="app-shell";root.replaceChildren();const top=el("header","","topbar");const brand=el("div","","brand");brand.append(el("div","RELEX WORKSPACE","eyebrow"),el("h1","Memory With a Receipt"));top.append(brand);
 if(me){top.append(el("span",me.display_name));top.append(button("Sign out",async()=>{try{await api("/api/logout","POST");}finally{reset();clearSession();me=null;projects=[];project=null;render();}}));}
 root.append(top);const notice=el("div");notice.id="notice";notice.setAttribute("role","alert");root.append(notice);const barrier=el("div");barrier.id="barrier";barrier.setAttribute("role","status");root.append(barrier);
 if(!me){login();return;}
 const picker=select("Project",projects.map(p=>[p.id,p.name+" · "+p.role]),project?.id||"");
 picker.onchange=()=>{reset();project=projects.find(p=>p.id===picker.value)||null;history.replaceState(null,"","/");render();};
 const projectField=field("Project",picker);projectField.classList.add("project-picker");root.append(projectField);
 if(!project){root.append(el("p","No project access has been assigned to this account. Share your account ID with a project administrator: "+me.user_id));return;}
 const nav=el("nav","","workspace-nav");
 for(const name of ["documents","search","chat","overview","visualization",...(project.role==="admin"?["administration"]:[])])
 nav.append(button(name[0].toUpperCase()+name.slice(1),()=>{view=name;render();},`nav-item ${view===name?"selected":""}`));
 root.append(nav);const main=el("main","","content-shell");main.id="content";root.append(main);if(!skipView)renderView();
}
function login(){
 root.className="app-shell auth-shell";const form=el("form","","auth-card"),email=input("Email","email"),password=input("Password","password"),name=input("Display name");
 email.autocomplete="username";email.required=true;email.maxLength=320;
 password.autocomplete=registering?"new-password":"current-password";password.required=true;password.maxLength=4096;
 name.autocomplete="name";name.required=true;name.maxLength=255;
 if(registering){password.minLength=10;form.append(field("Display name",name),el("p","Create an account. An administrator must grant access to a project."));}
 const submit=el("button",registering?"Create account":"Sign in");submit.type="submit";
 form.append(field("Email",email),field(registering?"Password (at least 10 characters)":"Password",password),submit);
 form.onsubmit=async e=>{e.preventDefault();submit.disabled=true;try{
 me=await api<Me>(registering?"/api/register":"/api/login","POST",{
 email:email.value.trim(),password:password.value,...(registering?{display_name:name.value.trim()}:{})});
 password.value="";registering=false;setCsrf(me.csrf_token);await loadProjects();
 }catch(e){showError(e);}finally{submit.disabled=false;}};
 root.append(el("div","Evidence-backed workspace","auth-kicker"),el("h1","Memory With a Receipt","auth-title"),el("p","A calm place to review project knowledge with a clear source trail.","auth-copy"),form,button(registering?"Back to sign in":"Register",()=>{registering=!registering;render();},"secondary-action"));
}
async function loadProjects(){projects=await list<Project>("/api/projects");const source=location.pathname.match(/^\/projects\/([^/]+)\/sources\/([^/]+)$/);
 project=(source?projects.find(p=>p.id===decodeURIComponent(source[1])):projects[0])||null;render(!!source);
 if(source){if(!project){showError(new Error("This project is unavailable."));return;}const query=new URLSearchParams(location.search);
 await sourceView(decodeURIComponent(source[2]),Number(query.get("version")),query.get("span")||"");}}
async function renderView(){if(poll){clearInterval(poll);poll=undefined;}document.querySelector("#receipt")?.remove();const main=root.querySelector<HTMLElement>("#content");if(!main)return;const mark=++epoch;main.replaceChildren(el("p","Loading…"));
 try{await ({documents,search,chat,overview,visualization,administration}[view]||documents)(main,mark);}catch(e){if(mark===epoch)showError(e,main);}}
function current(mark:number){if(mark!==epoch)throw new DOMException("Project changed","AbortError");}
function pager<T>(container:HTMLElement,path:string,draw:(item:T)=>HTMLElement){let cursor:string|null=null;const more=button("Load more",load);const rows=el("div");container.append(rows,more);
 async function load(){more.disabled=true;try{const page=await api<Page<T>>(path+(cursor?"?cursor="+encodeURIComponent(cursor):""));for(const item of page.items)rows.append(draw(item));cursor=page.next_cursor;more.hidden=!cursor;if(!rows.children.length)rows.append(el("p","No items."));}finally{more.disabled=false;}}return load();}
async function documents(main:HTMLElement,mark:number){main.replaceChildren(el("h2","Documents"));
 const status=await api<Models["ProjectStatus"]>(base()+"/status");current(mark);
 if(status.write_barrier)main.append(el("p","Project cleanup is in progress. Uploads and chat writes are temporarily unavailable.","banner"));
 if(project?.role==="admin"){const form=el("form"),file=input("Text file","file");file.accept=".txt,text/plain";
 const kind=select("Record type",["email","transcript","report","specification"].map(x=>[x,x]));
 const upload=el("button","Upload");upload.type="submit";upload.disabled=status.write_barrier;form.append(field("UTF-8 text file",file),field("Record type",kind),upload);
 form.onsubmit=async e=>{e.preventDefault();const f=file.files?.[0];if(!f)return;upload.disabled=true;
 const data=new FormData();data.set("file",f);data.set("record_type",kind.value);
 try{const job=await api<Job>(base()+"/documents","POST",data);current(mark);main.append(jobRow(job));file.value="";await refreshJobs(main,mark);}catch(e){showError(e);}finally{upload.disabled=status.write_barrier;}};
 main.append(form);}
 await pager<Models["Document"]>(main,base()+"/documents",doc=>{const row=el("article");row.append(el("h3",doc.title),el("p",doc.record_type+" · "+doc.ai_status+" · "+doc.processing_state+" · "+doc.record_count+" records"));
 row.append(button("Open records",async()=>{const target=el("section");row.append(target);await pager<Models["RecordSummary"]>(target,base()+"/documents/"+encodeURIComponent(doc.id)+"/records",r=>{
 const entry=el("div");entry.append(button(r.title,()=>recordView(r.record_id)));return entry;});}));
 if(project?.role==="admin"){for(const action of ["activate","deactivate","delete"]){const b=button(action,async()=>{
 if(!confirm(action+" document “"+doc.title+"” ("+doc.id+") in project “"+project?.name+"”?"))return;
 const j=await api<Job>(base()+"/documents/"+encodeURIComponent(doc.id)+(action==="delete"?"":"/"+action),action==="delete"?"DELETE":"POST");row.append(jobRow(j));});
 b.disabled=doc.processing_state==="running"||doc.processing_state==="pending"||status.write_barrier;row.append(b);}}
 return row;});
 if(project?.role==="admin")await refreshJobs(main,mark);
}
function jobRow(job:Job){const row=el("article");row.dataset.jobId=job.id;row.append(el("strong",job.kind+" · "+job.state),el("p","Stage: "+job.stage+" · "+job.id));
 if(job.error_code)row.append(el("p",job.error_code,"error"));if(job.retryable&&job.state==="failed")row.append(button("Retry job",async()=>{const next=await api<Job>(base()+"/jobs/"+encodeURIComponent(job.id)+"/retry","POST");row.replaceWith(jobRow(next));}));return row;}
async function refreshJobs(main:HTMLElement,mark:number){let section=main.querySelector<HTMLElement>("[data-jobs]");
 if(!section){section=el("section");section.dataset.jobs="true";main.append(section);}
 let previousStates:Map<string,string>|null=null;
 const update=async()=>{const jobs=await list<Job>(base()+"/jobs");const status=await api<Models["ProjectStatus"]>(base()+"/status");current(mark);const banner=root.querySelector("#barrier");if(banner)banner.replaceChildren(...(status.write_barrier?[el("p","Project cleanup is in progress. Content-producing writes are temporarily unavailable.","banner")]:[]));if(!section?.isConnected)return;const completedChange=previousStates!==null&&jobs.some(j=>j.state==="completed"&&previousStates!.get(j.id)!=="completed");previousStates=new Map(jobs.map(j=>[j.id,j.state]));section.replaceChildren(el("h2","Processing jobs"),...jobs.map(jobRow));if(completedChange&&view==="documents")await renderView();};
 await update();if(poll)clearInterval(poll);poll=window.setInterval(()=>{update().catch(e=>{if(!(e instanceof DOMException))showError(e);});},3000);}
async function recordView(id:string){const mark=++epoch;if(poll){clearInterval(poll);poll=undefined;}const main=root.querySelector<HTMLElement>("#content")!;main.replaceChildren(el("h2","Source record"));
 let cursor:string|null=null;const spans=el("section"),more=button("Next record page",load);main.append(spans,more);
 async function load(){const page=await api<Models["RecordPage"]>(base()+"/records/"+encodeURIComponent(id)+(cursor?"?cursor="+encodeURIComponent(cursor):""));
 current(mark);spans.append(el("h3",page.record.title));for(const s of page.spans)spans.append(el("p",s.text));cursor=page.next_cursor;more.hidden=!cursor;spans.append(el("small",page.complete?"End of record":"More source content available"));}await load();}
async function sourceView(id:string,version:number,span:string,cursor?:string){const mark=++epoch;if(poll){clearInterval(poll);poll=undefined;}const main=root.querySelector<HTMLElement>("#content")!;main.replaceChildren(el("p","Loading source…"));
 try{const page=await api<SourcePage>(base()+"/sources/"+encodeURIComponent(id)+"?"+new URLSearchParams({version:String(version),span,...(cursor?{cursor}:{})}));current(mark);main.replaceChildren(el("h2",page.record.title),el("p",page.record.record_type+" · "+(page.record.source_time.value||"Date unknown")));
 const highlights=new Set([...page.highlighted_span_ids,...(location.hash.startsWith("#spans=")?location.hash.slice(7).split(",").map(decodeURIComponent):[])]);
 for(const item of page.spans){main.append(el("small",locationLabel(item.source_location)));const n=el(highlights.has(item.span_id)?"mark":"p",item.text);n.id="span-"+item.span_id;main.append(n);}
 if(page.previous_cursor)main.append(button("Previous source page",()=>sourceView(id,version,span,page.previous_cursor!)));
 if(page.next_cursor)main.append(button("Next source page",()=>sourceView(id,version,span,page.next_cursor!)));
 main.querySelector("mark")?.scrollIntoView({block:"center"});
 }catch(e){if(e instanceof DOMException&&e.name==="AbortError")return;showError(e,main);main.append(button("Return to chat and regenerate",()=>{view="chat";renderView();}));}}
async function search(main:HTMLElement,mark:number){const options=await api<Models["FilterOptions"]>(base()+"/filters");current(mark);main.replaceChildren(el("h2","Search evidence"));
 const form=el("form"),q=input("Search query"),from=input("From date","date"),to=input("To date","date");q.maxLength=8000;
 const type=select("Record type",[["","Any type"],...options.record_types.map(x=>[x,x] as [string,string])]);
 const doc=select("Source document",[["","Any document"],...options.documents.map(x=>[x.id,x.label] as [string,string])]);
 const topic=select("Topic",[["","Any topic"],...options.topics.map(x=>[x.id,x.label] as [string,string])]);
 const person=select("Person",[["","Any person"],...options.people.map(x=>[x.id,x.label] as [string,string])]);
 const submit=el("button","Search");submit.type="submit";form.append(q,field("From",from),field("To",to),type,doc,topic,person,submit);main.append(form);
 const results=el("section");main.append(results);let query:Record<string,unknown>|null=null,cursor:string|null=null;
 const more=button("More results",load);more.hidden=true;main.append(more);
 async function load(){if(!query)return;const page=await api<Models["SearchPage"]>(base()+"/search","POST",{...query,...(cursor?{cursor}:{})});current(mark);
 for(const hit of page.items){const row=el("article");row.append(el("h3",hit.record.title),el("p",hit.snippet),el("small",hit.description),button("Read record",()=>recordView(hit.record.record_id)));results.append(row);}
 cursor=page.next_cursor;more.hidden=!cursor;if(!results.children.length)results.append(el("p","No eligible evidence matches."));}
 form.onsubmit=async e=>{e.preventDefault();const filters:Record<string,string>={};for(const[k,v]of Object.entries({date_from:from.value,date_to:to.value,record_type:type.value,original_doc_id:doc.value,topic_id:topic.value,person_id:person.value}))if(v)filters[k]=v;
 query={query:q.value,filters};cursor=null;results.replaceChildren();try{await load();}catch(e){showError(e,results);}};
}
async function citation(answerId:string,receiptId:string,anchor:HTMLElement){document.querySelector("#receipt")?.remove();const panel=el("aside");panel.id="receipt";panel.setAttribute("role","dialog");panel.setAttribute("aria-label","Source receipt");panel.append(el("p","Checking current source…"));root.append(panel);
 try{const receipt=await api<Receipt>(base()+"/answers/"+encodeURIComponent(answerId)+"/receipts/"+encodeURIComponent(receiptId));if(!panel.isConnected)return;
 panel.replaceChildren(button("Close",()=>panel.remove()),el("h3",receipt.source_title),el("p",receipt.record_type+" · "+(receipt.source_time.value||"Date unknown")),el("small",receipt.source_locations.map(locationLabel).join("; ")),el("blockquote",receipt.quote));
 const link=el("a","Open cited source in new tab");link.href=sourceLink(receipt);link.target="_blank";link.rel="noopener";panel.append(link);
 }catch(e){if(panel.isConnected){showError(e,panel);panel.append(button("Regenerate answer",()=>{panel.remove();pending=null;view="chat";renderView();}));}}}
function answerNode(answer:Answer){const row=el("article");row.dataset.answerId=answer.id;
 if(answer.cannot_establish)row.append(el("p","Cannot establish the requested answer: "+answer.cannot_establish.replaceAll("_"," ")));
 for(const claim of answer.claims){const p=el("p",claim.text);for(const id of claim.receipt_ids){const b=button("↗",()=>citation(answer.id,id,b),"citation");b.setAttribute("aria-label","View supporting quote");b.onmouseenter=()=>{citation(answer.id,id,b).catch(showError)};b.onfocus=()=>{citation(answer.id,id,b).catch(showError)};p.append(b);}row.append(p);}
 row.append(el("small","Coverage: "+answer.coverage.state));for(const lim of answer.coverage.limitations)row.append(el("p",lim.code.replaceAll("_"," "),"muted"));return row;}
async function chat(main:HTMLElement,mark:number){main.replaceChildren(el("h2","Reviewed project chat"));
 const conversations=await list<Models["Conversation"]>(base()+"/conversations");current(mark);
 const choose=select("Conversation",[["","New chat"],...conversations.map(c=>[c.id,c.title] as [string,string])],conversation||"");
 choose.onchange=()=>{conversation=choose.value||null;pending=null;renderView();};main.append(choose);
 const messages=el("section");messages.id="messages";main.append(messages);
 if(conversation){for(const m of await list<Models["Message"]>(base()+"/conversations/"+encodeURIComponent(conversation)+"/messages")){current(mark);
 if(m.state==="available"&&m.role==="assistant"&&m.answer_id){try{messages.append(answerNode(await api<Answer>(base()+"/answers/"+encodeURIComponent(m.answer_id))));}catch(e){messages.append(el("p","Previous answer unavailable. Regenerate it."));}}
 else messages.append(el("p",m.state==="unavailable"?"Previous answer unavailable. Regenerate it.":m.text||m.unavailable_reason||m.state));}}
 current(mark);
 const form=el("form"),question=el("textarea");question.setAttribute("aria-label","Question");question.maxLength=8000;question.required=true;question.value=questionDraft;
 question.oninput=()=>{questionDraft=question.value;if(pending&&pending.question!==question.value)pending=null;};
 const send=el("button",pending?"Retry question":"Ask");send.type="submit";form.append(question,send);main.append(form);
 const status=await api<Models["ProjectStatus"]>(base()+"/status");current(mark);send.disabled=status.write_barrier;
 if(status.write_barrier)main.append(el("p","Project cleanup is in progress. Your unsent text stays only in this tab.","banner"));
 form.onsubmit=async e=>{e.preventDefault();send.disabled=true;const processing=el("p","Finding evidence and independently reviewing the answer…");messages.append(processing);
 try{if(!conversation){const c=await api<Models["Conversation"]>(base()+"/conversations","POST",{});conversation=c.id;}
 if(!pending)pending={question:question.value,conversation_id:conversation,request_id:crypto.randomUUID()};
 const answer=await api<Answer>(base()+"/chat","POST",pending);current(mark);processing.replaceWith(answerNode(answer));pending=null;questionDraft="";question.value="";send.textContent="Ask";
 }catch(e){processing.remove();showError(e);if(e instanceof ApiError&&(!e.retryable||["evidence_changed","answer_unavailable","idempotency_conflict"].includes(e.code)))pending=null;send.textContent=pending?"Retry question":"Ask";}finally{send.disabled=false;}};}
async function overview(main:HTMLElement,mark:number){const data=await api<Models["Overview"]>(base()+"/overview");current(mark);main.replaceChildren(el("h2","Project overview"),el("p","State: "+data.state));
 if(data.state==="ready")for(const claim of data.claims){const row=el("article",claim.text);for(const id of claim.receipt_ids){const b=button("View source",async()=>{
 const fresh=await api<Models["Overview"]>(base()+"/overview");if(fresh.state!=="ready"||fresh.id!==data.id)throw new Error("Overview changed. Reload it.");
 const receipt=fresh.receipts.find(r=>r.id===id);if(!receipt)throw new Error("Source unavailable.");
 const detail=el("blockquote",receipt.quote),link=el("a",receipt.source_title);link.href=sourceLink(receipt);link.target="_blank";link.rel="noopener";detail.append(link);row.append(detail);});row.append(b);}main.append(row);}}
async function visualization(main:HTMLElement,mark:number){const status=await api<Models["ProjectStatus"]>(base()+"/status");current(mark);
 main.replaceChildren(el("h2","Project status"),el("p","Actual visualization content is deferred."),el("p",status.eligible_documents+" eligible documents · "+status.eligible_records+" eligible records"),el("p",status.write_barrier?"Cleanup write barrier active":"Project writes available"));}
async function administration(main:HTMLElement,mark:number){main.replaceChildren(el("h2","Project administration"),el("p","Grant registered accounts access to this project. Admins can manage membership and documents. Personnel associations and erasure are separate."));
 const members=el("section");main.append(members,el("h3","Members"));
 await pager<Models["Member"]>(members,base()+"/members",m=>{const row=el("article",m.display_name+" · "+m.role+" · "+m.user_id);row.append(button("Remove membership",async()=>{if(!confirm("Remove membership for "+m.display_name+" ("+m.user_id+") from "+project?.name+"? This does not erase their personal information."))return;await api(base()+"/members/"+encodeURIComponent(m.user_id),"DELETE");row.remove();}));return row;});
 const memberForm=el("form"),user=input("Registered email or account ID"),role=select("Role",[["member","Member"],["admin","Admin"]]),save=el("button","Grant or update access");save.type="submit";user.required=true;user.maxLength=320;memberForm.append(field("Registered email or account ID",user),field("Project role",role),save);
 memberForm.onsubmit=async e=>{e.preventDefault();try{const identity=user.value.trim();if(!confirm("Grant "+role.value+" access to "+identity+" in "+project?.name+"?"))return;save.disabled=true;await api(base()+"/members","POST",{...(identity.includes("@")?{email:identity}:{user_id:identity}),role:role.value});await renderView();}catch(e){showError(e);}finally{save.disabled=false;}};main.append(memberForm,el("h3","People"));
 await pager<Models["Person"]>(main,base()+"/people",p=>{const row=el("article",p.display_name+" · "+p.kind+" · "+p.id+" · "+p.state);
 const erase=button("Erase personal information",async()=>{if(!confirm("Erase personal information for "+p.display_name+" ("+p.id+") in "+project?.name+"? Project decisions will remain with [deleted user] attribution."))return;row.append(jobRow(await api<Job>(base()+"/people/"+encodeURIComponent(p.id)+"/erase","POST")));});erase.disabled=p.state==="erasing";row.append(erase);
 return row;});
 const form=el("form"),id=input("Person ID (blank for new identity)"),name=input("Display name"),kind=select("Person kind",[["client","Client"],["employee","Employee"]]),contact=input("Contact value"),contactKind=select("Contact kind",[["email","Email"],["phone","Phone"],["postal_address","Postal address"]]),add=el("button","Associate person");add.type="submit";name.maxLength=255;contact.maxLength=500;
 form.append(id,name,kind,contactKind,contact,add);form.onsubmit=async e=>{e.preventDefault();try{await api(base()+"/people","POST",{...(id.value?{person_id:id.value}:{}),display_name:name.value,kind:kind.value,contacts:contact.value?[{kind:contactKind.value,value:contact.value}]:[]});renderView();}catch(e){showError(e);}};main.append(form,el("h3","Privacy diagnostics"));
 await pager<PrivacyDiagnostic>(main,base()+"/privacy/diagnostics",diagnostic=>{const row=el("article");
  row.append(el("strong",diagnostic.kind+" · "+diagnostic.state),el("p",diagnostic.reason),el("small","Record "+diagnostic.record_id+" · version "+diagnostic.record_version+" · span "+diagnostic.span_id+(diagnostic.start===null?"":" · offsets "+diagnostic.start+"–"+diagnostic.end)));
  if(diagnostic.state==="open"){const resolution=select("Privacy resolution",[["organization","Organization"],["role","Operational role"],["system_code","System code"],["contact","Contact"],["personal_identifier","Personal identifier"],["private_cause","Private cause"],["bind:","Bind to existing person ID"]]);const personId=input("Existing person ID");personId.hidden=true;resolution.onchange=()=>{personId.hidden=resolution.value!=="bind:";};const resolve=button("Apply resolution",async()=>{const value=resolution.value==="bind:"?"bind:"+personId.value.trim():resolution.value;if(!confirm("Apply this source-version-bound privacy resolution? The record will be reprocessed before publication."))return;await api(base()+"/privacy/diagnostics/"+encodeURIComponent(diagnostic.id)+"/resolve","POST",{resolution:value});await renderView();});row.append(resolution,personId,resolve);}
  return row;});
 await refreshJobs(main,mark);
}
async function start(){try{me=await api<Me>("/api/me");setCsrf(me.csrf_token);await loadProjects();}catch{me=null;render();}}
start();

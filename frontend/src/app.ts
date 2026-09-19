import {api,ApiError,clearProject,clearSession,setCsrf,type Models} from "./api/client";
import "./style.css";
type Me=Models["Me"]; type Project=Models["Project"]; type Answer=Models["Answer"];
type Job=Models["Job"]; type Receipt=Models["Receipt"]; type SourcePage=Models["SourcePage"];
type TimelineRecord=Models["TimelineRecord"];
type PrivacyDiagnostic={id:string;record_id:string;record_version:number;span_id:string;start:number|null;end:number|null;kind:string;reason:string;state:"open"|"resolved";resolution:string|null;updated_at:string};
type Page<T>={items:T[];next_cursor:string|null};
const root=document.querySelector<HTMLDivElement>("#app")!;
let registering=false;
let me:Me|null=null, projects:Project[]=[], project:Project|null=null, view="documents";
let conversation:string|null=null, pending:{question:string;conversation_id:string;request_id:string}|null=null;
let questionDraft="", epoch=0, poll:number|undefined;
const pageNames=["documents","search","chat","overview","visualization","administration"] as const;
const pageLabels:Record<string,string>={documents:"Documents",search:"Evidence search",chat:"AI chat",overview:"Overview",visualization:"Project status",administration:"Administration"};
const pageDescriptions:Record<string,string>={
 documents:"Browse the source material available to this workspace.",
 search:"Find exact records, people, topics, and dates across approved sources.",
 chat:"Ask questions and verify every answer against its source receipt.",
 overview:"Review the current evidence-backed summary of this project.",
 visualization:"Monitor the evidence set and workspace availability.",
 administration:"Manage workspace access, people, and document processing."
};
function el<K extends keyof HTMLElementTagNameMap>(tag:K,text?:string,cls?:string):HTMLElementTagNameMap[K]{
 const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(cls)node.className=cls;return node;
}
function button(text:string, action:()=>unknown, cls=""){const n=el("button",text,cls);n.onclick=()=>{Promise.resolve(action()).catch(showError)};return n;}
function pagePath(name:string,projectId=project?.id){return projectId?"/#/projects/"+encodeURIComponent(projectId)+"/"+name:"/";}
function navigate(name:string){view=name;history.pushState({view:name},"",pagePath(name));render();}
function routeView(projectId:string){const match=location.hash.match(/^#\/projects\/([^/]+)\/([^/]+)$/);if(!match||decodeURIComponent(match[1])!==projectId)return "documents";return pageNames.includes(match[2] as typeof pageNames[number])?match[2]:"documents";}
function pageLink(name:string,selected:boolean){const link=el("a",pageLabels[name]||name,selected?"selected":"");link.href=pagePath(name);if(selected)link.setAttribute("aria-current","page");link.dataset.view=name;link.onclick=event=>{if(event.button!==0||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;event.preventDefault();navigate(name);};return link;}
function input(label:string,type="text",value=""){const n=el("input");n.type=type;n.value=value;n.setAttribute("aria-label",label);n.placeholder=label;return n;}
function select(label:string, values:[string,string][], value=""){const n=el("select");n.setAttribute("aria-label",label);for(const [v,t]of values){const o=el("option",t);o.value=v;n.append(o);}if(values.some(([v])=>v===value))n.value=value;return n;}
function field(label:string,node:HTMLElement){const wrap=el("label",label,"field");wrap.append(node);return wrap;}
function pageHeader(title:string,description:string,eyebrow="Workspace"){const header=el("header","","page-header");header.append(el("span",eyebrow,"eyebrow"),el("h2",title),el("p",description,"page-description"));return header;}
function emptyState(title:string,description:string){const state=el("div","","empty-state");state.append(el("strong",title),el("p",description));return state;}
function locationLabel(location:Models["SourceLocation"]){return [
 location.line_start!==null?"Line "+location.line_start+(location.line_end!==location.line_start?"–"+location.line_end:""):"",
 location.paragraph!==null?"Paragraph "+location.paragraph:"",
 location.message_ordinal!==null?"Message "+location.message_ordinal:"",
 location.turn_ordinal!==null?"Turn "+location.turn_ordinal:"",
 location.timestamp_label||""].filter(Boolean).join(" · ");}
function sourceLink(receipt:Receipt){return receipt.source_url+"#spans="+receipt.evidence_ref.span_ids.map(encodeURIComponent).join(",");}
function projectBase(projectId:string){return "/api/projects/"+encodeURIComponent(projectId);}
function base(){if(!project)throw new Error("Select a project");return projectBase(project.id);}
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
 root.className="app-shell";root.replaceChildren();const top=el("header","","app-header");
 const brand=el("div","","brand");brand.append(el("span","R","brand-mark"));const brandCopy=el("div","","brand-copy");brandCopy.append(el("h1","Relex Evidence"),el("p","Verifiable project knowledge","brand-tagline"));brand.append(brandCopy);top.append(brand);
 if(!me){top.classList.add("auth-header");top.append(el("span","Private project workspace","auth-header-note"));}
 if(me){const account=el("div","","account");const avatar=el("span",me.display_name.trim().slice(0,1).toUpperCase(),"account-avatar");const accountCopy=el("span","","account-copy");accountCopy.append(el("strong",me.display_name,"account-name"),el("small","Signed in","account-status"));account.append(avatar,accountCopy);account.append(button("Sign out",async()=>{try{await api("/api/logout","POST");}finally{reset();clearSession();me=null;projects=[];project=null;render();}},"button-quiet"));top.append(account);}
 root.append(top);const notice=el("div");notice.id="notice";notice.setAttribute("role","alert");const barrier=el("div");barrier.id="barrier";barrier.setAttribute("role","status");
 if(!me){root.append(notice,barrier);login();return;}
 const layout=el("div","","app-layout"),sidebar=el("aside","","sidebar"),stage=el("div","","app-stage");
 const workspace=el("section","","workspace-bar");const workspaceLabel=el("div","","workspace-label");workspaceLabel.append(el("span","CURRENT WORKSPACE","eyebrow"),el("strong",project?.name||"Choose a workspace"));workspace.append(workspaceLabel);
 const picker=select("Project",projects.map(p=>[p.id,p.name+" · "+p.role]),project?.id||"");picker.className="project-select";
 picker.onchange=()=>{reset();project=projects.find(p=>p.id===picker.value)||null;view="documents";history.pushState({view},"",pagePath(view,project?.id));render();};
 workspace.append(field("Switch workspace",picker));sidebar.append(workspace);
 if(!project){stage.append(notice,barrier,emptyState("No workspace access","Ask an administrator to grant access for account "+me.user_id+"."));layout.append(sidebar,stage);root.append(layout);return;}
 const nav=el("nav","","primary-nav");nav.setAttribute("aria-label","Primary navigation");
 for(const name of ["documents","search","chat","overview","visualization",...(project.role==="admin"?["administration"]:[])])nav.append(pageLink(name,view===name));
 sidebar.append(nav);const sidebarFoot=el("div","","sidebar-foot");sidebarFoot.append(el("span",project.role.toUpperCase(),"role-badge"),el("small","Access is scoped to this workspace."));sidebar.append(sidebarFoot);
 const main=el("main","","content-panel");main.id="content";stage.append(notice,barrier,main);layout.append(sidebar,stage);root.append(layout);if(!skipView)renderView();
}
function login(){
 const auth=el("main","","auth-layout"),intro=el("section","","auth-intro");intro.append(el("span","RELEX EVIDENCE WORKSPACE","eyebrow"),el("h2",registering?"Join your evidence workspace.":"Work from evidence, not memory."),el("p",registering?"Create your account first. A workspace administrator can then grant access to the right projects.":"Search approved project sources, ask evidence-backed questions, and return to the exact passage behind every answer."));
 const trust=el("div","","trust-list");for(const item of ["Project-scoped access","Reviewed answers","Exact source receipts"])trust.append(el("span",item));intro.append(trust);auth.append(intro);
 const form=el("form","","auth-form"),email=input("Email","email"),password=input("Password","password"),name=input("Display name");
 email.autocomplete="username";email.required=true;email.maxLength=320;
 password.autocomplete=registering?"new-password":"current-password";password.required=true;password.maxLength=4096;
 name.autocomplete="name";name.required=true;name.maxLength=255;
 if(registering){password.minLength=10;form.append(el("div","Create your account","form-title"),el("p","Registration creates your identity; workspace access is granted separately.","form-description"),field("Display name",name));}
 else form.append(el("div","Sign in","form-title"),el("p","Use the account connected to your project workspace.","form-description"));
 const submit=el("button",registering?"Create account":"Sign in");submit.type="submit";
 form.append(field("Email",email),field(registering?"Password (at least 10 characters)":"Password",password),submit);
 form.onsubmit=async e=>{e.preventDefault();submit.disabled=true;try{
 me=await api<Me>(registering?"/api/register":"/api/login","POST",{
 email:email.value.trim(),password:password.value,...(registering?{display_name:name.value.trim()}:{})});
 password.value="";registering=false;setCsrf(me.csrf_token);await loadProjects();
 }catch(e){showError(e);}finally{submit.disabled=false;}};
 const switcher=el("div","","auth-switch");switcher.append(el("span",registering?"Already registered?":"New to Relex?"));const toggle=button(registering?"Sign in":"Create account",()=>{registering=!registering;render();},"button-link");toggle.type="button";switcher.append(toggle);form.append(switcher);auth.append(form);root.append(auth);
}
async function loadProjects(){projects=await list<Project>("/api/projects");const source=location.pathname.match(/^\/projects\/([^/]+)\/sources\/([^/]+)$/);
 const routeProject=location.hash.match(/^#\/projects\/([^/]+)(?:\/|$)/);
 project=(source?projects.find(p=>p.id===decodeURIComponent(source[1])):routeProject?projects.find(p=>p.id===decodeURIComponent(routeProject[1])):projects[0])||null;
 if(project&&!source){view=routeView(project.id);if(view==="administration"&&project.role!=="admin")view="documents";}render(!!source);
 if(source){if(!project){showError(new Error("This project is unavailable."));return;}const query=new URLSearchParams(location.search);
 await sourceView(decodeURIComponent(source[2]),Number(query.get("version")),query.get("span")||"");}}
async function renderView(){if(poll){clearInterval(poll);poll=undefined;}document.querySelector("#receipt")?.remove();const main=root.querySelector<HTMLElement>("#content");if(!main)return;main.dataset.view=view;const mark=++epoch;main.replaceChildren(el("p","Loading…"));
 try{await ({documents,search,chat,overview,visualization,administration}[view]||documents)(main,mark);}catch(e){if(mark===epoch)showError(e,main);}}
function current(mark:number){if(mark!==epoch)throw new DOMException("Project changed","AbortError");}
function pager<T>(container:HTMLElement,path:string,draw:(item:T)=>HTMLElement){let cursor:string|null=null;const more=button("Load more",load);const rows=el("div","","pager-rows");container.append(rows,more);
 async function load(){more.disabled=true;try{const page=await api<Page<T>>(path+(cursor?"?cursor="+encodeURIComponent(cursor):""));for(const item of page.items)rows.append(draw(item));cursor=page.next_cursor;more.hidden=!cursor;if(!rows.children.length)rows.append(el("p","No items."));}finally{more.disabled=false;}}return load();}
function disclosure(label:string,count:number,cls:string,open=false){const group=el("details","",cls),summary=el("summary"),name=el("span",label),badge=el("span",String(count),"group-count"),body=el("div","","group-body");summary.append(name,badge);group.append(summary,body);group.open=open;return {group,body};}
function dismissedJobKey(){return "relex:dismissed-jobs:"+(project?.id||"none");}
function dismissedJobIds(){try{const value=JSON.parse(localStorage.getItem(dismissedJobKey())||"[]");return new Set<string>(Array.isArray(value)?value.filter(item=>typeof item==="string"):[]);}catch{return new Set<string>();}}
function dismissJob(id:string){const ids=dismissedJobIds();ids.add(id);localStorage.setItem(dismissedJobKey(),JSON.stringify([...ids]));}
async function documents(main:HTMLElement,mark:number){main.replaceChildren(pageHeader("Documents",pageDescriptions.documents,"Library"));
 const status=await api<Models["ProjectStatus"]>(base()+"/status");current(mark);
 const projectTypes=(await api<Page<{name:string}>>(base()+"/types")).items.map(x=>x.name);
 const summary=el("section","","library-summary");for(const [value,label] of [[status.eligible_documents,"AI-ready documents"],[status.eligible_records,"Searchable records"],[status.write_barrier?"Paused":"Ready","Ingestion"]]){const item=el("div","","summary-item");item.append(el("strong",String(value)),el("span",String(label)));summary.append(item);}main.append(summary);
 if(status.write_barrier)main.append(el("p","Project cleanup is in progress. Uploads and chat writes are temporarily unavailable.","banner"));
 const currentProject=project;if(currentProject?.role==="admin"){const form=el("form","","toolbar-form upload-form"),file=input("Text file","file");file.accept=".txt,text/plain";
 const kind=select("Record type",projectTypes.map(x=>[x,x]));
 const adminProjects=projects.filter(item=>item.role==="admin"),destination=select("Destination project",adminProjects.map(item=>[item.id,item.name]),currentProject.id),assignment=el("div");assignment.setAttribute("role","status");
 destination.onchange=async()=>{try{const targetTypes=(await api<Page<{name:string}>>(projectBase(destination.value)+"/types")).items.map(x=>x.name);kind.replaceChildren(...targetTypes.map(type=>el("option",type)));}catch(e){showError(e,assignment);}};
 const upload=el("button","Upload and assign");upload.type="submit";upload.disabled=status.write_barrier;form.append(field("UTF-8 text file",file),field("Record type",kind),field("Destination project",destination),upload);
 form.onsubmit=async e=>{e.preventDefault();const f=file.files?.[0];if(!f)return;upload.disabled=true;
 const data=new FormData();data.set("file",f);data.set("record_type",kind.value);
 try{const target=adminProjects.find(item=>item.id===destination.value);if(!target)throw new Error("Select a project you administer.");const targetStatus=target.id===currentProject.id?status:await api<Models["ProjectStatus"]>(projectBase(target.id)+"/status");current(mark);if(targetStatus.write_barrier)throw new Error(target.name+" is temporarily unavailable while project cleanup is in progress.");
 const job=await api<Job>(projectBase(target.id)+"/documents","POST",data);current(mark);file.value="";assignment.replaceChildren(el("p",f.name+" was assigned to "+target.name+". Processing job "+job.id+" has started.","section-note"));if(target.id===currentProject.id)await refreshJobs(main,mark);
 else assignment.append(button("Open "+target.name,()=>{reset();project=target;view="documents";history.pushState({view},"",pagePath(view,target.id));render();},"button-secondary"));}catch(e){showError(e,assignment);}finally{upload.disabled=status.write_barrier;}};
 main.append(form,assignment);}
 const docs=await list<Models["Document"]>(base()+"/documents");current(mark);const library=el("section","","document-library");library.append(el("h2","Documents by record type"));const groups=new Map<string,Models["Document"][]>();for(const doc of docs){const items=groups.get(doc.record_type)||[];items.push(doc);groups.set(doc.record_type,items);}if(!docs.length)library.append(emptyState("No documents","Upload a document to add it to this workspace."));
 for(const [recordType,items] of [...groups].sort(([a],[b])=>a.localeCompare(b))){const {group,body}=disclosure(recordType,items.length,"record-type-group");for(const doc of items){const row=el("article","","document-card"),mainRow=el("div","","document-card-main"),copy=el("div","","document-card-copy"),meta=el("div","","card-meta"),actions=el("div","","document-actions"),target=el("section","","document-records");meta.append(el("span",doc.ai_status,"meta-chip"),el("span",doc.processing_state,"meta-chip"));copy.append(el("h3",doc.title),el("p",doc.record_count+" source records","muted"),meta);target.hidden=true;let recordsLoaded=false;const openRecords=button("Open records",async()=>{if(!recordsLoaded){recordsLoaded=true;await pager<Models["RecordSummary"]>(target,base()+"/documents/"+encodeURIComponent(doc.id)+"/records",r=>{const entry=el("div");entry.append(button(r.title,()=>recordView(r.record_id)));return entry;});}target.hidden=!target.hidden;openRecords.textContent=target.hidden?"Open records":"Hide records";});actions.append(openRecords);
 if(project?.role==="admin"){for(const action of ["activate","deactivate","delete"]){const b=button(action[0].toUpperCase()+action.slice(1),async()=>{
 if(!confirm(action+" document “"+doc.title+"” ("+doc.id+") in project “"+project?.name+"”?"))return;
 const j=await api<Job>(base()+"/documents/"+encodeURIComponent(doc.id)+(action==="delete"?"":"/"+action),action==="delete"?"DELETE":"POST");row.append(jobRow(j));});
 b.className=action==="delete"?"button-danger":"button-secondary";b.disabled=doc.processing_state==="running"||doc.processing_state==="pending"||status.write_barrier;actions.append(b);}}mainRow.append(copy,actions);row.append(mainRow,target);body.append(row);}library.append(group);}main.append(library);
 if(project?.role==="admin")await refreshJobs(main,mark);
}
function jobRow(job:Job,onDismiss?:()=>void){const row=el("article","","job-row");row.dataset.jobId=job.id;const copy=el("div","","job-copy");copy.append(el("strong",job.state),el("p","Stage: "+job.stage+" · "+job.id,"muted"));row.append(copy);
 if(job.error_code)copy.append(el("p",job.error_code==="privacy_unresolved"?"Privacy review could not complete. The source may contain an unresolved identity or contextual decision, or the privacy model returned an invalid plan. Resolve the privacy diagnostic, then retry.":job.error_code,"error"));if(job.retryable&&job.state==="failed")row.append(button("Retry job",async()=>{const next=await api<Job>(base()+"/jobs/"+encodeURIComponent(job.id)+"/retry","POST");row.replaceWith(jobRow(next,onDismiss));},"button-secondary"));if(job.state==="completed"&&onDismiss)row.append(button("Remove log",()=>{dismissJob(job.id);onDismiss();},"button-secondary remove-job"));return row;}
function renderJobGroups(section:HTMLElement,jobs:Job[]){const openKinds=new Set([...section.querySelectorAll<HTMLDetailsElement>(".job-type-group[open]")].map(group=>group.dataset.groupKey||"")),visible=jobs.filter(job=>!dismissedJobIds().has(job.id));section.replaceChildren(el("h2","Processing jobs"));if(!visible.length){section.append(el("p","No processing jobs to show.","muted"));return;}const groups=new Map<Job["kind"],Job[]>();for(const job of visible){const items=groups.get(job.kind)||[];items.push(job);groups.set(job.kind,items);}for(const [kind,items] of groups){const label=kind.replaceAll("_"," ").replace(/^./,letter=>letter.toUpperCase()),active=items.some(job=>job.state==="pending"||job.state==="running"),{group,body}=disclosure(label,items.length,"job-type-group",active||openKinds.has(kind));group.dataset.groupKey=kind;for(const job of items)body.append(jobRow(job,()=>renderJobGroups(section,jobs)));section.append(group);}}
async function refreshJobs(main:HTMLElement,mark:number){let section=main.querySelector<HTMLElement>("[data-jobs]");
 if(!section){section=el("section");section.dataset.jobs="true";main.append(section);}
 let previousStates:Map<string,string>|null=null;
 const update=async()=>{const jobs=await list<Job>(base()+"/jobs");const status=await api<Models["ProjectStatus"]>(base()+"/status");current(mark);const banner=root.querySelector("#barrier");if(banner)banner.replaceChildren(...(status.write_barrier?[el("p","Project cleanup is in progress. Content-producing writes are temporarily unavailable.","banner")]:[]));if(!section?.isConnected)return;const completedChange=previousStates!==null&&jobs.some(j=>j.state==="completed"&&previousStates!.get(j.id)!=="completed");previousStates=new Map(jobs.map(j=>[j.id,j.state]));renderJobGroups(section,jobs);if(completedChange&&view==="documents")await renderView();};
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
async function search(main:HTMLElement,mark:number){const options=await api<Models["FilterOptions"]>(base()+"/filters");current(mark);main.replaceChildren(pageHeader("Search evidence",pageDescriptions.search,"Discovery"));
 const workspace=el("section","","search-workspace"),form=el("form","","search-form"),q=input("Search terms"),from=input("From date","date"),to=input("To date","date");q.maxLength=8000;q.className="search-query";q.placeholder="Search names, decisions, topics, or exact phrases";
 const type=select("Record type",[["","Any type"],...options.record_types.map(x=>[x,x] as [string,string])]);
 const doc=select("Source document",[["","Any document"],...options.documents.map(x=>[x.id,x.label] as [string,string])]);
 const topic=select("Topic",[["","Any topic"],...options.topics.map(x=>[x.id,x.label] as [string,string])]);
 const person=select("Person",[["","Any person"],...options.people.map(x=>[x.id,x.label] as [string,string])]);
 const submit=el("button","Search evidence");submit.type="submit";
 const primary=el("div","","search-primary"),queryField=field("Search terms",q);queryField.classList.add("search-query-field");primary.append(queryField,submit);
 const filters=el("details","","search-filters"),filterSummary=el("summary"),filterCount=el("span","No filters selected","filter-count"),filterGrid=el("div","","filter-grid");filterSummary.append(el("span","Filters"),filterCount);filterGrid.append(field("From date",from),field("To date",to),field("Record type",type),field("Source document",doc),field("Topic",topic),field("Person",person));filters.append(filterSummary,filterGrid);form.append(primary,filters);
 const resultsPanel=el("section","","results-panel"),resultsHeader=el("header","","results-header"),resultsStatus=el("span","Ready to search","results-status"),results=el("section","","search-results");resultsHeader.append(el("h3","Results"),resultsStatus);results.append(emptyState("Search your approved evidence","Enter a phrase above, or use filters to narrow the source material."));resultsPanel.append(resultsHeader,results);
 workspace.append(form,resultsPanel);main.append(workspace);let query:Record<string,unknown>|null=null,cursor:string|null=null,resultCount=0;
 const more=button("Load more results",load,"button-secondary");more.hidden=true;resultsPanel.append(more);
 const filterInputs=[from,to,type,doc,topic,person];const updateFilterCount=()=>{const count=filterInputs.filter(control=>control.value).length;filterCount.textContent=count?count+" selected":"No filters selected";};for(const control of filterInputs)control.addEventListener("change",updateFilterCount);
 async function load(){if(!query)return;const page=await api<Models["SearchPage"]>(base()+"/search","POST",{...query,...(cursor?{cursor}:{})});current(mark);
 for(const hit of page.items){const row=el("article","","search-result");row.append(el("small",hit.description,"result-context"),el("h3",hit.record.title),el("p",hit.snippet),button("Open record",()=>recordView(hit.record.record_id),"button-secondary"));results.append(row);}
 resultCount+=page.items.length;cursor=page.next_cursor;more.hidden=!cursor;resultsStatus.textContent=resultCount+" result"+(resultCount===1?"":"s")+(cursor?" shown":"");if(!resultCount)results.append(emptyState("No matching evidence","Try a broader phrase or remove one of the filters."));}
 form.onsubmit=async e=>{e.preventDefault();const filters:Record<string,string>={};for(const[k,v]of Object.entries({date_from:from.value,date_to:to.value,record_type:type.value,original_doc_id:doc.value,topic_id:topic.value,person_id:person.value}))if(v)filters[k]=v;
 query={query:q.value.trim(),filters};cursor=null;resultCount=0;more.hidden=true;results.replaceChildren();resultsStatus.textContent="Searching…";submit.disabled=true;try{await load();}catch(e){resultsStatus.textContent="Search failed";showError(e,results);}finally{submit.disabled=false;}};
}
async function citation(answerId:string,receiptId:string,anchor:HTMLElement){document.querySelector("#receipt")?.remove();const panel=el("aside");panel.id="receipt";panel.setAttribute("role","dialog");panel.setAttribute("aria-label","Source receipt");panel.append(el("p","Checking current source…"));root.append(panel);
 try{const receipt=await api<Receipt>(base()+"/answers/"+encodeURIComponent(answerId)+"/receipts/"+encodeURIComponent(receiptId));if(!panel.isConnected)return;
 panel.replaceChildren(button("Close",()=>panel.remove(),"receipt-close"),el("span","SOURCE RECEIPT","eyebrow"),el("h3",receipt.source_title),el("p",receipt.record_type+" · "+(receipt.source_time.value||"Date unknown")),el("small",receipt.source_locations.map(locationLabel).join("; ")),el("blockquote",receipt.quote));
 const link=el("a","Open cited source in new tab");link.href=sourceLink(receipt);link.target="_blank";link.rel="noopener";panel.append(link);
 }catch(e){if(panel.isConnected){showError(e,panel);panel.append(button("Regenerate answer",()=>{panel.remove();pending=null;view="chat";renderView();}));}}}
function answerNode(answer:Answer){const row=el("article","","message assistant-message");row.dataset.answerId=answer.id;row.append(el("span","Reviewed answer","message-label"));
 if(answer.cannot_establish)row.append(el("p","Cannot establish the requested answer: "+answer.cannot_establish.replaceAll("_"," ")));
 for(const claim of answer.claims){const p=el("p",claim.text);for(const [index,id] of claim.receipt_ids.entries()){const b=button("Source "+(index+1),()=>citation(answer.id,id,b),"citation");b.setAttribute("aria-label","View supporting quote");b.onfocus=()=>{citation(answer.id,id,b).catch(showError)};p.append(b);}row.append(p);}
 row.append(el("small","Coverage: "+answer.coverage.state));for(const lim of answer.coverage.limitations)row.append(el("p",lim.code.replaceAll("_"," "),"muted"));return row;}
async function chat(main:HTMLElement,mark:number){main.replaceChildren(pageHeader("AI chat",pageDescriptions.chat,"Ask with confidence"));
 const conversations=await list<Models["Conversation"]>(base()+"/conversations");current(mark);
 const choose=select("Conversation",[["","New chat"],...conversations.map(c=>[c.id,c.title] as [string,string])],conversation||"");
 choose.onchange=()=>{conversation=choose.value||null;pending=null;renderView();};const chatLayout=el("div","","chat-layout"),conversationRail=el("aside","","conversation-rail"),thread=el("section","","chat-thread");conversationRail.append(el("div","Conversations","panel-title"),el("p","Start fresh or return to a previous question.","muted"),field("Active conversation",choose));
 const messages=el("section");messages.id="messages";thread.append(messages);chatLayout.append(conversationRail,thread);main.append(chatLayout);
 if(conversation){for(const m of await list<Models["Message"]>(base()+"/conversations/"+encodeURIComponent(conversation)+"/messages")){current(mark);
 if(m.state==="available"&&m.role==="assistant"&&m.answer_id){try{messages.append(answerNode(await api<Answer>(base()+"/answers/"+encodeURIComponent(m.answer_id))));}catch(e){messages.append(el("p","Previous answer unavailable. Regenerate it."));}}
 else {const message=el("article","","message "+(m.role==="assistant"?"assistant-message":"user-message"));message.append(el("span",m.role==="assistant"?"Assistant":"You","message-label"),el("p",m.state==="unavailable"?"Previous answer unavailable. Regenerate it.":m.text||m.unavailable_reason||m.state));messages.append(message);}}}
 current(mark);
 const form=el("form"),question=el("textarea");question.setAttribute("aria-label","Question");question.maxLength=8000;question.required=true;question.value=questionDraft;
 question.oninput=()=>{questionDraft=question.value;if(pending&&pending.question!==question.value)pending=null;};
 question.placeholder="Ask a question about this workspace's approved evidence…";const send=el("button",pending?"Retry question":"Ask question");send.type="submit";form.className="composer";form.append(question,send);main.append(form);
 const status=await api<Models["ProjectStatus"]>(base()+"/status");current(mark);send.disabled=status.write_barrier;
 if(status.write_barrier)thread.append(el("p","Project cleanup is in progress. Your unsent text stays only in this tab.","banner"));
 form.onsubmit=async e=>{e.preventDefault();send.disabled=true;const processing=el("p","Finding evidence and independently reviewing the answer…");messages.append(processing);
 try{if(!conversation){const c=await api<Models["Conversation"]>(base()+"/conversations","POST",{});conversation=c.id;}
 if(!pending)pending={question:question.value,conversation_id:conversation,request_id:crypto.randomUUID()};
 const answer=await api<Answer>(base()+"/chat","POST",pending);current(mark);processing.replaceWith(answerNode(answer));pending=null;questionDraft="";question.value="";send.textContent="Ask";
 }catch(e){processing.remove();showError(e);if(e instanceof ApiError&&(!e.retryable||["evidence_changed","answer_unavailable","idempotency_conflict"].includes(e.code)))pending=null;send.textContent=pending?"Retry question":"Ask";}finally{send.disabled=false;}};}
function timelineTimestamp(time:Models["SourceTime"]){
 if(!time.value)return null;
 const normalized=time.precision==="year"?time.value+"-01-01T00:00:00Z":time.precision==="month"?time.value+"-01T00:00:00Z":time.precision==="day"?time.value+"T00:00:00Z":time.value;
 const timestamp=Date.parse(normalized);return Number.isNaN(timestamp)?null:timestamp;
}
function timelineTimeLabel(time:Models["SourceTime"]){
 if(!time.value)return "Date unknown";
 if(time.precision==="year")return time.value;
 const timestamp=timelineTimestamp(time);if(timestamp===null)return time.value;
 const date=new Date(timestamp);
 const options:Intl.DateTimeFormatOptions=time.precision==="month"?{month:"short",year:"numeric",timeZone:"UTC"}:time.precision==="day"?{day:"numeric",month:"short",year:"numeric",timeZone:"UTC"}:{day:"numeric",month:"short",year:"numeric",hour:"2-digit",minute:"2-digit",timeZoneName:"short"};
 return new Intl.DateTimeFormat(undefined,options).format(date);
}
function timelineView(records:TimelineRecord[]){
 const section=el("section","","timeline-section");section.dataset.timeline="true";section.setAttribute("aria-labelledby","timeline-title");
 const header=el("div","","timeline-header"),title=el("div");const heading=el("h3","Record timeline");heading.id="timeline-title";title.append(heading,el("p",records.length+" processed record"+(records.length===1?"":"s"),"muted"),el("p","AI-generated discovery context. Open processed content to inspect the source.","muted timeline-context"));
 const controls=el("div","","timeline-controls"),viewport=el("div","","timeline-viewport"),track=el("ol","","timeline-track");viewport.tabIndex=0;viewport.setAttribute("aria-label","Project records timeline");viewport.append(track);
 const range=el("input");range.type="range";range.min="70";range.max="160";range.step="10";range.value="100";range.setAttribute("aria-label","Timeline zoom");
 const zoomLabel=el("output","100%","timeline-zoom-value");zoomLabel.htmlFor=range.id="timeline-zoom";
 const timelineItems:HTMLElement[]=[];const timestamps=records.map(record=>timelineTimestamp(record.source_time));let zoom=100;
 const layoutTimeline=()=>{const scale=zoom/100,cardWidth=Math.round(286*scale),minimumStep=cardWidth+Math.round(22*scale),known=timestamps.filter((value):value is number=>value!==null),minimum=known.length?Math.min(...known):0,maximum=known.length?Math.max(...known):0,span=maximum-minimum,temporalWidth=Math.max(minimumStep*Math.max(1,known.length-1)*1.45,760*scale);let previous=0;
  track.style.setProperty("--timeline-card-width",cardWidth+"px");timelineItems.forEach((item,index)=>{const timestamp=timestamps[index],desired=timestamp!==null&&span>0?(timestamp-minimum)/span*temporalWidth:previous+minimumStep,position=index===0?0:Math.max(desired,previous+minimumStep);item.style.marginLeft=index===0?"0":Math.round(position-previous-cardWidth)+"px";previous=position;});};
 const applyZoom=(next:number)=>{zoom=Math.max(70,Math.min(160,next));range.value=String(zoom);zoomLabel.value=zoom+"%";layoutTimeline();};
 const control=(symbol:string,label:string,action:()=>void)=>{const result=button(symbol,action,"timeline-icon");result.type="button";result.title=label;result.setAttribute("aria-label",label);return result;};
 controls.append(control("<","Scroll timeline left",()=>viewport.scrollBy({left:-viewport.clientWidth*.72,behavior:"smooth"})),control(">","Scroll timeline right",()=>viewport.scrollBy({left:viewport.clientWidth*.72,behavior:"smooth"})),control("-","Zoom out timeline",()=>applyZoom(zoom-10)),range,zoomLabel,control("+","Zoom in timeline",()=>applyZoom(zoom+10)));
 range.oninput=()=>applyZoom(Number(range.value));header.append(title,controls);section.append(header);
 const types=[...new Set(records.map(item=>item.record_type))];const legend=el("div","","timeline-legend");legend.setAttribute("aria-label","Record types");for(const type of types){const item=el("span",type,"timeline-legend-item");item.dataset.recordType=type;item.prepend(el("i","","timeline-swatch"));legend.append(item);}section.append(legend);
 if(!records.length){section.append(emptyState("No processed records","This project has no timeline-ready records."));return section;}
 for(const record of records){const item=el("li","","timeline-item");item.dataset.recordType=record.record_type;item.append(el("time",timelineTimeLabel(record.source_time),"timeline-date"),el("span","","timeline-marker"));
  const card=el("article","","timeline-card"),meta=el("div","","card-meta");meta.append(el("span",record.record_type,"timeline-type"));card.append(meta,el("h4",record.title));
  const layer1=el("section","","timeline-summary");layer1.append(el("span","Level 1 routing summary","timeline-summary-label"),el("p",record.level1_summary||"Summary pending."));
  const layer2=el("section","","timeline-summary timeline-summary-secondary");layer2.append(el("span","Level 2 record summary","timeline-summary-label"),el("p",record.level2_summary||"Summary pending."));card.append(layer1,layer2);
  if(record.processed_content_url){const link=el("a","Open processed content","timeline-source-link");link.href=record.processed_content_url;link.target="_blank";link.rel="noopener";card.append(link);}item.append(card);timelineItems.push(item);track.append(item);
 }
 section.append(viewport);
 viewport.addEventListener("wheel",event=>{const maximumScroll=viewport.scrollWidth-viewport.clientWidth,canScroll=event.deltaY<0?viewport.scrollLeft>0:viewport.scrollLeft<maximumScroll;if(Math.abs(event.deltaY)>Math.abs(event.deltaX)&&canScroll){viewport.scrollLeft+=event.deltaY;event.preventDefault();}},{passive:false});
 let dragStart:number|null=null,scrollStart=0;viewport.addEventListener("pointerdown",event=>{if(event.pointerType!=="mouse"||event.button!==0||(event.target as Element).closest("a,button,input"))return;dragStart=event.clientX;scrollStart=viewport.scrollLeft;viewport.setPointerCapture(event.pointerId);viewport.classList.add("is-dragging");});
 viewport.addEventListener("pointermove",event=>{if(dragStart!==null)viewport.scrollLeft=scrollStart-(event.clientX-dragStart);});const stopDrag=()=>{dragStart=null;viewport.classList.remove("is-dragging");};viewport.addEventListener("pointerup",stopDrag);viewport.addEventListener("pointercancel",stopDrag);
 viewport.onkeydown=event=>{if(event.key==="ArrowLeft"||event.key==="ArrowRight"){viewport.scrollBy({left:(event.key==="ArrowLeft"?-1:1)*viewport.clientWidth*.45,behavior:"smooth"});event.preventDefault();}};
 applyZoom(100);return section;
}
async function overview(main:HTMLElement,mark:number){const [data,records]=await Promise.all([api<Models["Overview"]>(base()+"/overview"),list<TimelineRecord>(base()+"/timeline")]);current(mark);main.replaceChildren(pageHeader("Project overview",pageDescriptions.overview,"Briefing"));
 const briefing=el("section","","briefing-section"),briefingHeader=el("div","","section-heading");briefingHeader.append(el("h3","Evidence briefing"),el("span",data.state,"state-badge"));briefing.append(briefingHeader);
 if(data.state==="ready")for(const claim of data.claims){const row=el("article",claim.text,"briefing-card");for(const id of claim.receipt_ids){const b=button("View source",async()=>{
 const fresh=await api<Models["Overview"]>(base()+"/overview");if(fresh.state!=="ready"||fresh.id!==data.id)throw new Error("Overview changed. Reload it.");
 const receipt=fresh.receipts.find(r=>r.id===id);if(!receipt)throw new Error("Source unavailable.");
 const detail=el("blockquote",receipt.quote),link=el("a",receipt.source_title);link.href=sourceLink(receipt);link.target="_blank";link.rel="noopener";detail.append(link);row.append(detail);});row.append(b);}briefing.append(row);}
 else briefing.append(emptyState("Briefing is being prepared","The record timeline remains available while the project briefing is rebuilt."));main.append(briefing,timelineView(records));}
async function visualization(main:HTMLElement,mark:number){const status=await api<Models["ProjectStatus"]>(base()+"/status");current(mark);const stats=el("section","","stat-grid");for(const [value,label] of [[status.eligible_documents,"Eligible documents"],[status.eligible_records,"Eligible records"],[status.write_barrier?"Paused":"Available","Workspace writes"]]){const card=el("article","","stat-card");card.append(el("strong",String(value)),el("span",String(label)));stats.append(card);}
 main.replaceChildren(pageHeader("Project status",pageDescriptions.visualization,"Workspace health"),stats,el("p","Detailed visualization modules are planned for a later release.","muted"));}
async function administration(main:HTMLElement,mark:number){main.classList.add("administration-page");main.replaceChildren(pageHeader("Project administration",pageDescriptions.administration,"Admin tools"),el("p","Membership controls access to this workspace. Personnel associations and erasure remain separate.","section-note"));
 const projectPanel=el("section","","admin-create-project"),projectForm=el("form","","create-project-form"),projectName=input("Project name"),projectSave=el("button","Create project"),projectResult=el("div");projectSave.type="submit";projectName.required=true;projectName.maxLength=120;projectForm.append(field("New project",projectName),projectSave);const deleteProject=button("Delete project",async()=>{if(!project||!confirm("Delete project “"+project.name+"”? This is permanent and only empty projects can be deleted."))return;try{await api(base(),"DELETE");projects=projects.filter(item=>item.id!==project!.id);reset();project=projects[0]||null;view="documents";history.pushState({view},"",project?pagePath(view,project.id):"/");render();}catch(e){showError(e,projectResult);}},"button-danger");projectPanel.append(el("h3","Projects"),el("p","Create a workspace and become its first administrator.","muted"),projectForm,deleteProject,projectResult);projectForm.onsubmit=async e=>{e.preventDefault();projectSave.disabled=true;try{const created=await api<Project>("/api/projects","POST",{name:projectName.value.trim()});projects=[...projects,created];reset();project=created;view="administration";history.pushState({view},"",pagePath(view,created.id));render();}catch(e){showError(e,projectResult);}finally{projectSave.disabled=false;}};
 main.append(projectPanel);
 const accessPanel=el("section"),peoplePanel=el("section"),typesPanel=el("section");main.append(accessPanel,peoplePanel,typesPanel);
 const types=el("section");typesPanel.append(el("h3","Document types"),types);
 await pager<{name:string}>(types,base()+"/types",t=>el("article",t.name,"member-row"));
 const typeForm=el("form"),typeName=input("New document type"),typeSave=el("button","Create document type");typeSave.type="submit";typeName.required=true;typeName.maxLength=64;typeForm.append(field("New document type",typeName),typeSave);
 typeForm.onsubmit=async e=>{e.preventDefault();typeSave.disabled=true;try{await api(base()+"/types","POST",{name:typeName.value});typeName.value="";await renderView();}catch(e){showError(e);}finally{typeSave.disabled=false;}};typesPanel.append(typeForm);
 const members=el("section");accessPanel.append(el("h3","Members"),members);
 await pager<Models["Member"]>(members,base()+"/members",m=>{const row=el("article","","member-row");row.append(el("strong",m.display_name),el("span",m.role,"role-badge"),el("small",m.user_id));row.append(button("Remove access",async()=>{if(!confirm("Remove membership for "+m.display_name+" ("+m.user_id+") from "+project?.name+"? This does not erase their personal information."))return;await api(base()+"/members/"+encodeURIComponent(m.user_id),"DELETE");row.remove();},"button-danger"));return row;});
 const adminProjects=projects.filter(item=>item.role==="admin"),memberForm=el("form","","member-access-form"),user=input("Registered email or account ID"),targetProject=select("Destination project",adminProjects.map(item=>[item.id,item.name]),project?.id||""),role=select("Role",[["member","Member"],["admin","Admin"]]),save=el("button","Grant or update access"),memberResult=el("div");memberResult.setAttribute("role","status");save.type="submit";user.required=true;user.maxLength=320;memberForm.append(field("Registered email or account ID",user),field("Destination project",targetProject),field("Project role",role),save);
 memberForm.onsubmit=async e=>{e.preventDefault();try{const identity=user.value.trim(),target=adminProjects.find(item=>item.id===targetProject.value);if(!target)throw new Error("Select a project you administer.");if(!confirm("Grant "+role.value+" access to "+identity+" in "+target.name+"?"))return;save.disabled=true;await api(projectBase(target.id)+"/members","POST",{...(identity.includes("@")?{email:identity}:{user_id:identity}),role:role.value});current(mark);user.value="";if(target.id===project?.id)await renderView();else memberResult.replaceChildren(el("p","Access was granted in "+target.name+".","section-note"));}catch(e){showError(e,memberResult);}finally{save.disabled=false;}};accessPanel.append(memberForm);peoplePanel.append(el("div","People directory","panel-title"),el("p","Associate clients and employees, or start a privacy erasure workflow.","muted"));
 await pager<Models["Person"]>(peoplePanel,base()+"/people",p=>{const row=el("article",p.display_name+" · "+p.kind+" · "+p.id+" · "+p.state);
 const erase=button("Erase personal information",async()=>{if(!confirm("Erase personal information for "+p.display_name+" ("+p.id+") in "+project?.name+"? Project decisions will remain with [deleted user] attribution."))return;row.append(jobRow(await api<Job>(base()+"/people/"+encodeURIComponent(p.id)+"/erase","POST")));});erase.disabled=p.state==="erasing";row.append(erase);
 return row;});
 const form=el("form"),id=input("Person ID (blank for new identity)"),name=input("Display name"),kind=select("Person kind",[["client","Client"],["employee","Employee"]]),contact=input("Contact value"),contactKind=select("Contact kind",[["email","Email"],["phone","Phone"],["postal_address","Postal address"]]),add=el("button","Associate person");add.type="submit";name.maxLength=255;contact.maxLength=500;
 form.append(id,name,kind,contactKind,contact,add);form.onsubmit=async e=>{e.preventDefault();try{await api(base()+"/people","POST",{...(id.value?{person_id:id.value}:{}),display_name:name.value,kind:kind.value,contacts:contact.value?[{kind:contactKind.value,value:contact.value}]:[]});renderView();}catch(e){showError(e);}};peoplePanel.append(form);await refreshJobs(main,mark);
}
async function start(){try{me=await api<Me>("/api/me");setCsrf(me.csrf_token);await loadProjects();}catch{me=null;render();}}
window.addEventListener("popstate",()=>{if(me){if(project)view=routeView(project.id);render();}});
window.addEventListener("hashchange",()=>{if(me){if(project)view=routeView(project.id);render();}});
start();

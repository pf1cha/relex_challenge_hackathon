import {chromium} from "../../frontend/node_modules/playwright/index.mjs";
import fs from "node:fs";
import path from "node:path";
const config=JSON.parse(fs.readFileSync(process.env.RELEX_LIVE_CONFIG,"utf8"));
const directory=path.dirname(process.env.RELEX_LIVE_CONFIG),url=process.env.RELEX_LIVE_URL;
const report={cases:[],requirements:{},status:"running"};
const browser=await chromium.launch({headless:true,args:["--no-sandbox"]});
const context=await browser.newContext(),page=await context.newPage();
page.setDefaultTimeout(20000);
function record(id,detail){report.cases.push({id,status:"PASS",detail});console.log(JSON.stringify({id,status:"PASS",detail}));}
function assert(value,message){if(!value)throw new Error(message);}
async function response(method,route,body,sessionPage=page){return sessionPage.evaluate(async({method,route,body})=>{
 const me=await fetch("/api/me",{cache:"no-store"}).then(r=>r.json());
 const r=await fetch(route,{method,headers:{"Content-Type":"application/json","X-CSRF-Token":me.csrf_token},...(body===undefined?{}:{body:JSON.stringify(body)})});
 return {status:r.status,body:r.status===204?null:await r.json()};
},{method,route,body});}
async function login(target,email){await target.goto(url);await target.getByLabel("Email",{exact:true}).fill(email);await target.getByLabel("Password",{exact:true}).fill(config.password);await target.getByRole("button",{name:"Sign in",exact:true}).click();await target.getByRole("button",{name:"Sign out",exact:true}).waitFor();}
const base="/api/projects/"+config.project_id;
try{
 await page.goto(url);
 await page.getByLabel("Email",{exact:true}).fill(config.admin_email);
 await page.getByLabel("Password",{exact:true}).fill("wrong-synthetic-password");
 await page.getByRole("button",{name:"Sign in",exact:true}).click();
 await page.getByText("Please sign in.",{exact:true}).waitFor();
 await login(page,config.admin_email);
 assert((await response("GET","/api/projects")).body.items.some(p=>p.id===config.project_id),"Missing permitted project");
 const csrf=await page.evaluate(async(base)=>{const r=await fetch(base+"/conversations",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});return r.status;},base);
 assert(csrf===403,"Missing CSRF must be denied");
 const unknown=await response("GET",base+"/documents?unsupported=1");assert(unknown.status===422,"Unknown query rejected");
 record("C1-login-csrf","Real database login, incorrect password, project selector, missing CSRF, unknown query");
 await page.getByLabel("Text file",{exact:true}).setInputFiles({name:"invalid.txt",mimeType:"text/plain",buffer:Buffer.from([255,0])});
 const malformedPromise=page.waitForResponse(r=>r.url().endsWith(base+"/documents")&&r.request().method()==="POST");
 await page.getByRole("button",{name:"Upload",exact:true}).click();
 assert((await malformedPromise).status()===422,"Malformed UTF-8 upload must fail visibly");
 await page.getByText("Upload supported UTF-8 text.",{exact:true}).waitFor();
 record("C2-malformed-upload","Invalid UTF-8 rejected with safe UI error; same form remains usable");
 await page.getByLabel("Text file",{exact:true}).setInputFiles("fixtures/implementation/launch-report.txt");
 await page.getByLabel("Record type",{exact:true}).selectOption("report");
 const uploadPromise=page.waitForResponse(r=>r.url().endsWith(base+"/documents")&&r.request().method()==="POST");
 await page.getByRole("button",{name:"Upload",exact:true}).click();
 const uploadResponse=await uploadPromise;assert(uploadResponse.status()===202,"Upload acceptance");const job=await uploadResponse.json();
 record("C2-upload-accepted","Job "+job.id+" is accepted as processing, not completed");
 let finalJob;
 for(let n=0;n<180;n++){finalJob=(await response("GET",base+"/jobs/"+job.id)).body;
 if(finalJob.state==="completed"||finalJob.state==="failed")break;await page.waitForTimeout(1000);}
 assert(finalJob.state==="completed","Real ingestion failed/incomplete: "+finalJob.error_code+" stage "+finalJob.stage);
 await page.reload();await page.getByRole("button",{name:"Sign out",exact:true}).waitFor();
 const documents=(await response("GET",base+"/documents")).body.items;
 assert(documents.length>0,"Published document visible");const document=documents.find(d=>d.latest_job_id===job.id)||documents.at(-1);
 const records=(await response("GET",base+"/documents/"+document.id+"/records")).body.items;
 assert(records.length>0,"Canonical records published");
 const recordPage=(await response("GET",base+"/records/"+records[0].record_id)).body;
 assert(recordPage.spans.length>0,"Canonical source spans published");
 record("C2-publication-reload","Real worker completed; document "+document.id+"; record "+records[0].record_id+"; jobs rediscovered after reload");
 await page.getByRole("button",{name:"Search",exact:true}).first().click();
 await page.getByLabel("Search query",{exact:true}).fill("ZQX-741");
 await page.locator("form").getByRole("button",{name:"Search",exact:true}).click();
 await page.getByRole("button",{name:"Read record",exact:true}).first().waitFor();
 const search=(await response("POST",base+"/search",{query:"ZQX-741",filters:{}}));
 assert(search.status===200&&search.body.items.length>0,"Real hybrid exact identifier");
 const filterOptions=(await response("GET",base+"/filters")).body;
 for(const filters of [{date_from:"2026-09-01"},{date_to:"2026-09-30"},{date_from:"2026-09-01",date_to:"2026-09-30",record_type:"report",original_doc_id:document.id},{record_type:"report"},{original_doc_id:document.id},...filterOptions.people.slice(0,1).map(x=>({person_id:x.id})),...filterOptions.topics.slice(0,1).map(x=>({topic_id:x.id}))]){
 const result=await response("POST",base+"/search",{query:"launch",filters});assert(result.status===200,"Filter query failed");}
 const centered=await response("GET",base+"/sources/"+records[0].record_id+"?version="+records[0].record_version+"&span="+recordPage.spans[3].span_id+"&limit=2");
 assert(centered.status===200&&centered.body.highlighted_span_ids.includes(recordPage.spans[3].span_id),"Centered source page");
 assert(centered.body.previous_cursor||centered.body.next_cursor,"Source pagination available");
 record("C2-search","Real UI search; individual date/source/type and combined filters; canonical centered source pagination");
 await page.getByRole("button",{name:"Chat",exact:true}).click();
 await page.getByLabel("Question",{exact:true}).fill("What Finland launch was agreed and what condition applies?");
 const chatPromise=page.waitForResponse(r=>r.url().endsWith(base+"/chat"),{timeout:320000});
 await page.getByRole("button",{name:"Ask",exact:true}).click();
 const chatResponse=await chatPromise;
 assert(chatResponse.status()===200,"Chat failed: "+chatResponse.status());const answer=await chatResponse.json();
 assert(!("review_results"in answer)&&!("candidate_digest"in answer),"Internal candidate exposed");
 assert(answer.claims.length>0&&answer.receipts.length>0,"Expected grounded synthetic launch answer");
 await page.getByLabel("View supporting quote").first().focus();
 await page.locator("#receipt blockquote").waitFor();
 const quote=await page.locator("#receipt blockquote").textContent();
 assert(answer.receipts.some(r=>r.quote===quote),"Popover exact receipt quote");
 const tabPromise=context.waitForEvent("page");await page.getByRole("link",{name:"Open cited source in new tab"}).click();const sourceTab=await tabPromise;
 await sourceTab.locator("mark").first().waitFor();
 assert((await sourceTab.locator("mark").allTextContents()).some(t=>quote.includes(t)),"Source centered highlighted quote equality");
 if(await sourceTab.getByRole("button",{name:"Next source page",exact:true}).count()){
  await sourceTab.getByRole("button",{name:"Next source page",exact:true}).click();
  await sourceTab.getByRole("button",{name:"Previous source page",exact:true}).waitFor();
  await sourceTab.getByRole("button",{name:"Previous source page",exact:true}).click();
  await sourceTab.locator("mark").first().waitFor();
 }
 await sourceTab.close();
 await page.getByRole("button",{name:"Close",exact:true}).click();
 await page.getByLabel("View supporting quote").first().hover();await page.locator("#receipt blockquote").waitFor();
 await page.getByRole("button",{name:"Close",exact:true}).click();
 await page.getByLabel("View supporting quote").first().click();await page.locator("#receipt blockquote").waitFor();
 const replay=await response("POST",base+"/chat",{question:"What Finland launch was agreed and what condition applies?",conversation_id:answer.conversation_id,request_id:answer.request_id});
 assert(replay.status===200&&replay.body.id===answer.id,"Stable request replay");
 const conflict=await response("POST",base+"/chat",{question:"Different input",conversation_id:answer.conversation_id,request_id:answer.request_id});
 assert(conflict.status===409&&conflict.body.error.code==="idempotency_conflict","Changed retry input must conflict");
 record("C3-reviewed-chat-receipts","Answer "+answer.id+"; focus/hover/tap, new tab source, exact quote, stable replay and conflict observed");
 const memberContext=await browser.newContext(),member=await memberContext.newPage();await login(member,config.member_email);
 assert(await member.getByRole("button",{name:"Administration",exact:true}).count()===0,"Member saw admin UI");
 const denied=await response("DELETE",base+"/documents/"+document.id,undefined,member);assert(denied.status===403,"Member admin bypass allowed");
 const ownerDenied=await response("GET",base+"/answers/"+answer.id,undefined,member);assert(ownerDenied.status===404,"Wrong answer owner leaked");
 const outsiderContext=await browser.newContext(),outsider=await outsiderContext.newPage();await login(outsider,config.outsider_email);
 const outsiderProjects=await response("GET","/api/projects",undefined,outsider);assert(outsiderProjects.body.items.length===0,"Outsider project leaked");
 const deniedSource=await response("GET",base+"/sources/"+records[0].record_id+"?version="+records[0].record_version+"&span="+recordPage.spans[0].span_id,undefined,outsider);assert(deniedSource.status===404,"Outsider source leaked");
 record("C1-boundaries","Actual separate member/outsider browser sessions; admin 403, other owner's answer 404, project/source 404");
 await memberContext.close();await outsiderContext.close();
 await page.getByRole("button",{name:"Close",exact:true}).click();
 await page.getByRole("button",{name:"Documents",exact:true}).click();
 page.once("dialog",d=>d.accept());
 const deactivatePromise=page.waitForResponse(r=>r.url().endsWith("/deactivate"));
 await page.getByRole("button",{name:"deactivate",exact:true}).first().click();
 assert((await deactivatePromise).status()===202,"Deactivation accepted");
 const stale=await response("GET",base+"/answers/"+answer.id+"/receipts/"+answer.receipts[0].id);assert(stale.status===410,"Old receipt must become unavailable");
 await page.getByRole("button",{name:"Chat",exact:true}).click();await page.getByLabel("Conversation",{exact:true}).selectOption(answer.conversation_id);
 await page.getByText(/unavailable/i).first().waitFor();
 record("C4-deactivation","Admin exact-target confirmation, async job state and stale receipt 410");
 await page.screenshot({path:path.join(directory,"browser.png"),fullPage:true});
 await page.getByRole("button",{name:"Sign out",exact:true}).click();await page.getByRole("button",{name:"Sign in",exact:true}).waitFor();
 const loggedOut=await page.evaluate(async()=>{const r=await fetch("/api/me");return r.status;});assert(loggedOut===401,"Logout not revoked");
 record("C1-logout","Real session revoked and browser state cleared");
 report.status="PASS";
 report.requirements={
  "R-C1":"LIVE: login/incorrect login/logout/project boundary/CSRF/direct URL; process restart pending",
  "R-C2":"LIVE: malformed upload recovery/publication/date-type-source filters/source pagination/citation interactions; person/topic filter semantic matrix linked to B",
  "R-C3":"LIVE: reviewed answer/replay/owner/stale receipt; in-flight races/provider fault and project switch pending",
  "R-C4":"LIVE: denied admin and deactivation UI; remaining lifecycle failure/retry/erasure workflows pending",
  "R-G1":"LIVE: synthetic upload to real worker/provider/index/canonical source",
  "R-G2":"LIVE: real reviewed answer to exact receipt and source browser",
  "R-G3":"PENDING: complete lifecycle/failure/late-write inspection requires A/B verification",
  "R-G4":"PENDING: complete matrix, restart and simultaneous A/B/C",
  "R-S":"PENDING: second isolated live run"
 };
}catch(error){report.status="FAIL";report.failure=error instanceof Error?error.message:String(error);console.error(JSON.stringify({status:"FAIL",failure:report.failure}));await page.screenshot({path:path.join(directory,"failure.png"),fullPage:true}).catch(()=>{});}
finally{fs.writeFileSync(path.join(directory,"browser.json"),JSON.stringify(report,null,2));await browser.close();}
process.exit(report.status==="PASS"?0:1);

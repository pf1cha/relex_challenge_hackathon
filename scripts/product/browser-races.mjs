import {chromium} from "../../frontend/node_modules/playwright/index.mjs";
import fs from "node:fs";import path from "node:path";
const c=JSON.parse(fs.readFileSync(process.env.RELEX_LIVE_CONFIG,"utf8")),dir=path.dirname(process.env.RELEX_LIVE_CONFIG),controls=process.env.RELEX_FAULT_CONTROLS,base="/api/projects/"+c.project_id;
const browser=await chromium.launch({headless:true,args:["--no-sandbox"]}),context=await browser.newContext(),page=await context.newPage();page.setDefaultTimeout(20000);
const report={status:"running",cases:[]};
function check(v,m){if(!v)throw Error(m);}
function note(id,detail){report.cases.push({id,status:"PASS",detail});console.log(JSON.stringify(report.cases.at(-1)));}
async function login(p,email){await p.goto(process.env.RELEX_LIVE_URL);await p.getByLabel("Email",{exact:true}).fill(email);await p.getByLabel("Password",{exact:true}).fill(c.password);await p.getByRole("button",{name:"Sign in",exact:true}).click();await p.getByRole("button",{name:"Sign out",exact:true}).waitFor();}
async function api(p,method,route,body){return p.evaluate(async({method,route,body})=>{const me=await fetch("/api/me").then(r=>r.json());const r=await fetch(route,{method,headers:{"Content-Type":"application/json","X-CSRF-Token":me.csrf_token},...(body===undefined?{}:{body:JSON.stringify(body)})});return {status:r.status,body:r.status===204?null:await r.json()};},{method,route,body});}
function mark(n){fs.writeFileSync(path.join(controls,n),"1");}
function reset(){for(const n of ["answer-ready","release-answer","pause-answer"])fs.rmSync(path.join(controls,n),{force:true});mark("pause-answer");}
async function ready(){for(let n=0;n<600;n++){if(fs.existsSync(path.join(controls,"answer-ready")))return JSON.parse(fs.readFileSync(path.join(controls,"answer-ready")));await new Promise(r=>setTimeout(r,250));}throw Error("Actual candidate pause not reached");}
async function ask(p,question){reset();await p.getByRole("button",{name:"Chat",exact:true}).click();await p.getByLabel("Question",{exact:true}).fill(question);const req=p.waitForRequest(r=>r.url().endsWith(base+"/chat"));await p.getByRole("button",{name:"Ask",exact:true}).click();const request=await req;const input=request.postDataJSON();const resp=request.response().catch(()=>null);await ready();return {input,resp};}
async function job(id){for(let n=0;n<180;n++){const s=(await api(page,"GET",base+"/jobs/"+id)).body;if(["completed","failed"].includes(s.state))return s;await new Promise(r=>setTimeout(r,1000));}throw Error("Job timeout");}
try{
 await login(page,c.admin_email);
 await page.getByLabel("Text file",{exact:true}).setInputFiles("fixtures/implementation/launch-report.txt");await page.getByLabel("Record type",{exact:true}).selectOption("report");
 const up=page.waitForResponse(r=>r.url().endsWith(base+"/documents")&&r.request().method()==="POST");await page.getByRole("button",{name:"Upload and assign",exact:true}).click();const upload=await(await up).json();check((await job(upload.id)).state==="completed","Upload failed");
 const doc=(await api(page,"GET",base+"/documents")).body.items[0];
 let held=await ask(page,"What Finland launch was agreed and what condition applies?");
 const duplicate=await api(page,"POST",base+"/chat",held.input);check(duplicate.status===409&&duplicate.body.error.code==="request_in_progress","Duplicate not fenced");
 mark("release-answer");const first=await held.resp;check(first.status()===200,"Initial release failed");const answer=await first.json();check(answer.claims.length>0,"Positive candidate missing");
 note("double-submit","Actual held candidate; duplicate returns request_in_progress; original reviewed answer released");
 held=await ask(page,"What is the agreed Finland launch condition?");
 await page.getByLabel("Project",{exact:true}).selectOption(c.other_project_id);mark("release-answer");await new Promise(r=>setTimeout(r,600));
 check(!(await page.locator("main").innerText()).includes(answer.claims[0].text),"Old claim leaked after switch");note("project-switch-in-flight","Project switch aborts/clears previous view and ignores late actual candidate");
 await page.getByLabel("Project",{exact:true}).selectOption(c.project_id);
 held=await ask(page,"What condition was agreed for the Finland launch?");
 await page.getByRole("button",{name:"Sign out",exact:true}).click();mark("release-answer");await page.getByRole("button",{name:"Sign in",exact:true}).waitFor();
 check(await page.evaluate(async()=> (await fetch("/api/me")).status)===401,"Logout not revoked");note("logout-in-flight","Session revoked during actual candidate; login screen retained");
 await login(page,c.admin_email);
 const mc=await browser.newContext(),member=await mc.newPage();member.setDefaultTimeout(20000);await login(member,c.member_email);
 held=await ask(member,"What Finland launch agreement and condition are recorded?");
 const revoke=await api(page,"DELETE",base+"/members/"+c.member_id);check(revoke.status===204,"Revoke failed "+revoke.status);mark("release-answer");
 const denied=await held.resp;check(denied&&denied.status()===404,"Revoked candidate release leaked");note("membership-revocation-in-flight","Actual member candidate withheld after admin revokes membership; HTTP404");await mc.close();
 held=await ask(page,"Which condition governs the Finland launch?");
 const deact=await api(page,"POST",base+"/documents/"+doc.id+"/deactivate");check(deact.status===202,"Deactivate failed");mark("release-answer");const stale=await held.resp;check(stale&&stale.status()===409,"Stale candidate release not fenced");check((await stale.json()).error.code==="evidence_changed","Wrong stale error");
 note("source-invalidation-in-flight","Actual reviewed candidate rejected evidence_changed after canonical source deactivation");
 const receipt=await api(page,"GET",base+"/answers/"+answer.id+"/receipts/"+answer.receipts[0].id);check(receipt.status===410,"Old receipt remained available");
 await page.getByLabel("Conversation",{exact:true}).selectOption(answer.conversation_id);await page.getByText(/unavailable/i).first().waitFor();check(await page.locator("#receipt blockquote").count()===0,"Stale quote retained");note("stale-receipt","Canonical receipt returns410 and browser removes quote after lifecycle change");
 report.status="PASS";
}catch(e){report.status="FAIL";report.failure=e.message;console.error(e);await page.screenshot({path:path.join(dir,"race-failure.png")}).catch(()=>{});}
finally{mark("release-answer");mark("release-index");fs.writeFileSync(path.join(dir,"browser-races.json"),JSON.stringify(report,null,2));await browser.close();}
process.exit(report.status==="PASS"?0:1);

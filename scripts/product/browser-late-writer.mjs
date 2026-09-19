import {chromium} from "../../frontend/node_modules/playwright/index.mjs";
import fs from "node:fs";import path from "node:path";
const c=JSON.parse(fs.readFileSync(process.env.RELEX_LIVE_CONFIG,"utf8")),dir=path.dirname(process.env.RELEX_LIVE_CONFIG),ctrl=process.env.RELEX_FAULT_CONTROLS,base="/api/projects/"+c.project_id;
const b=await chromium.launch({headless:true,args:["--no-sandbox"]}),p=await b.newPage();p.setDefaultTimeout(20000);const report={status:"running",cases:[]};
function check(v,m){if(!v)throw Error(m);}
async function api(method,route,body){return p.evaluate(async({method,route,body})=>{const me=await fetch("/api/me").then(r=>r.json());const r=await fetch(route,{method,headers:{"Content-Type":"application/json","X-CSRF-Token":me.csrf_token},...(body===undefined?{}:{body:JSON.stringify(body)})});return {status:r.status,body:r.status===204?null:await r.json()};},{method,route,body});}
async function waitJob(id,target){for(let n=0;n<180;n++){const s=(await api("GET",base+"/jobs/"+id)).body;if(s.state===target)return s;await new Promise(r=>setTimeout(r,500));}throw Error("Job not "+target);}
try{
 await p.goto(process.env.RELEX_LIVE_URL);await p.getByLabel("Email",{exact:true}).fill(c.admin_email);await p.getByLabel("Password",{exact:true}).fill(c.password);await p.getByRole("button",{name:"Sign in",exact:true}).click();await p.getByRole("button",{name:"Sign out",exact:true}).waitFor();
 const person=await api("POST",base+"/people",{display_name:"Race Person",kind:"employee",contacts:[{kind:"email",value:"race@synthetic.invalid"}]});check(person.status===200,"Association failed "+person.status);
 fs.writeFileSync(path.join(ctrl,"pause-index"),"1");
 await p.getByLabel("Text file",{exact:true}).setInputFiles({name:"late-race.txt",mimeType:"text/plain",buffer:Buffer.from("Race Person (race@synthetic.invalid) agreed the Finland launch will use Helsinki first. The agreement requires warehouse confirmation.\n")});await p.getByLabel("Record type",{exact:true}).selectOption("report");await p.getByRole("button",{name:"Upload and assign",exact:true}).click();
 for(let n=0;n<600&&!fs.existsSync(path.join(ctrl,"index-ready"));n++)await new Promise(r=>setTimeout(r,250));check(fs.existsSync(path.join(ctrl,"index-ready")),"Actual tracked index dispatch not reached");
 const erased=await api("POST",base+"/people/"+person.body.id+"/erase");check(erased.status===202,"Erasure not accepted");const id=erased.body.id;
 const failed=await waitJob(id,"failed");check(failed.error_code==="index_outcome_unknown"&&failed.retryable,"Unexpected cleanup failure "+failed.error_code);
 await p.reload();await p.getByText(/Project cleanup is in progress/).first().waitFor();check(await p.getByRole("button",{name:"Upload and assign",exact:true}).isDisabled(),"Barrier upload enabled");
 await p.getByRole("button",{name:"Chat",exact:true}).click();await p.getByLabel("Question",{exact:true}).fill("Keep this unsent question");check(await p.getByRole("button",{name:"Ask",exact:true}).isDisabled(),"Barrier chat enabled");
 report.cases.push({id:"late-writer-barrier",status:"PASS",job_id:id,error:failed.error_code,detail:"Actual upsert held after durable dispatch; erasure fails safely; reload displays barrier and disables producing writes"});
 fs.writeFileSync(path.join(ctrl,"release-index"),"1");
 await new Promise(r=>setTimeout(r,1500));
 await p.getByRole("button",{name:"Documents",exact:true}).click();
 const response=p.waitForResponse(r=>r.url().endsWith("/jobs/"+id+"/retry"));await p.locator('[data-job-id="'+id+'"]').getByRole("button",{name:"Retry job",exact:true}).click();check((await response).status()===200,"Retry rejected");check((await waitJob(id,"completed")).state==="completed","Cleanup incomplete");
 check(!(await api("GET",base+"/status")).body.write_barrier,"Barrier remained");
 const docs=(await api("GET",base+"/documents")).body.items;
 check(docs.length>0,"Sanitized document missing");for(const doc of docs){const records=(await api("GET",base+"/documents/"+doc.id+"/records")).body.items;for(const record of records){const page=await api("GET",base+"/records/"+record.record_id);check(!JSON.stringify(page.body).includes("race@synthetic.invalid")&&!JSON.stringify(page.body).includes("Race Person"),"Identity remained in source");}}
 await p.reload();await p.getByRole("button",{name:"Open records",exact:true}).first().click();await p.locator("#content article section button").filter({hasNotText:"Load more"}).first().click();await p.getByText("End of record",{exact:true}).waitFor();const text=await p.locator("#content").innerText();check(text.includes("[deleted user]")&&text.includes("Finland")&&!text.includes("Race Person")&&!text.includes("race@synthetic.invalid"),"Redacted source browser content wrong");
 report.cases.push({id:"late-writer-retry",status:"PASS",job_id:id,entry_ids:JSON.parse(fs.readFileSync(path.join(ctrl,"index-ready"))).entry_ids,detail:"Actual writer released; browser retries persisted cleanup job; completion clears barrier and canonical source excludes erased identity"});report.status="PASS";console.log(JSON.stringify(report));
}catch(e){report.status="FAIL";report.failure=e.message;console.error(e);await p.screenshot({path:path.join(dir,"late-failure.png")}).catch(()=>{});}
finally{fs.writeFileSync(path.join(ctrl,"release-index"),"1");fs.writeFileSync(path.join(dir,"browser-late-writer.json"),JSON.stringify(report,null,2));await b.close();}
process.exit(report.status==="PASS"?0:1);

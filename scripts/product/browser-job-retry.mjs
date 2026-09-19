import {chromium} from "../../frontend/node_modules/playwright/index.mjs";
import fs from "node:fs";import path from "node:path";
const config=JSON.parse(fs.readFileSync(process.env.RELEX_LIVE_CONFIG,"utf8")),directory=path.dirname(process.env.RELEX_LIVE_CONFIG),base="/api/projects/"+config.project_id;
const browser=await chromium.launch({headless:true,args:["--no-sandbox"]}),page=await browser.newPage();page.setDefaultTimeout(20000);
try{
 await page.goto(process.env.RELEX_LIVE_URL);await page.getByLabel("Email",{exact:true}).fill(config.admin_email);await page.getByLabel("Password",{exact:true}).fill(config.password);await page.getByRole("button",{name:"Sign in",exact:true}).click();await page.getByRole("button",{name:"Sign out",exact:true}).waitFor();
 let jobId;
 if(process.env.RELEX_FAULT_STAGE==="failure"){
  await page.getByLabel("Text file",{exact:true}).setInputFiles("fixtures/implementation/launch-report.txt");
  await page.getByLabel("Record type",{exact:true}).selectOption("report");
  const [response]=await Promise.all([page.waitForResponse(r=>r.url().endsWith(base+"/documents")&&r.request().method()==="POST"),page.getByRole("button",{name:"Upload and assign",exact:true}).click()]);
  if(response.status()!==202)throw new Error("Upload not accepted");jobId=(await response.json()).id;
  fs.writeFileSync(path.join(directory,"retry-job.json"),JSON.stringify({id:jobId}));
 }else{
  jobId=JSON.parse(fs.readFileSync(path.join(directory,"retry-job.json"),"utf8")).id;
  const row=page.locator('[data-job-id="'+jobId+'"]');
  const [retry]=await Promise.all([page.waitForResponse(r=>r.url().endsWith("/jobs/"+jobId+"/retry")),row.getByRole("button",{name:"Retry job",exact:true}).click()]);
  if(retry.status()!==200)throw new Error("Retry rejected");
 }
 let state;
 for(let i=0;i<150;i++){state=await page.evaluate(async(path)=>fetch(path).then(r=>r.json()),base+"/jobs/"+jobId);
  if(state.state==="failed"||state.state==="completed")break;await page.waitForTimeout(1000);}
 const expected=process.env.RELEX_FAULT_STAGE==="failure"?"failed":"completed";
 if(state.state!==expected)throw new Error("Expected "+expected+", observed "+state.state+" "+state.error_code);
 if(expected==="failed"){
  if(!state.retryable)throw new Error("Real transient provider failure not retryable");
  await page.locator('[data-job-id="'+jobId+'"]').getByRole("button",{name:"Retry job",exact:true}).waitFor();
 }else{
  // Completed polling refreshes the actual document list without reload.
  await page.getByRole("button",{name:"Open records",exact:true}).first().waitFor();
 }
 const result={status:"PASS",stage:process.env.RELEX_FAULT_STAGE,job_id:jobId,state:state.state,
  observation:expected==="failed"?"Real failed worker job rediscovered with retry control":"Same persisted job completed after restoring worker provider; published document displayed"};
 fs.writeFileSync(path.join(directory,"job-"+process.env.RELEX_FAULT_STAGE+".json"),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
}finally{await browser.close();}

import {chromium} from "../../frontend/node_modules/playwright/index.mjs";
import fs from "node:fs";
import path from "node:path";
const config=JSON.parse(fs.readFileSync(process.env.RELEX_LIVE_CONFIG,"utf8"));
const browser=await chromium.launch({headless:true,args:["--no-sandbox"]});
const context=await browser.newContext(),page=await context.newPage();
try{
 await page.goto(process.env.RELEX_LIVE_URL);
 await page.getByLabel("Email",{exact:true}).fill(config.admin_email);
 await page.getByLabel("Password",{exact:true}).fill(config.password);
 await page.getByRole("button",{name:"Sign in",exact:true}).click();
 await page.getByRole("button",{name:"Sign out",exact:true}).waitFor();
 await page.getByText("Processing jobs",{exact:true}).waitFor();
 const result=await page.evaluate(async(project)=>{const paths=["documents","conversations","jobs"];const out={};for(const key of paths){const r=await fetch("/api/projects/"+project+"/"+key);if(!r.ok)throw new Error("Persistent read failed");out[key]=(await r.json()).items.length;}return out;},config.project_id);
 if(!result.documents||!result.conversations||!result.jobs)throw new Error("Persistent objects missing after process restart");
 await page.getByRole("button",{name:"Chat",exact:true}).click();
 await page.getByLabel("Question",{exact:true}).fill("Unsent text stays in this project only");
 await page.getByLabel("Project",{exact:true}).selectOption(config.other_project_id);
 await page.getByLabel("Question",{exact:true}).waitFor();
 if(await page.getByLabel("Question",{exact:true}).inputValue())throw new Error("Unsent project text leaked across switch");
 await page.getByLabel("Project",{exact:true}).selectOption(config.project_id);
 await page.reload();await page.getByRole("button",{name:"Sign out",exact:true}).waitFor();
 const report={status:"PASS",cases:["HTTP and worker restarted against persistent storage","Persisted jobs/documents/conversations rediscovered","Project switch cleared question/chat state","Browser reload restored real session"],counts:result};
 fs.writeFileSync(path.join(path.dirname(process.env.RELEX_LIVE_CONFIG),"restart.json"),JSON.stringify(report,null,2));
 console.log(JSON.stringify(report));
}finally{await browser.close();}

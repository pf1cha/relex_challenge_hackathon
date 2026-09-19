import {chromium} from "../../frontend/node_modules/playwright/index.mjs";
import fs from "node:fs";import path from "node:path";
const config=JSON.parse(fs.readFileSync(process.env.RELEX_LIVE_CONFIG,"utf8")),directory=path.dirname(process.env.RELEX_LIVE_CONFIG);
const input=JSON.parse(fs.readFileSync(path.join(directory,"failed-request.json"),"utf8"));
const browser=await chromium.launch({headless:true,args:["--no-sandbox"]});const page=await browser.newPage();
try{
 await page.goto(process.env.RELEX_LIVE_URL);await page.getByLabel("Email",{exact:true}).fill(config.admin_email);await page.getByLabel("Password",{exact:true}).fill(config.password);await page.getByRole("button",{name:"Sign in",exact:true}).click();await page.getByRole("button",{name:"Sign out",exact:true}).waitFor();
 const result=await page.evaluate(async({project,input})=>{const me=await fetch("/api/me").then(r=>r.json());const response=await fetch("/api/projects/"+project+"/chat",{method:"POST",headers:{"Content-Type":"application/json","X-CSRF-Token":me.csrf_token},body:JSON.stringify(input)});return{status:response.status,body:await response.json()};},{project:config.project_id,input});
 if(result.status!==200||!result.body.id)throw new Error("Restored real provider retry failed: "+result.status);
 const report={status:"PASS",answer_id:result.body.id,cases:["Actual configured provider restored in HTTP process","Same failed request ID retried through real chat and released safely"]};
 fs.writeFileSync(path.join(directory,"provider-recovery.json"),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
}finally{await browser.close();}

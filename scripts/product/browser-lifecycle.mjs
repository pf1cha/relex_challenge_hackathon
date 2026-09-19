import {chromium} from "../../frontend/node_modules/playwright/index.mjs";
import fs from "node:fs";import path from "node:path";
const config=JSON.parse(fs.readFileSync(process.env.RELEX_LIVE_CONFIG,"utf8"));
const directory=path.dirname(process.env.RELEX_LIVE_CONFIG),base="/api/projects/"+config.project_id;
const browser=await chromium.launch({headless:true,args:["--no-sandbox"]}),context=await browser.newContext(),page=await context.newPage();
page.setDefaultTimeout(20000);const result={status:"running",cases:[]};
function assert(v,m){if(!v)throw new Error(m);}
async function request(method,route,body){return page.evaluate(async({method,route,body})=>{const me=await fetch("/api/me").then(r=>r.json());const r=await fetch(route,{method,headers:{"Content-Type":"application/json","X-CSRF-Token":me.csrf_token},...(body===undefined?{}:{body:JSON.stringify(body)})});return{status:r.status,body:r.status===204?null:await r.json()};},{method,route,body});}
async function job(id){for(let i=0;i<180;i++){const j=(await request("GET",base+"/jobs/"+id)).body;if(j.state==="completed")return j;if(j.state==="failed")throw new Error("Lifecycle job failed: "+j.kind+" "+j.error_code);await page.waitForTimeout(1000);}throw new Error("Lifecycle timed out");}
try{
 await page.goto(process.env.RELEX_LIVE_URL);await page.getByLabel("Email",{exact:true}).fill(config.admin_email);await page.getByLabel("Password",{exact:true}).fill(config.password);await page.getByRole("button",{name:"Sign in",exact:true}).click();await page.getByRole("button",{name:"Sign out",exact:true}).waitFor();
 await page.getByRole("button",{name:"Administration",exact:true}).click();
 await page.getByLabel("Existing user ID",{exact:true}).fill(config.outsider_id);
 await page.getByRole("button",{name:"Set membership",exact:true}).click();
 await page.getByText("Synthetic Outsider", {exact:false}).waitFor();
 const outsiderRow=page.locator("article").filter({hasText:config.outsider_id});
 page.once("dialog",d=>{assert(d.message().includes(config.outsider_id)&&d.message().includes("does not erase"),"Membership confirmation");d.accept();});
 await outsiderRow.getByRole("button",{name:"Remove membership",exact:true}).click();
 await outsiderRow.waitFor({state:"detached"});
 result.cases.push("Admin membership grant and exact-target removal, distinct from erasure");
 async function associate(contact){
  await page.getByLabel("Display name",{exact:true}).fill("Synthetic Same Name");
  await page.getByLabel("Contact value",{exact:true}).fill(contact);
  const [response]=await Promise.all([page.waitForResponse(r=>r.url().endsWith(base+"/people")&&r.request().method()==="POST"),page.getByRole("button",{name:"Associate person",exact:true}).click()]);
  const created=await response.json();await page.getByLabel("Display name",{exact:true}).waitFor();return created;
 }
 const person1=await associate("same-one@synthetic.invalid"),person2=await associate("same-two@synthetic.invalid");
 assert(person1.id!==person2.id,"Same-name identities merged");
 const target=page.locator("article").filter({hasText:person1.id});
 page.once("dialog",d=>{assert(d.message().includes(person1.id)&&d.message().includes("Project decisions will remain"),"Erasure confirmation scope");d.accept();});
 const [eraseResponse]=await Promise.all([page.waitForResponse(r=>r.url().endsWith("/people/"+person1.id+"/erase")),target.getByRole("button",{name:"Erase personal information",exact:true}).click()]);
 const erasure=await eraseResponse.json();await job(erasure.id);
 const people=(await request("GET",base+"/people")).body.items;
 assert(!people.some(p=>p.id===person1.id)&&people.some(p=>p.id===person2.id),"Selected erasure affected wrong identity");
 result.cases.push("Same-name person IDs remain distinct; UI erasure targets one exact project/person; real job completion and remaining identity checked");
 await page.getByRole("button",{name:"Documents",exact:true}).click();
 let docs=(await request("GET",base+"/documents")).body.items;const document=docs.find(d=>d.ai_status==="inactive");
 assert(document,"Expected inactive document");
 const row=page.locator("article").filter({hasText:document.title}).first();
 page.once("dialog",d=>d.accept());
 const [activated]=await Promise.all([page.waitForResponse(r=>r.url().endsWith("/documents/"+document.id+"/activate")),row.getByRole("button",{name:"activate",exact:true}).click()]);await job((await activated.json()).id);
 const status=(await request("GET",base+"/status")).body;assert(status.eligible_documents>0,"Coherent reactivation did not restore eligibility");
 await page.reload();await page.getByRole("button",{name:"Documents",exact:true}).click();
 const refreshed=page.locator("article").filter({hasText:document.title}).first();
 page.once("dialog",d=>{assert(d.message().includes(document.id),"Document confirmation omits exact target");d.accept();});
 const [deleted]=await Promise.all([page.waitForResponse(r=>r.url().endsWith("/documents/"+document.id)&&r.request().method()==="DELETE"),refreshed.getByRole("button",{name:"delete",exact:true}).click()]);const deletion=await deleted.json();await job(deletion.id);
 docs=(await request("GET",base+"/documents")).body.items;assert(!docs.some(d=>d.id===document.id),"Deleted document still listed");
 result.cases.push("Reactivate rebuilt eligible source; delete exact document through UI; real durable cleanup completed and document absent");
 result.status="PASS";console.log(JSON.stringify(result));
}catch(e){result.status="FAIL";result.failure=e.message;console.error(JSON.stringify(result));await page.screenshot({path:path.join(directory,"lifecycle-failure.png"),fullPage:true});}
finally{fs.writeFileSync(path.join(directory,"lifecycle.json"),JSON.stringify(result,null,2));await browser.close();}
process.exit(result.status==="PASS"?0:1);

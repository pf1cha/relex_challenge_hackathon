import {chromium} from "../../frontend/node_modules/playwright/index.mjs";
import fs from "node:fs";import path from "node:path";
const config=JSON.parse(fs.readFileSync(process.env.RELEX_LIVE_CONFIG,"utf8"));
const browser=await chromium.launch({headless:true,args:["--no-sandbox"]});
const page=await browser.newPage();page.setDefaultTimeout(20000);
try{
 await page.goto(process.env.RELEX_LIVE_URL);
 await page.getByLabel("Email",{exact:true}).fill(config.admin_email);await page.getByLabel("Password",{exact:true}).fill(config.password);await page.getByRole("button",{name:"Sign in",exact:true}).click();
 await page.getByRole("button",{name:"Chat",exact:true}).click();
 await page.getByLabel("Question",{exact:true}).fill("What evidence is available for the Finland launch?");
 const [response]=await Promise.all([page.waitForResponse(r=>r.url().endsWith("/chat"),{timeout:60000}),page.getByRole("button",{name:"Ask",exact:true}).click()]);
 fs.writeFileSync(path.join(path.dirname(process.env.RELEX_LIVE_CONFIG),"failed-request.json"),JSON.stringify(response.request().postDataJSON()),{mode:0o600});
 if(response.status()!==503)throw new Error("Unavailable real dependency did not produce 503");
 const payload=await response.json();if(payload.error.code!=="provider_unavailable"&&payload.error.code!=="dependency_unavailable")throw new Error("Unsafe error code");
 if("claims"in payload)throw new Error("Unchecked claims exposed on failure");
 await page.getByRole("button",{name:"Retry question",exact:true}).waitFor();
 if(await page.getByLabel("View supporting quote").count())throw new Error("Provider failure styled as verified answer");
 const result={status:"PASS",cases:["Actual owned HTTP process uses unreachable embedding endpoint","Real chat route returns safe 503 with no claims","Browser shows retry action and no verified citation"]};
 fs.writeFileSync(path.join(path.dirname(process.env.RELEX_LIVE_CONFIG),"provider-failure.json"),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
}finally{await browser.close();}

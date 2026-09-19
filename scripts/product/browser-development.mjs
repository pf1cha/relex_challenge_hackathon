import {chromium} from "../../frontend/node_modules/playwright/index.mjs";
const browser=await chromium.launch({headless:true,args:["--no-sandbox"]});
try{
 const page=await browser.newPage();await page.goto(process.env.RELEX_FIXTURE_ORIGIN);
 await page.getByLabel("Email",{exact:true}).fill("fixture@synthetic.invalid");
 await page.getByLabel("Password",{exact:true}).fill("synthetic-password");
 await page.getByRole("button",{name:"Sign in",exact:true}).click();
 await page.getByText("SYNTHETIC DEVELOPMENT FIXTURE",{exact:true}).first().waitFor();
 await page.getByRole("button",{name:"Sign out",exact:true}).click();
 await page.getByRole("button",{name:"Sign in",exact:true}).waitFor();
 console.log("Development browser PASS: actual routes/browser; A/B are explicit synthetic substitutes. Not acceptance.");
}finally{await browser.close();}

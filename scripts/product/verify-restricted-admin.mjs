import {chromium} from '../../frontend/node_modules/playwright/index.mjs';
import {readFileSync,writeFileSync} from 'node:fs';
import {randomUUID} from 'node:crypto';

const cfg=JSON.parse(readFileSync('.runtime/manual/admin-check.json','utf8'));
const url=process.env.RELEX_VERIFY_URL||'http://127.0.0.1:18080';
const artifact=process.env.RELEX_VERIFY_ARTIFACT||'.runtime/manual/restricted-admin-verification.json';
const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
const adminContext=await browser.newContext({viewport:{width:1440,height:1000}});
const memberContext=await browser.newContext({viewport:{width:1280,height:900}});
const admin=await adminContext.newPage(),member=await memberContext.newPage();
const email='restricted-check-'+randomUUID()+'@example.test',password=randomUUID();
const base='/api/projects/'+cfg.project;
const checks=[];
let memberId=null;
async function login(page,email,password){
 await page.goto(url);await page.getByLabel('Email',{exact:true}).fill(email);
 await page.getByLabel('Password',{exact:true}).fill(password);
 await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await page.getByRole('button',{name:'Sign out',exact:true}).waitFor();
}
async function request(page,path,options={}){
 return page.evaluate(async({path,options})=>{const response=await fetch(path,options);return {status:response.status,body:await response.text()};},{path,options});
}
try{
 await member.goto(url);await member.getByRole('button',{name:'Create account',exact:true}).click();
 await member.getByLabel('Display name',{exact:true}).fill('Restricted access verification');
 await member.getByLabel('Email',{exact:true}).fill(email);await member.getByLabel('Password',{exact:true}).fill(password);
 await member.getByRole('button',{name:'Create account',exact:true}).click();
 await member.getByText('No workspace access',{exact:true}).waitFor();
 memberId=await member.evaluate(async()=>await fetch('/api/me').then(response=>response.json()).then(value=>value.user_id));

 await login(admin,cfg.email,cfg.password);await admin.getByRole('link',{name:'Administration',exact:true}).click();
 await admin.getByRole('heading',{name:'Original documents',exact:true}).waitFor();
 const groups=admin.locator('.original-document-library > details.record-type-group');
 await groups.first().waitFor();
 if(await groups.count()<2)throw Error('Expected original documents grouped by record type');
 for(let index=0;index<await groups.count();index++)if(await groups.nth(index).getAttribute('open')!==null)throw Error('Original document group was not folded');
 checks.push('Original documents are grouped by folded record type');

 const firstGroup=groups.first();await firstGroup.locator('summary').click();
 const firstDocument=firstGroup.locator('.original-document-card').first();
 await firstDocument.getByRole('button',{name:'View original',exact:true}).click();
 const content=firstDocument.locator('.original-document-content');await content.waitFor();
 if(!(await content.textContent()).trim())throw Error('Original document content was empty');
 checks.push('Administrator can open original source content on demand');

 const mappingGroups=admin.locator('.identity-mappings-panel .identity-kind-group');await mappingGroups.first().waitFor();
 for(let index=0;index<await mappingGroups.count();index++)if(await mappingGroups.nth(index).getAttribute('open')!==null)throw Error('Identifier mapping group was not folded');
 await admin.getByLabel('Search pseudonym or identity',{exact:true}).fill('PERSON_');
 await admin.getByRole('button',{name:'Search mappings',exact:true}).click();
 const mapping=admin.locator('.identity-row').first();await mapping.waitFor();
 if(!(await mapping.locator('strong').textContent()).startsWith('PERSON_'))throw Error('Pseudonym search did not return a mapping');
 if(await admin.locator('.identity-mappings-panel .identity-kind-group[open]').count()===0)throw Error('Filtered mapping group did not open');
 checks.push('Identifier mappings are folded until an administrator searches');

 const peopleGroups=admin.locator('.people-directory-panel .identity-kind-group');await peopleGroups.first().waitFor();
 for(let index=0;index<await peopleGroups.count();index++)if(await peopleGroups.nth(index).getAttribute('open')!==null)throw Error('People directory group was not folded');
 await admin.getByLabel('Search people directory',{exact:true}).fill('Katarina');await admin.getByRole('button',{name:'Search people',exact:true}).click();
 const person=admin.locator('.people-directory-panel .identity-row').first();await person.waitFor();
 if(!(await person.textContent()).includes('Katarina'))throw Error('People directory search did not filter results');
 if(await person.getByRole('button',{name:'Erase personal information',exact:true}).count()!==1)throw Error('People result lost privacy action');
 checks.push('People directory matches folded mapping style and supports search');

 const csrf=await admin.evaluate(async()=>await fetch('/api/me').then(response=>response.json()).then(value=>value.csrf_token));
 const grant=await request(admin,base+'/members',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify({email,role:'member'})});
 if(grant.status!==200)throw Error('Could not grant temporary member access: '+grant.status);
 await member.reload();await member.getByRole('link',{name:'Documents',exact:true}).waitFor();
 if(await member.getByRole('link',{name:'Administration',exact:true}).count())throw Error('Member saw administration navigation');
 for(const path of [base+'/original-documents',base+'/identity-mappings']){
  const denied=await request(member,path);if(denied.status!==403)throw Error('Member was not denied '+path+': '+denied.status);
 }
 checks.push('Regular member has no administration UI and receives 403 from both restricted APIs');
 await admin.getByLabel('Search pseudonym or identity',{exact:true}).fill('');await admin.getByRole('button',{name:'Search mappings',exact:true}).click();
 await admin.getByLabel('Search people directory',{exact:true}).fill('');await admin.getByRole('button',{name:'Search people',exact:true}).click();
 await mappingGroups.first().waitFor();
 if(await admin.locator('.identity-kind-group[open]').count())throw Error('Directory groups did not return to folded state');
 await firstGroup.locator('summary').click();
 await admin.screenshot({path:'.runtime/manual/restricted-admin-browser.png',fullPage:true});
 await admin.setViewportSize({width:390,height:844});
 if(await admin.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth))throw Error('Administration layout overflows mobile viewport');
 await admin.screenshot({path:'.runtime/manual/restricted-admin-mobile.png',fullPage:true});
 checks.push('Administration layout fits a 390px mobile viewport');
 writeFileSync(artifact,JSON.stringify({status:'PASS',checks},null,2));
 console.log(JSON.stringify({status:'PASS',checks}));
}finally{
 if(memberId){
  try{const csrf=await admin.evaluate(async()=>await fetch('/api/me').then(response=>response.json()).then(value=>value.csrf_token));await request(admin,base+'/members/'+encodeURIComponent(memberId),{method:'DELETE',headers:{'X-CSRF-Token':csrf}});}catch{}
 }
 await browser.close();
}

import fs from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';
const require=createRequire(import.meta.url);
const pw=require('playwright');
const pack=path.resolve('offline-study-pack/2026-11-04');
const browser=await pw.chromium.launch({channel:'chrome',headless:true});
const context=await browser.newContext({viewport:{width:1440,height:1000}});
await context.addInitScript(()=>localStorage.setItem('regatta_view_mode','grid'));
const page=await context.newPage();
const errors=[]; page.on('pageerror',e=>errors.push(e.message));
const external=[];
await context.route('**/*',r=>{if(!new URL(r.request().url()).hostname.match(/^(127\.0\.0\.1|localhost)$/)){external.push(r.request().url());return r.abort()}return r.continue()});
const captures=[];
for(const view of ['replay','analysis','compare','reports','forecast']){
  await page.goto('http://127.0.0.1:5197/?race=naples_pr1&t=240&view='+view);
  await page.getByRole('banner').waitFor();
  await page.waitForTimeout(1800);
  await page.screenshot({path:path.join(pack,'assets',view+'.png'),fullPage:false});
  captures.push({view,url:page.url(),title:await page.title(),text_excerpt:(await page.locator('main').innerText()).slice(0,400)});
}
await fs.writeFile(path.join(pack,'verification/dashboard-captures.json'),JSON.stringify({captured_utc:new Date().toISOString(),external_blocked:true,external_requests:external,errors,captures},null,2));
await browser.close();
console.log(JSON.stringify({screenshots:captures.length,errors,external_requests:external.length}));

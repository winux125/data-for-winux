// Real UI -> real API. Never print video pixels, scene descriptions, evidence or keys.
const {createRequire}=require('node:module');
const {resolve}=require('node:path');
const {chromium}=createRequire(resolve(process.env.FORTE_FRONTEND_DIR||resolve(__dirname,'../forte-vision'),'package.json'))('@playwright/test');
const fs=require('node:fs');
(async()=>{
 const video=process.argv[2];
 if(!video||!fs.existsSync(video))throw Error('Pass the path to a real negative MOV: node browser_api_smoke.cjs /path/to/video.mov');
 fs.mkdirSync('data',{recursive:true});
 const browser=await chromium.launch({headless:true});
 try {
  const page=await browser.newPage({reducedMotion:'reduce',viewport:{width:1366,height:900}});
  const errors=[],statuses=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('response',r=>{if(r.url().includes('/api/browser/analyze'))statuses.push(r.status());});
  await page.goto((process.env.FORTE_PUBLIC_URL||'https://forte26.vercel.app')+'/app',{waitUntil:'networkidle'});
  await page.locator('.fv-mode-pill[data-connection=connected]').waitFor({timeout:30000});
  await page.getByLabel('Выбрать видеозапись',{exact:true}).setInputFiles(video);
  await page.getByRole('button',{name:'Начать проверку',exact:true}).click();
  await page.locator('#review-heading').waitFor({timeout:290000});
  const clean=await page.getByText('Нарушение не обнаружено',{exact:true}).count();
  const report={realUiApi:true,uploadStatuses:statuses,noViolationVisible:clean>0,errors};
  fs.writeFileSync('data/browser-api-smoke.json',JSON.stringify(report,null,2));
  console.log(JSON.stringify(report));
  if(!clean||errors.length||!statuses.includes(202))process.exitCode=1;
 } finally {await browser.close();}
})();

// Render a private saved API response locally; report structural checks only.
const { chromium } = require('playwright');
const fs = require('fs');
(async()=>{
  const payload=JSON.parse(fs.readFileSync(process.argv[2]||'data/benchmark/11.json','utf8'));
  if(payload.status!=='done'||!payload.violations.length)throw Error('A real completed positive response is required');
  const browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:1280,height:1100}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('https://185.216.22.24.sslip.io',{waitUntil:'networkidle'});
  await page.evaluate(value=>render(value),payload);
  await page.locator('.frame img').first().waitFor();
  await page.waitForFunction(()=>[...document.querySelectorAll('.frame img')].every(i=>i.complete&&i.naturalWidth>0));
  const events=await page.locator('.event').count();
  const images=await page.locator('.frame img').count();
  await page.screenshot({path:'data/ui-real-result-private.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:'data/ui-real-result-mobile-private.png',fullPage:true});
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
  console.log(JSON.stringify({events,images,expectedEvents:payload.violations.length,mobileHorizontalOverflow:overflow,errors}));
  await browser.close();
})();

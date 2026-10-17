const {chromium} = require('playwright');
const fs = require('node:fs');
(async () => {
  fs.mkdirSync('data', {recursive:true});
  const browser=await chromium.launch({headless:true});
  const origin=process.env.FORTE_PUBLIC_URL || 'https://154.54.100.194.sslip.io';
  const checks=[];
  for(const locale of ['ru','kk','en']) {
    const context=await browser.newContext({reducedMotion:'reduce'});
    await context.addCookies([{name:'forte-locale',value:locale,url:origin}]);
    const page=await context.newPage();
    const errors=[],external=new Set();
    page.on('pageerror',e=>errors.push(e.message));
    page.on('request',r=>{const u=new URL(r.url());if(u.protocol.startsWith('http')&&u.origin!==origin)external.add(u.origin);});
    for(const width of [1366,375]) {
      await page.setViewportSize({width,height:900});
      await page.goto(origin+'/app',{waitUntil:'networkidle'});
      await page.locator('#main h1').waitFor();
      await page.screenshot({path:`data/forte-vision-${locale}-${width}.png`,fullPage:true});
      checks.push({locale,width,lang:await page.locator('html').getAttribute('lang'),
        overflow:await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),
        errors:[...errors],externalOrigins:[...external]});
    }
    await context.close();
  }
  await browser.close();
  fs.writeFileSync('data/frontend-browser-checks.json',JSON.stringify(checks,null,2));
  console.log(JSON.stringify(checks));
  if(checks.some(c=>c.overflow||c.errors.length))process.exitCode=1;
})();

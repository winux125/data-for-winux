import {webkit} from '@playwright/test';
const browser=await webkit.launch();
try {
 const page=await browser.newPage({viewport:{width:768,height:900}});
 await page.goto('https://154.54.100.194.sslip.io/app');
 const badge=page.locator('.checks-table-desktop .check-status--violation').first();
 await badge.waitFor({state:'visible'});
 const metrics=()=>badge.evaluate(el=>({html:el.outerHTML,display:getComputedStyle(el).display,
   line:getComputedStyle(el).lineHeight,height:el.getBoundingClientRect().height,
   ancestors:[el.parentElement,el.parentElement.parentElement,el.parentElement.parentElement.parentElement].map(n=>({tag:n.tagName,display:getComputedStyle(n).display,html:n.outerHTML.slice(0,150)}))}));
 console.log('BEFORE',JSON.stringify(await metrics()));
 await badge.scrollIntoViewIfNeeded();
 console.log('AFTER',JSON.stringify(await metrics()));
} finally {await browser.close();}

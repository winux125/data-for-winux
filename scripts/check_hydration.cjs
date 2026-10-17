const {chromium}=require('playwright');
const fs=require('fs');
(async()=>{
 const browser=await chromium.launch({headless:true});
 for(const js of [false,true]){
  const c=await browser.newContext({javaScriptEnabled:js,reducedMotion:'reduce'});
  await c.addCookies([{name:'forte-locale',value:'kk',url:'https://154.54.100.194.sslip.io'}]);
  const p=await c.newPage();
  await p.goto('https://154.54.100.194.sslip.io/app',{waitUntil:'networkidle'});
  const texts=await p.locator('body').evaluate(el=>{
   const walk=document.createTreeWalker(el,NodeFilter.SHOW_TEXT),texts=[];
   while(walk.nextNode()){const n=walk.currentNode;if(!n.parentElement?.closest('script,style'))texts.push(n.textContent);}
   return texts.join('\n');
  });
  fs.writeFileSync(`data/hydration-${js}.txt`,texts);
  await c.close();
 }
 await browser.close();
})();

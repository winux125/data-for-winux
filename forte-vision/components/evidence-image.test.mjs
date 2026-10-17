import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import test from "node:test";
import ts from "typescript";
const require=createRequire(import.meta.url);
function harness() {
  let state; const ready=[]; const cache=new Map();
  function load(name) {
    if(name==="react") return {useState(initial){state??=initial;return [state,next=>{state=next;}];},useRef:value=>({current:value}),useEffect(){},useMemo:fn=>fn()};
    if(name==="@/components/locale-provider") return {useI18n:()=>({t:(text,values={})=>text.replace(/\{([^}]+)\}/g,(m,key)=>values[key]??m)})};
    if(name==="lucide-react") return new Proxy({}, {get:()=>()=>null});
    if(name==="@/lib/analysis") return {formatTime:seconds=>String(seconds)};
    if(!name.startsWith("@/")) return require(name);
    if(cache.has(name)) return cache.get(name).exports;
    const module={exports:{}};cache.set(name,module);
    const source=readFileSync(new URL(`../${name.slice(2)}${name.startsWith("@/components")?".tsx":".ts"}`,import.meta.url),"utf8");
    vm.runInNewContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText,{module,exports:module.exports,require:load});
    return module.exports;
  }
  const {EvidenceImage}=load("@/components/evidence-image");
  return {ready,render:()=>EvidenceImage({source:"bounded-local-image",alt:"Frame",onReady:value=>ready.push(value)})};
}
function find(node,type) { if(!node||typeof node!=="object")return; if(node.type===type)return node; for(const child of [node.props?.children].flat(2)){const found=find(child,type);if(found)return found;} }
test("decode failure replaces the image and never enables enlargement", async()=>{
  const h=harness(); await find(h.render(),"img").props.onLoad({currentTarget:{naturalWidth:100,naturalHeight:100,decode:()=>Promise.reject(new Error("corrupt"))}});
  assert.equal(find(h.render(),"img"),undefined); assert.deepEqual(h.ready,[false]);
});
test("enlargement waits for decode and is revoked if a later image error occurs",async()=>{
  const h=harness();let resolve;const decode=new Promise(r=>resolve=r);
  const loading=find(h.render(),"img").props.onLoad({currentTarget:{naturalWidth:100,naturalHeight:100,decode:()=>decode}});
  assert.deepEqual(h.ready,[]);resolve();await loading;assert.deepEqual(h.ready,[true]);
  find(h.render(),"img").props.onError();assert.deepEqual(h.ready,[true,false]);assert.equal(find(h.render(),"img"),undefined);
});
test("oversized decoded dimensions are rejected before readiness",async()=>{
  const h=harness();await find(h.render(),"img").props.onLoad({currentTarget:{naturalWidth:10000,naturalHeight:10000}});
  assert.deepEqual(h.ready,[false]);assert.equal(find(h.render(),"img"),undefined);
});

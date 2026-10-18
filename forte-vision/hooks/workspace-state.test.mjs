import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import ts from "typescript";
const require=createRequire(import.meta.url);
const plain=value=>JSON.parse(JSON.stringify(value));

// Deterministic hook boundary: real history entries, explicit traversal, and a clock.
function harness(moduleName,hookName,args=()=>[],href="https://frontend.example/app") {
  const storage=new Map(); const requests=[];
  const cells=[];const effects=[];const timers=new Map();const events=new Map();const cache=new Map();
  let now=1000;let timerId=0;let cursor=0;let queued=false;let alive=true;let value;
  let index=0;const entries=[{url:href,state:{framework:"preserved"}}];
  const location={};const locate=()=>Object.assign(location,{origin:new URL(entries[index].url).origin,pathname:new URL(entries[index].url).pathname,hash:new URL(entries[index].url).hash});locate();
  const clone=value=>plain(value);
  const history={get state(){return entries[index].state;},replaceState(state,_,url){entries[index]={state:clone(state),url:new URL(url,entries[index].url).href};locate();},pushState(state,_,url){entries.splice(++index);entries.push({state:clone(state),url:new URL(url,entries[index-1].url).href});locate();}};
  const window={location,history,addEventListener(name,fn){events.set(name,fn);},removeEventListener(name,fn){if(events.get(name)===fn)events.delete(name);}};
  const schedule=()=>{if(!queued&&alive){queued=true;queueMicrotask(()=>{queued=false;if(alive)render();});}};
  const react={
    useState(initial){const id=cursor++;if(!(id in cells))cells[id]=typeof initial==="function"?initial():initial;return [cells[id],next=>{if(!alive)return;const value=typeof next==="function"?next(cells[id]):next;if(Object.is(value,cells[id]))return;cells[id]=value;schedule();}];},
    useRef(initial){const id=cursor++;return cells[id]||=( {current:initial} );},
    useCallback(fn,deps){const id=cursor++;if(!cells[id]||deps.some((d,i)=>!Object.is(d,cells[id].deps[i])))cells[id]={fn,deps};return cells[id].fn;},
    useEffect(fn,deps){const id=cursor++;const old=cells[id];if(!old||deps.some((d,i)=>!Object.is(d,old.deps[i]))){cells[id]={deps,cleanup:old?.cleanup};effects.push(()=>{cells[id].cleanup?.();cells[id].cleanup=fn();});}},
  };
  class ClockDate extends Date {static now(){return now;}}
  function load(name){
    if(name==="react")return react;
    if(!name.startsWith("@/"))return require(name);
    if(cache.has(name))return cache.get(name).exports;
    const module={exports:{}};cache.set(name,module);
    const code=ts.transpileModule(readFileSync(new URL(`../${name.slice(2)}.ts`,import.meta.url),"utf8"),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
    vm.runInNewContext(code,{module,exports:module.exports,require:load,URL,Error,window,Date:ClockDate,AbortController,
      sessionStorage:{getItem:key=>storage.get(key)||null,setItem:(key,value)=>storage.set(key,value)},
      fetch:async url=>{requests.push(url);return {ok:true,json:async()=>String(url).endsWith("/config")?{base_url:"https://api.example",max_upload_bytes:10*1024**3}:{token:"scoped-test-session",expires_at:100000}};},
      setTimeout(fn,ms){const id=++timerId;timers.set(id,{fn,at:now+ms});return id;},clearTimeout(id){timers.delete(id);},
    });return module.exports;
  }
  const hook=load(moduleName)[hookName];function render(){cursor=0;value=hook(...args());while(effects.length)effects.shift()();}render();
  return {get state(){return value;},entries,location,events,timers,load,requests,storage,rerender:render,
    async flush(){for(let i=0;i<8;i++)await Promise.resolve();},
    async until(predicate){for(let i=0;i<100;i++){if(predicate(value))return;await Promise.resolve();}assert.fail("Hook did not settle to the expected state");},
    traverse(offset){index+=offset;assert.ok(index>=0&&index<entries.length);locate();events.get("popstate")?.({state:history.state});},
    tick(ms,run=true){now+=ms;if(run)for(const [id,timer]of [...timers])if(timer.at<=now&&timers.delete(id))timer.fn();},
    unmount(){alive=false;for(const cell of cells)cell?.cleanup?.();},
  };
}

test("sections, checks and consecutive events follow browser back and forward",async()=>{
  const h=harness("@/hooks/use-workspace-navigation","useWorkspaceNavigation");await h.flush();
  h.state.goSection("checks");await h.flush();h.state.openCheck("DEMO-001");await h.flush();
  h.state.reviewAction({type:"inspect",index:0,count:2,position:19.5});await h.flush();
  h.state.reviewAction({type:"inspect",index:1,count:2});await h.flush();
  assert.equal(h.location.hash,"#workspace/checks/DEMO-001/event/2");
  h.traverse(-1);await h.flush();assert.equal(h.state.route.review.eventIndex,0);
  h.traverse(-1);await h.flush();assert.equal(h.state.route.review.screen,"video");assert.equal(h.state.route.review.position,19.5);
  h.traverse(-1);await h.flush();assert.equal(h.state.route.checkId,null);assert.equal(h.state.route.section,"checks");
  h.traverse(1);await h.flush();assert.equal(h.state.route.checkId,"DEMO-001");
  h.traverse(1);await h.flush();assert.equal(h.state.route.review.eventIndex,0);
  assert.equal(h.entries.at(-1).state.framework,"preserved");h.unmount();assert.equal(h.events.size,0);
});
test("time replaces entries; clip mode and position survive traversal; stale video callbacks are ignored",async()=>{
  const h=harness("@/hooks/use-workspace-navigation","useWorkspaceNavigation");await h.flush();h.state.openCheck("DEMO-001");await h.flush();
  const count=h.entries.length;for(let seconds=1;seconds<=8;seconds++)h.state.reviewAction({type:"time",seconds});await h.flush();assert.equal(h.entries.length,count);
  h.state.reviewAction({type:"inspect",index:0,count:2,position:8});await h.flush();h.state.reviewAction({type:"watch_clip",start:1,end:7});await h.flush();
  h.state.reviewAction({type:"time",seconds:3});await h.flush();h.state.reviewAction({type:"full_video"});await h.flush();
  const revision=h.state.revision;h.traverse(-1);await h.flush();assert.deepEqual(plain(h.state.route.review.clip),{start:1,end:7});assert.equal(h.state.route.review.position,3);
  h.state.reviewAction({type:"time",seconds:99},false,"DEMO-001",revision);await h.flush();assert.equal(h.state.route.review.position,3);
  h.state.reviewAction({type:"time",seconds:99},false,"different",h.state.revision);await h.flush();assert.equal(h.state.route.review.position,3);
  const serialized=JSON.stringify(h.entries);for(const secret of ["apiKey","videoUrl","image_base64","result","blob:"])assert.ok(!serialized.includes(secret));h.unmount();
});
test("an event URL opens directly and malformed history payload cannot inject media or selection",async()=>{
  const h=harness("@/hooks/use-workspace-navigation","useWorkspaceNavigation",()=>[],"https://frontend.example/app#workspace/checks/DEMO-001/event/2");await h.flush();assert.equal(h.state.route.review.eventIndex,1);
  const {readWorkspaceRoute}=h.load("@/lib/workspace-navigation");assert.equal(readWorkspaceRoute("#main"),null);
  assert.equal(readWorkspaceRoute("#workspace/checks/%2Fsecret/event/1").checkId,null);
  const invalid=readWorkspaceRoute("#workspace/checks/DEMO-001/event/2",{forteWorkspaceNavigationV1:{section:"checks",checkId:"different",review:{screen:"event",eventIndex:999,position:Infinity}}});
  assert.equal(invalid.review.eventIndex,1);assert.equal(invalid.review.position,0);h.unmount();
});

test("automatic connection uses a scoped session without a jury key or manual settings",async()=>{
  const h=harness("@/hooks/use-api-connection","useApiConnection");await h.until(s=>s.connection.state==="connected");
  assert.equal(h.state.connection.state,"connected");assert.equal(h.state.api.browser,true);
  assert.equal(h.state.api.apiKey,"scoped-test-session");assert.equal(h.requests.length,2);
  const config=h.state.api;
  h.state.report({...config,apiKey:"wrong"},{kind:"failure",error:new Error("unrelated")});await h.flush();
  assert.equal(h.state.connection.state,"connected");
  h.state.retry();await h.until(s=>s.connection.state==="connected"&&h.requests.length===3);assert.equal(h.requests.length,3);
  assert.equal(h.state.api.apiKey,config.apiKey);h.unmount();
});
test("transport, authentication, protocol and model failures have distinct connection meanings",async()=>{
  const h=harness("@/hooks/use-api-connection","useApiConnection");await h.until(s=>s.connection.state==="connected");const config=h.state.api;
  const {AnalysisError}=h.load("@/lib/analysis");
  for(const [error,state]of [[new AnalysisError("offline","network",true),"unavailable"],[new AnalysisError("denied","http",false,401),"rejected"],[new AnalysisError("bad JSON","invalid_response"),"error"]]){
    h.state.report(config,{kind:"failure",error});await h.flush();assert.equal(h.state.connection.state,state);
  }
  h.state.report(config,{kind:"response"});await h.flush();h.state.report(config,{kind:"failure",error:new AnalysisError("model failed","job_failed")});await h.flush();assert.equal(h.state.connection.state,"connected");
  h.state.report(config,{kind:"retry"});await h.flush();assert.equal(h.state.connection.state,"reconnecting");
  h.unmount();assert.equal(h.timers.size,0);
});

const record=id=>({id,name:`${id}.mov`,status:"no_violation",createdAt:"2026-10-18",duration:"00:12",events:0,videoUrl:`blob:${id}`,result:{job_id:id,status:"done",verdict:"no_violation",violations:[]}});
test("Undo restores exact result objects, video URLs, order and selection even after a new upload",async()=>{
  const original=[record("a"),record("b"),record("c")];let records=[...original];const purged=[];let h;
  const setRecords=fn=>{records=fn(records);};h=harness("@/hooks/use-undo-deletion","useUndoDeletion",()=>[records,setRecords,removed=>purged.push(...removed)]);await h.flush();
  h.state.remove(["a","c"],["a","c"]);await h.flush();assert.equal(records.length,1);assert.equal(purged.length,0);
  records=[record("new"),...records];h.rerender();const saved=h.state.undo();await h.flush();assert.deepEqual(plain(records.map(r=>r.id)),["new","a","b","c"]);
  assert.equal(records[1],original[0]);assert.equal(records[3].result,original[2].result);assert.equal(records[3].videoUrl,"blob:c");assert.deepEqual(plain(saved.selected),["a","c"]);
  h.tick(20_000);await h.flush();assert.equal(purged.length,0);h.unmount();
});
test("consecutive deletions share Undo; expiration purges once and late Undo does not resurrect data",async()=>{
  let records=[record("a"),record("b"),record("c")];const purged=[];const setRecords=fn=>{records=fn(records);};
  const h=harness("@/hooks/use-undo-deletion","useUndoDeletion",()=>[records,setRecords,removed=>purged.push(...removed)]);await h.flush();
  h.state.remove(["a"],[]);await h.flush();h.tick(1000);h.state.remove(["b"],[]);await h.flush();assert.equal(h.state.pending.records.length,2);
  h.tick(9000);await h.flush();assert.equal(purged.length,0);assert.ok(h.state.undo());await h.flush();assert.deepEqual(plain(records.map(r=>r.id)),["a","b","c"]);
  h.state.remove(["a"],[]);await h.flush();h.tick(10_000);await h.flush();assert.deepEqual(purged.map(r=>r.id),["a"]);assert.equal(h.state.undo(),null);assert.equal(records.some(r=>r.id==="a"),false);h.unmount();
});
test("a throttled expired deletion is finalized before the next deletion starts",async()=>{
  let records=[record("a"),record("b")];const purged=[];const setRecords=fn=>{records=fn(records);};
  const h=harness("@/hooks/use-undo-deletion","useUndoDeletion",()=>[records,setRecords,removed=>purged.push(...removed)]);await h.flush();
  h.state.remove(["a"],[]);await h.flush();h.tick(11_000,false);h.state.remove(["b"],[]);await h.flush();assert.deepEqual(purged.map(r=>r.id),["a"]);
  h.state.undo();await h.flush();assert.deepEqual(plain(records.map(r=>r.id)),["b"]);h.unmount();assert.equal(h.timers.size,0);
});

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import ts from "typescript";

// Exercise the hook at its transport/storage boundaries without a DOM or timers.
function harness(saved = "[]") {
  const cells = []; const pending = []; const calls = []; const notices = []; const storage = new Map([["forte-job-checkpoints-v1", saved]]);
  let cursor = 0; let queued = false; let mounted = true; let state;
  const schedule = () => { if (!queued && mounted) { queued = true; queueMicrotask(() => { queued = false; if (mounted) render(); }); } };
  const react = {
    useState(initial) { const id = cursor++; if (!(id in cells)) cells[id] = typeof initial === "function" ? initial() : initial;
      return [cells[id], value => { if (!mounted) return; cells[id] = typeof value === "function" ? value(cells[id]) : value; schedule(); }]; },
    useRef(initial) { const id = cursor++; return cells[id] ||= { current: initial }; },
    useCallback(fn, deps) { const id = cursor++; const cell = cells[id]; if (!cell || deps.some((d,i) => !Object.is(d,cell.deps[i]))) cells[id] = { fn, deps }; return cells[id].fn; },
    useEffect(fn, deps) { const id = cursor++; const cell = cells[id]; if (!cell || deps.some((d,i) => !Object.is(d,cell.deps[i]))) {
      cells[id] = { deps, cleanup: cell?.cleanup }; pending.push(() => { cells[id].cleanup?.(); cells[id].cleanup = fn(); });
    } },
  };
  const cache = new Map();
  const transport = (mode, input, config, options) => new Promise((resolve, reject) => {
    const call = { mode, input, config, options, resolve, reject }; calls.push(call);
    options.signal.addEventListener("abort", () => reject(new Error("aborted")), { once: true });
  });
  function load(name) {
    if (name === "react") return react;
    if (cache.has(name)) return cache.get(name).exports;
    const module = { exports: {} }; cache.set(name, module);
    const path = new URL(`../${name.slice(2)}.ts`, import.meta.url);
    const code = ts.transpileModule(readFileSync(path,"utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
    vm.runInNewContext(code, { module, exports: module.exports, require: load, Error, URL, AbortController, queueMicrotask,
      crypto: { randomUUID: () => `test-${calls.length}` },
      sessionStorage: { getItem: key => storage.get(key), setItem: (key,value) => storage.set(key,value) },
      window: { location: { origin: "https://api.example.kz" }, addEventListener() {}, removeEventListener() {} },
    }, { filename: name });
    if (name === "@/lib/analysis") {
      module.exports.analyzeVideo = (file,config,options) => transport("upload",file,config,options);
      module.exports.resumeAnalysis = (id,config,options) => transport("resume",id,config,options);
    }
    return module.exports;
  }
  const { useAnalysisJobs } = load("@/hooks/use-analysis-jobs");
  const notice = (...args) => notices.push(args);
  function render() { cursor = 0; state = useAnalysisJobs([],notice); while (pending.length) pending.shift()(); }
  render();
  return { get state() { return state; }, calls, notices, storage,
    async flush() { for (let i=0;i<8;i++) await Promise.resolve(); },
    unmount() { mounted = false; for (const cell of cells) cell?.cleanup?.(); },
  };
}
const file = { name: "review.mov", size: 100 }; const config = { baseUrl: "https://api.example.kz", apiKey: "runtime-secret" };
const processing = { job_id: "server-1", status: "processing", progress: 47 };
const done = { job_id: "server-1", status: "done", verdict: "no_violation", violations: [] };

test("history exists before upload completes and one entry survives pause and GET-only resume", async () => {
  const h = harness(); await h.flush();
  const id = h.state.start(file,"blob:video",12,config);
  assert.equal(h.state.start(file,"blob:duplicate",12,config), null);
  await h.flush(); assert.equal(h.state.records.length,1); assert.equal(h.state.records[0].status,"uploading");
  h.calls[0].options.onStatus(processing); await h.flush();
  assert.equal(h.state.records[0].jobId,"server-1"); assert.equal(h.state.records[0].progress,47);
  h.state.cancel(); await h.flush();
  assert.equal(h.state.busyId,null); assert.equal(h.state.records[0].status,"paused");
  h.state.resume(id,config); await h.flush();
  assert.equal(h.calls.length,2); assert.equal(h.calls[1].mode,"resume"); assert.equal(h.calls[1].input,"server-1");
  h.calls[1].resolve(done); await h.flush();
  assert.equal(h.state.records.length,1); assert.equal(h.state.records[0].id,id); assert.equal(h.state.records[0].status,"no_violation");
  assert.equal(h.storage.get("forte-job-checkpoints-v1"),"[]"); h.unmount();
});

test("reload restores an explicit paused job, without key, blob, or an automatic request", async () => {
  const h = harness(); await h.flush(); h.state.start(file,"blob:video",12,config); await h.flush();
  h.calls[0].options.onStatus(processing); await h.flush();
  const checkpoint = h.storage.get("forte-job-checkpoints-v1"); h.unmount(); await h.flush();
  assert.ok(checkpoint.includes("server-1")); assert.ok(!checkpoint.includes("runtime-secret")); assert.ok(!checkpoint.includes("blob:"));
  const restored = harness(checkpoint); await restored.flush();
  assert.equal(restored.calls.length,0); assert.equal(restored.state.records[0].status,"paused");
  restored.state.resume(restored.state.records[0].id,{ ...config,baseUrl:"https://different.example.kz" });
  assert.equal(restored.calls.length,0); assert.equal(restored.notices.length,1);
  restored.state.resume(restored.state.records[0].id,config); await restored.flush();
  assert.equal(restored.calls[0].mode,"resume"); restored.calls[0].resolve(done); await restored.flush(); restored.unmount();
});

test("unmount aborts the request and late responses cannot change the disposed session", async () => {
  const h = harness(); await h.flush(); h.state.start(file,"blob:video",12,config); await h.flush();
  h.unmount(); assert.equal(h.calls[0].options.signal.aborted,true);
  h.calls[0].options.onStatus(done); await h.flush();
  assert.equal(h.state.records[0].status,"uploading"); assert.equal(h.notices.length,0);
});

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import vm from "node:vm";

// Exercise the browser integration with Node's test runner and TypeScript already
// installed by the app. No framework, server, network or new dependency required.
const require = createRequire(import.meta.url);
const ts = require("typescript");
const compiled = ts.transpileModule(readFileSync(new URL("./analysis.ts", import.meta.url), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText;
const evidence = {};
vm.runInNewContext(ts.transpileModule(readFileSync(new URL("./evidence.ts", import.meta.url),"utf8"), { compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022} }).outputText,{exports:evidence});
const config = { baseUrl: "https://analysis.example.kz", apiKey: "runtime-test-key" };
const png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLbtAAAAABJRU5ErkJggg==";
const file = () => new File(["video content"], "cashdesk.mov", { type: "video/quicktime" });
const completed = (extra = {}) => ({ job_id: "job-1", status: "done", verdict: "no_violation", violations: [], ...extra });

function harness() {
  let now = 0;
  let nextId = 1;
  const timers = new Map();
  const uploads = [];
  const polls = [];
  const replies = [];
  class MockXHR {
    upload = {};
    headers = {};
    status = 0;
    responseText = "";
    aborted = false;
    constructor() { uploads.push(this); }
    open(method, url) { this.method = method; this.url = url; }
    setRequestHeader(name, value) { this.headers[name] = value; }
    send(body) { this.body = body; }
    abort() { this.aborted = true; this.onabort?.(); }
    respond(body, status = 202) { this.status = status; this.responseText = JSON.stringify(body); this.onload?.(); }
  }
  const module = { exports: {} };
  const context = {
    module,
    exports: module.exports,
    URL,
    FormData,
    TextEncoder, TextDecoder,
    require(name) { if (name === "@/lib/evidence") return evidence; throw new Error(name); },
    AbortController,
    XMLHttpRequest: MockXHR,
    setTimeout(callback, ms) { const id = nextId++; timers.set(id, { callback, at: now + ms }); return id; },
    clearTimeout(id) { timers.delete(id); },
    async fetch(url, init) {
      polls.push({ url, init });
      const reply = replies.shift();
      if (!reply) throw new Error("Unexpected poll");
      if (reply instanceof Error) throw reply;
      if (reply.response) return reply.response;
      if (reply.httpError) return { ok: false, status: reply.httpError };
      return { ok: true, status: 200, text: async () => JSON.stringify(reply) };
    },
  };
  vm.runInNewContext(compiled, context, { filename: "analysis.ts" });
  return {
    api: module.exports,
    uploads,
    polls,
    replies,
    timers,
    tick(ms) {
      now += ms;
      const due = [...timers].filter(([, timer]) => timer.at <= now).sort((a, b) => a[1].at - b[1].at);
      for (const [id, timer] of due) if (timers.delete(id)) timer.callback();
    },
  };
}

async function flush() { for (let i = 0; i < 8; i++) await Promise.resolve(); }

test("uploads the actual file with runtime key and polls the created job", async () => {
  const h = harness();
  const progress = [];
  const statuses = [];
  const video = file();
  h.replies.push(completed());
  const result = h.api.analyzeVideo(video, config, { onUploadProgress: p => progress.push(p), onStatus: job => statuses.push(job.status) });
  const xhr = h.uploads[0];
  assert.equal(xhr.url, "https://analysis.example.kz/api/v1/analyze");
  assert.equal(xhr.method, "POST");
  assert.equal(xhr.headers["X-API-Key"], config.apiKey);
  assert.equal(xhr.headers["Content-Type"], undefined);
  assert.equal(xhr.body.get("file").name, video.name);
  assert.equal(await xhr.body.get("file").text(), "video content");
  xhr.upload.onprogress({ lengthComputable: true, loaded: 3, total: 12 });
  xhr.respond({ job_id: "job-1", status: "processing" });
  await flush();
  assert.deepEqual(progress, [0, 25]);
  assert.equal(h.polls.length, 0);
  h.tick(1500);
  const job = await result;
  assert.equal(job.verdict, "no_violation");
  assert.equal(h.polls[0].url, "https://analysis.example.kz/api/v1/jobs/job-1");
  assert.equal(h.polls[0].init.headers["X-API-Key"], config.apiKey);
  assert.deepEqual(statuses, ["processing", "done"]);
  assert.equal(h.timers.size, 0);
});

test("a temporary GET failure reconnects and keeps the original upload", async () => {
  const h = harness(); const connections = []; const progress = [];
  h.replies.push(new TypeError("offline"), { job_id: "job-1", status: "processing", progress: 47 }, completed());
  const result = h.api.analyzeVideo(file(), config, { onConnectionChange: value => connections.push(value.state), onStatus: job => progress.push(job.progress) });
  h.uploads[0].respond({ job_id: "job-1" }); await flush();
  h.tick(1500); await flush();
  assert.equal(h.polls.length, 1); assert.deepEqual(connections, ["reconnecting"]);
  h.tick(1500); await flush();
  assert.deepEqual(connections, ["reconnecting", "connected"]);
  assert.ok(progress.includes(47));
  h.tick(1500); assert.equal((await result).status, "done");
  assert.equal(h.uploads.length, 1); assert.equal(h.polls.length, 3); assert.equal(h.timers.size, 0);
});

test("GET retries are bounded and keep a recoverable error after backoff", async () => {
  const h = harness(); const attempts = [];
  h.replies.push(...Array.from({ length: 4 }, () => ({ httpError: 503 })));
  const result = h.api.resumeAnalysis("job-1", config, { onConnectionChange: value => attempts.push(value.attempt) });
  const rejection = assert.rejects(result, error => error.code === "http" && error.httpStatus === 503 && error.retryable);
  await flush();
  for (const ms of [1500, 3000, 6000]) { h.tick(ms); await flush(); }
  await rejection;
  assert.deepEqual(attempts, [1, 2, 3]); assert.equal(h.polls.length, 4); assert.equal(h.uploads.length, 0); assert.equal(h.timers.size, 0);
});

test("resume polls the saved ID without needing a file or creating a new job", async () => {
  const h = harness(); h.replies.push(completed());
  const job = await h.api.resumeAnalysis("job-1", config);
  assert.equal(job.job_id, "job-1"); assert.equal(h.uploads.length, 0); assert.equal(h.polls.length, 1);
  assert.equal(h.polls[0].init.headers["X-API-Key"], config.apiKey);
});

test("authentication failures and malformed status responses are never automatically retried", async () => {
  for (const reply of [{ httpError: 401 }, { job_id: "different-job", status: "processing" }]) {
    const h = harness(); h.replies.push(reply);
    await assert.rejects(h.api.resumeAnalysis("job-1", config));
    assert.equal(h.polls.length, 1); assert.equal(h.uploads.length, 0); assert.equal(h.timers.size, 0);
  }
});

test("cancel during reconnect clears retries and never reuploads", async () => {
  const h = harness(); const controller = new AbortController(); h.replies.push(new TypeError("offline"));
  const result = h.api.resumeAnalysis("job-1", config, { signal: controller.signal });
  await flush(); controller.abort();
  await assert.rejects(result, { name: "AbortError" });
  assert.equal(h.timers.size, 0); assert.equal(h.polls.length, 1); assert.equal(h.uploads.length, 0);
});

test("a failed upload is not automatically submitted a second time", async () => {
  const h = harness(); const result = h.api.analyzeVideo(file(), config);
  h.uploads[0].onerror();
  await assert.rejects(result, error => error.code === "network");
  assert.equal(h.uploads.length, 1); assert.equal(h.polls.length, 0);
});

test("cancelling an upload aborts XHR and never polls", async () => {
  const h = harness();
  const controller = new AbortController();
  const result = h.api.analyzeVideo(file(), config, { signal: controller.signal });
  controller.abort();
  await assert.rejects(result, { name: "AbortError", message: "Анализ отменён." });
  assert.equal(h.uploads[0].aborted, true);
  assert.equal(h.polls.length, 0);
  assert.equal(h.timers.size, 0);
});

test("creation accepts the guaranteed job_id-only response and then polls", async () => {
  const h = harness();
  h.replies.push(completed());
  const result = h.api.analyzeVideo(file(), config);
  h.uploads[0].respond({ job_id: "job-1" });
  await flush();
  h.tick(1500);
  assert.equal((await result).verdict, "no_violation");
  assert.equal(h.polls.length, 1);
});

test("polling still requires an explicit status", async () => {
  const h = harness();
  h.replies.push({ job_id: "job-1" });
  const result = h.api.analyzeVideo(file(), config);
  h.uploads[0].respond({ job_id: "job-1" });
  await flush();
  h.tick(1500);
  await assert.rejects(result, /неизвестный статус задания/);
});

test("cancelling between polls clears the pending polling timer", async () => {
  const h = harness();
  const controller = new AbortController();
  const result = h.api.analyzeVideo(file(), config, { signal: controller.signal });
  h.uploads[0].respond({ job_id: "job-1", status: "processing" });
  await flush();
  controller.abort();
  await assert.rejects(result, { name: "AbortError" });
  h.tick(1500);
  assert.equal(h.polls.length, 0);
  assert.equal(h.timers.size, 0);
});

test("the five-minute total timeout includes a stalled upload", async () => {
  const h = harness();
  const result = h.api.analyzeVideo(file(), config);
  h.tick(300_000);
  await assert.rejects(result, /Превышено время ожидания - 5 минут/);
  assert.equal(h.uploads[0].aborted, true);
  assert.equal(h.timers.size, 0);
});

test("done without verdict and inconsistent verdict are rejected", async () => {
  for (const response of [
    { job_id: "job-1", status: "done", violations: [] },
    completed({ verdict: "violation" }),
  ]) {
    const h = harness();
    const result = h.api.analyzeVideo(file(), config);
    h.uploads[0].respond(response, 200);
    await assert.rejects(result, /некорректный результат/);
    assert.equal(h.timers.size, 0);
  }
});

test("valid evidence is preserved and a missing rule stays absent", async () => {
  const h = harness();
  const result = h.api.analyzeVideo(file(), config);
  h.uploads[0].respond(completed({ verdict: "violation", violations: [{ type: "event", timecode_sec: 12.5, description: "Observed action", evidence_frames: [{ timestamp_sec: 12.5, image_base64: png }] }] }), 200);
  const job = await result;
  assert.equal(job.violations[0].rule, undefined);
  assert.equal(h.api.evidenceDataUrl(job.violations[0].evidence_frames[0].image_base64), `data:image/png;base64,${png}`);
  assert.equal(h.api.evidenceDataUrl(`data:image/jpeg;base64,${png}`), null);
  assert.equal(h.api.evidenceDataUrl("https://untrusted.example/frame.png"), null);
});

test("source quotes and related full provisions survive response parsing", async () => {
  const h = harness(); const result = h.api.analyzeVideo(file(), config);
  const quote = "Начало пункта.\n" + "Полный текст без обрезки. ".repeat(200) + "Конец пункта.";
  const rule = {title:"Правила", section:"п. 75", quote, unit_id:"act:rules1:p75",
    path:["Глава 3", "п. 75"],source_relation:"candidate_clause",
    context:[{title:"Правила",section:"п. 2",quote:"Определение и исключение полностью."}]};
  h.uploads[0].respond(completed({verdict:"violation", violations:[{
    type:"event",timecode_sec:4,description:"Observed",evidence_frames:[],rule}]}),200);
  const received = (await result).violations[0].rule;
  assert.equal(received.quote, quote);
  assert.equal(received.path.join(" → "), "Глава 3 → п. 75");
  assert.equal(received.context[0].quote, rule.context[0].quote);
  assert.equal(received.source_relation,"candidate_clause");
});

test("server failure is surfaced without producing a completed result", async () => {
  const h = harness();
  const result = h.api.analyzeVideo(file(), config);
  h.uploads[0].respond({ job_id: "job-1", status: "failed", error: "Недостаточно памяти модели" });
  await assert.rejects(result, /Недостаточно памяти модели/);
  assert.equal(h.polls.length, 0);
});

test("public HTTP is rejected before the file is sent", async () => {
  const h = harness();
  await assert.rejects(h.api.analyzeVideo(file(), { ...config, baseUrl: "http://public.example.kz" }), /Используйте HTTPS/);
  assert.equal(h.uploads.length, 0);
});

const eventWith = frames => ({ type:"event",timecode_sec:4,description:"Keep this explanation",evidence_frames:frames.map(image_base64=>({timestamp_sec:4,image_base64})) });
const jobWith = events => completed({verdict:"violation",violations:events});
function largePng(width=1,height=1,bytes=evidence.MAX_FRAME_BYTES) {
  const buffer=Buffer.alloc(bytes); Buffer.from(png,"base64").copy(buffer);
  buffer.writeUInt32BE(width,16); buffer.writeUInt32BE(height,20); return buffer.toString("base64");
}
test("bad, unsupported, oversized and excessive-resolution frames retain the event explanation", async () => {
  for (const [image,issue] of [["data:image/svg+xml;base64,PHN2Zz4=","invalid"],["not-an-image","invalid"],[largePng(1,1,evidence.MAX_FRAME_BYTES+1),"size"],[largePng(10000,10000,100),"dimensions"]]) {
    const h=harness(); const result=h.api.analyzeVideo(file(),config); h.uploads[0].respond(jobWith([eventWith([image])]),200);
    const [event]=(await result).violations; assert.equal(event.description,"Keep this explanation"); assert.equal(event.evidence_frames[0].image_issue,issue); assert.equal(event.evidence_frames[0].image_base64,"");
  }
});
test("frame count and aggregate evidence byte limits do not discard other events", async () => {
  const h=harness(); const big=largePng(); const result=h.api.analyzeVideo(file(),config);
  h.uploads[0].respond(jobWith([eventWith([big,big,big]),eventWith([big,big]),eventWith([png,png,png,png])]),200);
  const events=(await result).violations;
  assert.equal(events.length,3); assert.equal(events[1].evidence_frames[0].image_issue,undefined); assert.equal(events[1].evidence_frames[1].image_issue,"budget");
  assert.equal(events[2].evidence_frames.length,3); assert.equal(events[2].omitted_evidence_frames,1);
});
test("an oversized POST response is aborted and is not parsed or resubmitted", async () => {
  const h=harness(); const result=h.api.analyzeVideo(file(),config);
  h.uploads[0].onprogress({loaded:h.api.MAX_API_RESPONSE_BYTES+1});
  await assert.rejects(result,error=>error.code==="invalid_response"); assert.equal(h.uploads[0].aborted,true); assert.equal(h.uploads.length,1);
});
test("a streamed GET response over the limit is canceled without retrying", async () => {
  const h=harness(); let canceled=false;
  const stream=new ReadableStream({start(controller){controller.enqueue(new Uint8Array(h.api.MAX_API_RESPONSE_BYTES+1));},cancel(){canceled=true;}});
  h.replies.push({response:new Response(stream)});
  await assert.rejects(h.api.resumeAnalysis("job-1",config),error=>error.code==="invalid_response"); assert.equal(canceled,true); assert.equal(h.polls.length,1);
});

test("connectivity signals require real validated responses, not a local resume status", async () => {
  const h=harness();let requests=0;let responses=0;
  h.replies.push(completed());const result=h.api.analyzeVideo(file(),config,{onRequest:()=>requests++,onResponse:()=>responses++});
  assert.equal(requests,1);assert.equal(responses,0);h.uploads[0].respond({job_id:"job-1"});await flush();assert.equal(responses,1);
  h.tick(1500);await result;assert.equal(requests,2);assert.equal(responses,2);
  const denied=harness();let confirmed=0;denied.replies.push({httpError:401});
  await assert.rejects(denied.api.resumeAnalysis("job-1",config,{onResponse:()=>confirmed++}));assert.equal(confirmed,0);
});

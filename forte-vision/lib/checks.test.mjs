import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";
const cache = new Map();
function load(name) {
  if (cache.has(name)) return cache.get(name).exports;
  const module = { exports: {} }; cache.set(name, module);
  const source = readFileSync(new URL(`../${name.slice(2)}.ts`, import.meta.url), "utf8");
  vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText,
    { module, exports: module.exports, require: load, URL, Error }, { filename: name });
  return module.exports;
}
const checks = load("@/lib/checks"); const { AnalysisError } = load("@/lib/analysis");
const initial = { id: "local-1", name: "cash.mov", createdAt: "2026-10-17T17:00:00Z", status: "uploading", events: 0, duration: "01:24", seconds: 84, fileBytes: 100, baseUrl: "https://analysis.example.kz", videoUrl: "blob:secret-video" };
const processing = () => checks.applyJobStatus(initial, { job_id: "server-1", status: "processing", progress: 47 });

test("the same history entry moves from upload through processing to a verified result", () => {
  const active = processing();
  assert.equal(active.id, initial.id); assert.equal(active.jobId, "server-1"); assert.equal(active.progress, 47);
  assert.equal(checks.isRunningCheck(active), true); assert.equal(checks.isFinishedCheck(active), false);
  const done = checks.applyJobStatus(active, { job_id: "server-1", status: "done", verdict: "no_violation", violations: [] });
  assert.equal(done.id, initial.id); assert.equal(checks.isFinishedCheck(done), true);
  assert.equal(done.canResume, false); assert.equal(checks.checkpointData([done]), "[]");
});

test("transport failures and canceled waiting retain a resumable job in history", () => {
  for (const [error, aborted] of [[new AnalysisError("offline", "network", true), false], [new Error("abort"), true]]) {
    const stopped = checks.stopCheck(processing(), error, aborted);
    assert.equal(stopped.status, "paused"); assert.equal(stopped.jobId, "server-1");
    assert.equal(stopped.canResume, true); assert.equal(checks.isFinishedCheck(stopped), false); assert.equal(stopped.result, undefined);
  }
});

test("server-declared failure is visible and cannot resume a terminal failed job", () => {
  const failed = checks.stopCheck(processing(), new AnalysisError("bad video", "job_failed"), false);
  assert.equal(failed.status, "failed"); assert.equal(failed.canResume, false); assert.equal(failed.error, "bad video");
  const abortedUpload = checks.stopCheck(initial, new Error("abort"), true);
  assert.equal(abortedUpload.status, "paused"); assert.equal(abortedUpload.canResume, false);
});

test("checkpoint restores only safe metadata and requires explicit resumption", () => {
  const source = { ...processing(), apiKey: "secret-key", result: { secret: "frames" }, upload: { secret: "file-bytes" } };
  const raw = checks.checkpointData([source]);
  for (const value of ["secret-key", "frames", "file-bytes", "blob:", "apiKey", "result"]) assert.ok(!raw.includes(value));
  const [restored] = checks.restoreCheckpoints(raw);
  assert.equal(restored.status, "paused"); assert.equal(restored.canResume, true); assert.equal(restored.jobId, "server-1");
  assert.equal(restored.videoUrl, undefined); assert.equal(restored.result, undefined); assert.equal(restored.seconds, 84);
});

test("untrusted, duplicate, unsafe and malformed checkpoints never start jobs", () => {
  assert.equal(checks.restoreCheckpoints("not-json").length, 0);
  const valid = JSON.parse(checks.checkpointData([processing()]))[0];
  assert.equal(checks.restoreCheckpoints(JSON.stringify([valid, valid])).length, 1);
  for (const change of [{ baseUrl: "javascript:alert(1)" }, { baseUrl: "https://user:secret@example.kz" }, { baseUrl: "https://example.kz?key=secret" }, { jobId: "" }]) {
    assert.equal(checks.restoreCheckpoints(JSON.stringify([{ ...valid, ...change }])).length, 0);
  }
});

import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import ts from "typescript";

function route() {
  const logs = [];
  const exports = {};
  const source = fs.readFileSync(new URL("./route.ts", import.meta.url), "utf8");
  vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText, {
    exports, URL, Response, TextDecoder, Uint8Array, console: { error: (...args) => logs.push(args) },
  });
  return { ...exports, logs };
}
function request(body, extraHeaders = {}, raw = false) {
  return new Request("https://forte.example/api/client-error", { method: "POST", headers: { Origin: "https://forte.example", "Content-Type": "application/json", ...extraHeaders }, body: raw ? body : JSON.stringify(body) });
}

test("client diagnostics require same origin and JSON before logging", async () => {
  const api = route();
  const missing = request({ message: "Oops" }); missing.headers.delete("Origin");
  assert.equal((await api.POST(missing)).status, 403);
  assert.equal((await api.POST(request({ message: "Oops" }, { Origin: "https://other.example" }))).status, 403);
  assert.equal((await api.POST(request({ message: "Oops" }, { "Sec-Fetch-Site": "cross-site" }))).status, 403);
  assert.equal((await api.POST(request({ message: "Oops" }, { "Content-Type": "text/plain" }))).status, 415);
  assert.equal(api.logs.length, 0);
});

test("client diagnostics bound actual streamed UTF-8 bytes and cancel oversize streams", async () => {
  const api = route();
  let canceled = false;
  let pulls = 0;
  const stream = new ReadableStream({ pull(controller) { pulls++; controller.enqueue(new Uint8Array(4000)); }, cancel() { canceled = true; } });
  const req = new Request("https://forte.example/api/client-error", { method: "POST", headers: { Origin: "https://forte.example", "Content-Type": "application/json", "Content-Length": "1" }, body: stream, duplex: "half" });
  assert.equal((await api.POST(req)).status, 413);
  assert.equal(canceled, true);
  assert.ok(pulls < 5);
  assert.equal((await api.POST(request({ message: "ж".repeat(4000) }))).status, 413);
  assert.equal(api.logs.length, 0);
});

test("client diagnostics discard malformed bodies and invalid or foreign fields", async () => {
  const api = route();
  for (const body of ["{", "null", "[]", '{"message":{}}', '{"message":""}']) assert.equal((await api.POST(request(body, {}, true))).status, 400);
  const response = await api.POST(request({ message: "Failure", name: { password: "never-log" }, secret: "never-log", source: 7, release: "build-1" }));
  assert.equal(response.status, 204);
  assert.equal(response.headers.get("Cache-Control"), "private, no-store");
  assert.deepEqual(JSON.parse(api.logs[0][1]), { release: "build-1", message: "Failure" });
});

test("client diagnostics redact credentials, emails and URL queries before bounded logging", async () => {
  const api = route();
  const response = await api.POST(request({
    release: "r".repeat(200), source: "s".repeat(200), name: "n".repeat(200),
    path: "/auth?code=private-code&email=private@example.test",
    message: 'private@example.test Bearer private-bearer password="private-password" api_key=private-api token:private-token authorization: "private-auth"',
    stack: "https://username:private-password@example.test/auth?access_token=private-query\n" + "x".repeat(3000),
  }));
  assert.equal(response.status, 204);
  assert.equal(api.logs[0][0], "forte-client-error");
  const serialized = api.logs[0][1];
  for (const secret of ["private@example.test", "private-code", "private-bearer", "private-password", "private-api", "private-token", "private-auth", "private-query"]) assert.ok(!serialized.includes(secret), secret);
  const safe = JSON.parse(serialized);
  for (const [field, bound] of Object.entries({ release: 80, source: 80, path: 120, name: 80, message: 500, stack: 2500 })) assert.ok(safe[field].length <= bound, field);
  assert.match(safe.message, /redacted/);
});

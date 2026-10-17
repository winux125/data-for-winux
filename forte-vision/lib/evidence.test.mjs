import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import test from "node:test";
import ts from "typescript";
const api={};vm.runInNewContext(ts.transpileModule(readFileSync(new URL("./evidence.ts",import.meta.url),"utf8"),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,{exports:api});
const png="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLbtAAAAABJRU5ErkJggg==";
test("raster headers, MIME and dimensions are checked before an image reaches the DOM",()=>{
  assert.ok(api.evidenceDataUrl(png));assert.equal(api.evidenceDataUrl(`data:image/jpeg;base64,${png}`),null);
  assert.equal(api.evidenceDataUrl("https://untrusted.example/image.png"),null);
  const huge=Buffer.from(png,"base64");huge.writeUInt32BE(10000,16);assert.equal(api.inspectEvidence(huge.toString("base64")).issue,"dimensions");
  assert.equal(api.inspectEvidence("iVBORw0KGgo=").issue,"invalid");
});
test("JPEG segment bounds and dimensions are validated",()=>{
  const jpeg=Buffer.from([255,216,255,192,0,8,8,0,100,0,100,1,255,217]);
  assert.ok(api.evidenceDataUrl(jpeg.toString("base64")));
  jpeg.writeUInt16BE(9000,7);assert.equal(api.inspectEvidence(jpeg.toString("base64")).issue,"dimensions");
  assert.equal(api.inspectEvidence(Buffer.from([255,216,255,192,255,255]).toString("base64")).issue,"invalid");
});

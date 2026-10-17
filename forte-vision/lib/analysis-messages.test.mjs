import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import test from 'node:test';
import vm from 'node:vm';
const ts = createRequire(import.meta.url)('typescript');
const exported = {};
vm.runInNewContext(ts.transpileModule(readFileSync(new URL('./analysis-messages.ts', import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 }
}).outputText, { exports: exported });
test('service failures explain original RAG publication gate', () => {
  const calls = [];
  const translated = exported.translateAnalysisMessage('publication_not_allowed', text => { calls.push(text); return 'translated'; });
  assert.equal(translated, 'translated');
  assert.match(calls[0], /RAG.*проверки специалистом/);
  assert.match(exported.translateAnalysisMessage('evidence_insufficient', text => text), /ручная проверка/);
});

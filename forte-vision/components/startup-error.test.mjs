import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import vm from "node:vm";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const require = createRequire(import.meta.url);
let language = "ru";
function load(name) {
  if (name === "react") return { ...React, useState: () => [language, () => {}] };
  if (name === "@/lib/client-error") return { clientErrorText: value => value || "", reportClientError() {} };
  if (!name.startsWith("@/") && !name.startsWith("./")) return require(name);
  const file = new URL(name.startsWith("@/") ? `../${name.slice(2)}.ts` : `../lib/${name.slice(2)}.ts`, import.meta.url);
  const exports = {};
  vm.runInNewContext(ts.transpileModule(readFileSync(file, "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText, { exports, require: load });
  return exports;
}
const { recoveryLocale, startupErrorCopy } = load("@/lib/startup-error");
const exports = {};
vm.runInNewContext(ts.transpileModule(readFileSync(new URL("../app/global-error.tsx", import.meta.url), "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText, { exports, require: load });

test("root recovery reads only the language preference, with blocked or malformed cookies falling back safely", () => {
  assert.equal(recoveryLocale("other=secret; forte-locale=en; test=1", "ru"), "en");
  assert.equal(recoveryLocale("forte-locale=kk-KZ"), "kk");
  assert.equal(recoveryLocale("", "en-GB"), "en");
  assert.equal(recoveryLocale("forte-locale=%XX", "kk"), "kk");
  assert.equal(recoveryLocale("forte-locale=<script>"), "ru");
});

test("the root error screen renders complete RU, KK and EN recovery controls outside locale providers", () => {
  for (language of ["ru", "kk", "en"]) {
    const copy = startupErrorCopy[language];
    const html = renderToStaticMarkup(React.createElement(exports.default, { error: new Error("") }));
    assert.ok(html.includes(`lang="${language}"`));
    for (const text of Object.values(copy)) assert.ok(html.includes(text), `${language}: ${text}`);
    assert.ok(html.includes('aria-labelledby="startup-heading"'));
    assert.ok(html.includes('tabindex="-1"'));
    assert.equal((html.match(/<button/g) || []).length, 1);
    assert.equal((html.match(/<a /g) || []).length, 1);
  }
});

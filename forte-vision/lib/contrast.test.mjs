import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import ts from "typescript";
const exports = {};
vm.runInNewContext(ts.transpileModule(readFileSync(new URL("../tests/support/contrast.ts", import.meta.url), "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText, { exports });
const { contrastRatio } = exports;

test("contrast uses linearized sRGB and an unrounded 4.5 threshold", () => {
  assert.equal(contrastRatio("#000000", "#ffffff"), 21);
  assert.equal(contrastRatio("#ffffff", "#ffffff"), 1);
  assert.ok(contrastRatio("#777777", "#ffffff") < 4.5);
  assert.ok(contrastRatio("#767676", "#ffffff") >= 4.5);
  assert.ok(Math.abs(contrastRatio("#b29ca8", "#fbf8fa") - 2.424) < 0.001);
});

test("the actual secondary-text tokens pass on plain, selected, hovered and footer surfaces in both themes", () => {
  const css = readFileSync(new URL("../app/themes.css", import.meta.url), "utf8");
  const colors = [...css.matchAll(/--theme-muted:\s*(#[a-f0-9]{6})/g)].map(match => match[1]);
  assert.equal(colors.length, 2);
  for (const background of ["#ffffff", "#fbfafb", "#fdfbfc", "#f4ecf1", "#fcf4f8", "#fcf7f9", "#fbf8fa"]) assert.ok(contrastRatio(colors[0], background) >= 4.5, `${colors[0]} on ${background}`);
  for (const background of ["#130f14", "#1c161e", "#271e28", "#402034", "#342536", "#191318"]) assert.ok(contrastRatio(colors[1], background) >= 4.5, `${colors[1]} on ${background}`);
});

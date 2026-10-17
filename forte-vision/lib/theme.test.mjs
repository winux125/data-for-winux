import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import ts from "typescript";

const source = readFileSync(new URL("./theme.ts", import.meta.url), "utf8");
const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const theme = {};
vm.runInNewContext(code, { exports: theme });

function boot(stored, systemDark, { blocked = false, media = true } = {}) {
  const classes = new Set();
  const root = { dataset: {}, style: {}, classList: { toggle(name, enabled) { if (enabled) classes.add(name); else classes.delete(name); } } };
  vm.runInNewContext(theme.themeInitScript, {
    localStorage: { getItem() { if (blocked) throw new Error("Storage blocked"); return stored; } },
    window: { matchMedia: media ? () => ({ matches: systemDark }) : undefined },
    document: { documentElement: root },
  });
  return { mode: root.dataset.theme, colorScheme: root.style.colorScheme, darkClass: classes.has("dark") };
}

test("saved dark theme is applied before hydration even on a light system", () => {
  assert.deepEqual(boot("dark", false), { mode: "dark", colorScheme: "dark", darkClass: true });
});
test("saved light theme takes precedence over a dark system", () => {
  assert.deepEqual(boot("light", true), { mode: "light", colorScheme: "light", darkClass: false });
});
test("system and invalid preferences follow system colors without unsafe values", () => {
  for (const stored of [null, "system", "invalid", "<script>"]) {
    assert.equal(boot(stored, true).mode, "dark");
    assert.equal(boot(stored, false).mode, "light");
  }
});
test("blocked storage preserves the system theme and unavailable media falls back to light", () => {
  assert.equal(boot(null, true, { blocked: true }).mode, "dark");
  assert.equal(boot(null, true, { media: false }).mode, "light");
  assert.doesNotThrow(() => vm.runInNewContext(theme.themeInitScript, {}));
});
test("preference parsing and resolved mode only return supported themes", () => {
  assert.equal(theme.parseTheme("dark"), "dark");
  assert.equal(theme.parseTheme("light"), "light");
  for (const value of [null, undefined, {}, "unsupported"]) assert.equal(theme.parseTheme(value), "system");
  assert.equal(theme.resolveTheme("system", true), "dark");
  assert.equal(theme.resolveTheme("light", true), "light");
  assert.equal(theme.resolveTheme("dark", false), "dark");
});

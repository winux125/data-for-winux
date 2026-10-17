import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";

function readTs(file) {
  const exports = {};
  vm.runInNewContext(ts.transpileModule(readFileSync(file, "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText, { exports });
  return exports;
}
const { kazakhGridStrings, kazakhTableStrings } = readTs(new URL("./react-aria-kazakh.ts", import.meta.url));
const { addKazakhTableLocale } = readTs(new URL("../build/react-aria-kazakh-plugin.ts", import.meta.url));
const require = createRequire(import.meta.url);
const heroRequire = createRequire(require.resolve("@heroui/react/package.json"));
const root = dirname(heroRequire.resolve("react-aria/package.json"));

test("Kazakh table and grid announcements cover every installed library message, including zero and user filenames", async () => {
  for (const [kind, dictionary] of [["grid", kazakhGridStrings], ["table", kazakhTableStrings]]) {
    const installed = (await import(pathToFileURL(resolve(root, `dist/private/intl/${kind}/en-US.js`)))).default;
    assert.deepEqual(Object.keys(dictionary).sort(), Object.keys(installed).sort());
    for (const value of Object.values(dictionary)) assert.ok(typeof value === "function" || value.trim());
  }
  assert.equal(kazakhGridStrings.selectedCount({ count: 0 }), "Таңдалған элементтер жоқ.");
  assert.equal(kazakhGridStrings.selectedCount({ count: 3 }), "3 элемент таңдалды.");
  assert.equal(kazakhGridStrings.selectedItem({ item: "$&.mov" }), "$&.mov таңдалды.");
});

test("the installed React Aria module shape accepts the additive Kazakh locale; unrelated modules are untouched", () => {
  for (const kind of ["grid", "table"]) {
    const file = resolve(root, `dist/private/${kind}/intlStrings.js`);
    const original = readFileSync(file, "utf8");
    const result = addKazakhTableLocale(original, file, "/test/kazakh.ts");
    assert.ok(result.includes('["kk-KZ"] = forteKazakhStrings'));
    assert.ok(result.includes(kind === "grid" ? "kazakhGridStrings" : "kazakhTableStrings"));
    assert.ok(result.includes('as default}'));
    assert.equal((result.match(/import \{ kazakh/g) || []).length, 1);
  }
  assert.equal(addKazakhTableLocale("export default {}", "/app/table.ts", "/test/kazakh.ts"), null);
  assert.throws(() => addKazakhTableLocale("export default {}", resolve(root, "dist/private/grid/intlStrings.js"), "/test/kazakh.ts"), /module changed/);
});

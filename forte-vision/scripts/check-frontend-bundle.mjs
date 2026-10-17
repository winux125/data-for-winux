import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { gzipSync } from "node:zlib";
import { resolve } from "node:path";

const client = resolve("dist/client");
const manifest = JSON.parse(readFileSync(resolve(client, ".vite/manifest.json"), "utf8"));
const rootCss = readdirSync(resolve(client, "_next/static/css")).filter(file => /^index\..*\.css$/.test(file)).map(file => `_next/static/css/${file}`);
function closure(roots) {
  const keys = new Set();
  function visit(key) {
    assert.ok(manifest[key], `Missing build entry: ${key}`);
    if (keys.has(key)) return;
    keys.add(key);
    (manifest[key].imports || []).forEach(visit);
  }
  roots.forEach(visit);
  return keys;
}
function sizes(files) {
  const result = { js: 0, css: 0, jsGzip: 0, cssGzip: 0 };
  for (const file of new Set(files)) {
    const body = readFileSync(resolve(client, file));
    const kind = file.endsWith(".css") ? "css" : "js";
    result[kind] += body.length;
    result[`${kind}Gzip`] += gzipSync(body).length;
  }
  return result;
}
const canvasKey = "components/ui/cashdesk-canvas.tsx";
assert.ok(manifest[canvasKey]?.isDynamicEntry, "The WebGL renderer must remain a dynamic entry");
const report = {};
for (const [name, component] of [["workspace", "components/forte-workspace.tsx"], ["landing", "components/forte-landing.tsx"]]) {
  const keys = closure(["virtual:vinext-app-browser-entry", "components/theme-provider.tsx", component]);
  assert.ok(!keys.has(canvasKey), `${name} eagerly loads 3D`);
  if (name === "workspace") {
    const code = [...keys].map(key => readFileSync(resolve(client, manifest[key].file), "utf8")).join("\n");
    assert.ok(code.includes("Барлық элементтер таңдалды."), "Kazakh React Aria dictionary did not reach the client bundle");
  }
  const files = [...keys].flatMap(key => [manifest[key].file, ...manifest[key].css || []]);
  report[name] = sizes([...files, ...rootCss]);
  assert.ok(report[name].js < 1200 * 1024, `${name} startup JS exceeds 1200 KiB`);
  assert.ok(report[name].css < 400 * 1024, `${name} startup CSS exceeds 400 KiB`);
}
const cssFiles = [...new Set([...rootCss, ...Object.values(manifest).flatMap(entry => entry.css || [])])];
const css = cssFiles.map(file => readFileSync(resolve(client, file), "utf8")).join("\n");
for (const selector of [".table__cell", ".button", ".checkbox__control", ".chip"]) assert.ok(css.includes(selector), `Missing used HeroUI style: ${selector}`);
for (const selector of [".date-picker__", ".calendar__", ".alert-dialog__"]) assert.ok(!css.includes(selector), `Unused HeroUI component leaked into styles: ${selector}`);
assert.ok(!css.includes("@apply"), "Uncompiled Tailwind applies remain");
report.workspaceStyles = sizes(manifest["components/forte-workspace.tsx"].css || []);
report.deferred3D = sizes([manifest[canvasKey].file]);
console.log(JSON.stringify(report, null, 2));

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";

const require = createRequire(import.meta.url);
const code = ts.transpileModule(readFileSync(new URL("./ui/cashdesk-scene.tsx", import.meta.url), "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 } }).outputText;
function harness({ reduced = false, saveData = false, observer = true, idle = true } = {}) {
  let effect, cleanup, intersect, idleFn, timerFn, enabled = false, canceled = false, disconnected = false, imported = 0;
  const exports = {};
  const window = idle ? { requestIdleCallback(fn) { idleFn = fn; return 1; }, cancelIdleCallback() { canceled = true; } } : {};
  class Observer {
    constructor(fn) { intersect = fn; }
    observe() {}
    disconnect() { disconnected = true; }
  }
  function load(name) {
    if (name === "react") return {
      lazy(loader) { return { loader }; }, Suspense: "suspense",
      useRef() { return { current: {} }; }, useState() { return [enabled, next => { enabled = next; }]; },
      useEffect(fn) { effect = fn; },
    };
    if (name === "@/components/visual-effect-boundary") return { VisualEffectBoundary: "boundary" };
    if (name === "@/lib/browser-media") return { readMediaQuery: () => ({ matches: reduced }) };
    if (name === "./cashdesk-fallback") return { default: "svg-fallback", __esModule: true };
    if (name === "./cashdesk-canvas") { imported++; return { default: "canvas", __esModule: true }; }
    return require(name);
  }
  vm.runInNewContext(code, { exports, require: load, window, navigator: { connection: { saveData } }, IntersectionObserver: observer ? Observer : undefined,
    setTimeout(fn) { timerFn = fn; return 1; }, clearTimeout() { canceled = true; },
  });
  function render() { return exports.default({}); }
  render(); cleanup = effect();
  return {
    render, get enabled() { return enabled; }, get imported() { return imported; }, get scheduled() { return Boolean(idleFn || timerFn); },
    get canceled() { return canceled; }, get disconnected() { return disconnected; },
    enter() { intersect?.([{ isIntersecting: true }]); }, leave() { intersect?.([{ isIntersecting: false }]); },
    run() { (idleFn || timerFn)?.(); }, unmount() { cleanup?.(); },
  };
}

test("optional 3D stays out of first paint and waits for both visibility and idle time", () => {
  const h = harness();
  assert.equal(h.enabled, false); assert.equal(h.imported, 0); assert.equal(h.scheduled, false);
  h.leave(); assert.equal(h.scheduled, false);
  h.enter(); assert.equal(h.scheduled, true); assert.equal(h.enabled, false); assert.equal(h.disconnected, true);
  h.run(); assert.equal(h.enabled, true);
});

test("reduced motion and data saving keep the accessible SVG without scheduling WebGL", () => {
  for (const options of [{ reduced: true }, { saveData: true }]) {
    const h = harness(options); h.enter(); h.run();
    assert.equal(h.enabled, false); assert.equal(h.imported, 0); assert.equal(h.scheduled, false);
  }
});

test("unmount cancels pending work, including late idle callbacks and timer fallbacks", () => {
  for (const options of [{}, { observer: false, idle: false }]) {
    const h = harness(options); h.enter(); assert.equal(h.scheduled, true); h.unmount(); h.run();
    assert.equal(h.canceled, true); assert.equal(h.enabled, false); assert.equal(h.imported, 0);
  }
});

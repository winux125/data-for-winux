import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import ts from "typescript";

const source = readFileSync(new URL("./opening-reveal.ts", import.meta.url), "utf8");
const config = {};
vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText, { exports: config });

function bootstrap({ path = "/", reduced = false, seen = false, blockedStorage = false, canvas = true, supports = true, media = true, visibility = "visible" } = {}) {
  const dataset = {};
  const timers = [];
  const window = {
    location: { pathname: path },
    matchMedia: media ? () => ({ matches: reduced }) : undefined,
    requestAnimationFrame() {},
    CSS: { supports() { return supports; } },
    sessionStorage: { getItem() { if (blockedStorage) throw new Error("Storage unavailable"); return seen ? "seen" : null; } },
    setTimeout(callback, ms) { timers.push({ callback, ms }); },
  };
  const document = { documentElement: { dataset }, visibilityState: visibility, createElement() { return { getContext() { return canvas ? {} : null; } }; } };
  assert.doesNotThrow(() => vm.runInNewContext(config.openingInitScript, { window, document }));
  return { dataset, timers };
}

test("the opaque SSR veil is selected synchronously before React mounts", () => {
  const state = bootstrap();
  assert.equal(state.dataset.fvIntro, "pending");
  assert.equal(state.timers.length, 1);
  assert.equal(state.timers[0].ms, config.REVEAL_FAILSAFE_MS);
  state.timers[0].callback();
  assert.equal(state.dataset.fvIntro, undefined, "failed hydration cannot leave the veil in place");
});

test("the opening is skipped for other routes, reduced motion, repeat visits and unavailable capabilities", () => {
  for (const options of [{ path: "/auth" }, { path: "/demo" }, { reduced: true }, { seen: true }, { blockedStorage: true }, { canvas: false }, { supports: false }, { media: false }, { visibility: "hidden" }]) {
    const state = bootstrap(options);
    assert.equal(state.dataset.fvIntro, undefined, JSON.stringify(options));
    assert.equal(state.timers.length, 0);
  }
  assert.doesNotThrow(() => vm.runInNewContext(config.openingInitScript, {}));
});

test("the actual reveal holds its first frame and then removes the veil and listeners", () => {
  const effects = [];
  const stateUpdates = [];
  const frames = new Map();
  const timers = new Map();
  const listeners = new Set();
  const dataset = { fvIntro: "pending" };
  const ctx = { setTransform() {}, clearRect() {}, fillText() {} };
  const panel = {};
  const veil = { style: {} };
  const canvas = { getContext() { return ctx; } };
  const skip = { contains() { return false; } };
  const refs = [panel, veil, canvas, skip];
  const session = new Map();
  let nextId = 0;
  const schedule = callback => { const id = ++nextId; frames.set(id, callback); return id; };
  const cancel = id => frames.delete(id);
  const events = { addEventListener(type, callback) { listeners.add(callback); }, removeEventListener(type, callback) { listeners.delete(callback); } };
  const window = { ...events, innerWidth: 900, innerHeight: 600, devicePixelRatio: 1, sessionStorage: { setItem(key, value) { session.set(key, value); } }, setTimeout(callback, ms) { const id = ++nextId; timers.set(id, { callback, ms }); return id; }, clearTimeout(id) { timers.delete(id); } };
  const document = { ...events, documentElement: { dataset }, visibilityState: "visible" };
  const compiled = ts.transpileModule(readFileSync(new URL("../components/site-reveal.tsx", import.meta.url), "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX } }).outputText;
  const exports = {};
  const react = { useState(value) { return [value, next => stateUpdates.push(next)]; }, useRef(value) { return { current: value === null ? refs.shift() : value }; }, useEffect(callback) { effects.push(callback); } };
  vm.runInNewContext(compiled, {
    exports, window, document, performance: { now: () => 0 }, requestAnimationFrame: schedule, cancelAnimationFrame: cancel,
    getComputedStyle() { return { color: "#a31551" }; }, MutationObserver: class { observe() {} disconnect() {} },
    require(id) {
      if (id === "react") return react;
      if (id === "react/jsx-runtime") return { jsx: (type, props) => ({ type, props }), jsxs: (type, props) => ({ type, props }) };
      if (id === "@/lib/opening-reveal") return config;
      if (id === "@/lib/browser-media") return { readMediaQuery: () => ({ matches: false }), listenMediaQuery: () => () => {} };
      if (id === "@/components/locale-provider") return { useI18n: () => ({ t: value => value }) };
      if (id === "lucide-react" || id.endsWith(".css") || id === "@/lib/messages/reveal") return {};
      throw new Error("Unexpected import " + id);
    },
  });
  const initial = exports.SiteReveal();
  assert.equal(initial.props.className, "fsr-reveal", "the veil markup is present on the first render");
  const cleanup = effects.map(effect => effect()).filter(value => typeof value === "function");
  assert.equal(session.get(config.REVEAL_SESSION_KEY), "seen");
  const tick = time => { const callbacks = [...frames.values()]; frames.clear(); callbacks.forEach(callback => callback(time)); };
  tick(config.REVEAL_HOLD_MS - 1);
  assert.equal(veil.style.clipPath, "inset(0 0 0 0%)", "the brand is held before the reveal begins");
  assert.equal(dataset.fvIntro, "pending");
  tick(config.REVEAL_HOLD_MS + config.REVEAL_TRANSITION_MS / 2);
  assert.equal(veil.style.clipPath, "inset(0 0 0 50%)");
  tick(config.REVEAL_TOTAL_MS);
  assert.equal(dataset.fvIntro, undefined);
  assert.ok(stateUpdates.includes(false));
  cleanup.forEach(callback => callback());
  assert.equal(listeners.size, 0);
  assert.equal(frames.size, 0);
  assert.equal(timers.size, 0);
});

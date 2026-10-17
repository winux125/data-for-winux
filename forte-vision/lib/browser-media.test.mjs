import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import ts from "typescript";

const source = readFileSync(new URL("./browser-media.ts", import.meta.url), "utf8");
const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;

function load(window) {
  const exports = {};
  vm.runInNewContext(code, window === undefined ? { exports } : { exports, window });
  return exports;
}

test("media query reading falls back safely without a browser or supported API", () => {
  for (const window of [undefined, {}, { matchMedia: null }, { matchMedia() { throw new Error("Unavailable"); } }]) {
    assert.equal(load(window).readMediaQuery("(prefers-color-scheme: dark)"), null);
  }
  const blockedWindow = {};
  Object.defineProperty(blockedWindow, "matchMedia", { get() { throw new Error("Blocked"); } });
  assert.equal(load(blockedWindow).readMediaQuery("(pointer: fine)"), null);
});

test("media query reading preserves a valid result and rejects invalid results", () => {
  const media = { matches: true };
  let received;
  assert.equal(load({ matchMedia(query) { received = query; return media; } }).readMediaQuery("(pointer: fine)"), media);
  assert.equal(received, "(pointer: fine)");
  for (const value of [null, undefined, {}, { matches: "yes" }]) {
    assert.equal(load({ matchMedia() { return value; } }).readMediaQuery("test"), null);
  }
});

test("modern media subscriptions use the same handler and clean up once", () => {
  const calls = [];
  const handler = () => {};
  const media = {
    addEventListener(...args) { calls.push(["add", ...args]); },
    removeEventListener(...args) { calls.push(["remove", ...args]); },
  };
  const stop = load().listenMediaQuery(media, handler);
  assert.deepEqual(calls, [["add", "change", handler]]);
  stop(); stop();
  assert.deepEqual(calls, [["add", "change", handler], ["remove", "change", handler]]);
});

test("legacy media subscriptions work without modern methods", () => {
  const calls = [];
  const handler = () => {};
  const media = {
    addListener(value) { calls.push(["add", value]); },
    removeListener(value) { calls.push(["remove", value]); },
  };
  const stop = load().listenMediaQuery(media, handler);
  stop(); stop();
  assert.deepEqual(calls, [["add", handler], ["remove", handler]]);
});

test("rejected modern registration falls back to a usable legacy subscription", () => {
  const calls = [];
  const media = {
    addEventListener() { throw new Error("Unsupported"); },
    removeEventListener() { calls.push("modern cleanup"); },
    addListener() { calls.push("legacy add"); },
    removeListener() { calls.push("legacy remove"); },
  };
  const stop = load().listenMediaQuery(media, () => {});
  stop();
  assert.deepEqual(calls, ["modern cleanup", "legacy add", "legacy remove"]);
});

test("unavailable, throwing and blocked subscriptions never escape registration or cleanup", () => {
  const api = load();
  const throwing = () => { throw new Error("Unavailable"); };
  const blocked = {};
  Object.defineProperty(blocked, "addEventListener", { get: throwing });
  Object.defineProperty(blocked, "addListener", { get: throwing });
  for (const media of [null, {}, blocked, {
    addEventListener: throwing, removeEventListener: throwing,
    addListener: throwing, removeListener: throwing,
  }, {
    addEventListener() {}, removeEventListener: throwing,
  }, {
    addListener() {}, removeListener: throwing,
  }]) {
    assert.doesNotThrow(() => { const stop = api.listenMediaQuery(media, () => {}); stop(); stop(); });
  }
});

test("the root ThemeProvider mounts and cleans up with missing, throwing or legacy media APIs", () => {
  const providerSource = readFileSync(new URL("../components/theme-provider.tsx", import.meta.url), "utf8");
  const providerCode = ts.transpileModule(providerSource, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX,
  } }).outputText;
  const themeSource = readFileSync(new URL("./theme.ts", import.meta.url), "utf8");
  const theme = {};
  vm.runInNewContext(ts.transpileModule(themeSource, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022,
  } }).outputText, { exports: theme });

  for (const kind of ["missing", "throwing", "legacy"]) {
    const effects = [];
    const updates = [];
    const subscriptions = [];
    let hookIndex = 0;
    const legacy = {
      matches: true,
      addListener(handler) { subscriptions.push(["media add", handler]); },
      removeListener(handler) { subscriptions.push(["media remove", handler]); },
    };
    const window = {
      matchMedia: kind === "missing" ? undefined : () => {
        if (kind === "throwing") throw new Error("Unavailable");
        return legacy;
      },
      addEventListener(type, handler) { subscriptions.push([type + " add", handler]); },
      removeEventListener(type, handler) { subscriptions.push([type + " remove", handler]); },
    };
    const react = {
      createContext: value => ({ Provider: "provider", value }),
      useState: value => {
        const index = hookIndex++;
        return [value, next => updates.push([index, next])];
      },
      useEffect: callback => effects.push(callback),
      useCallback: callback => callback,
      useMemo: factory => factory(),
    };
    const exports = {};
    vm.runInNewContext(providerCode, {
      exports, window, localStorage: { getItem() { return "dark"; } },
      require(id) {
        if (id === "react") return react;
        if (id === "react/jsx-runtime") return { jsx: (type, props) => ({ type, props }), jsxs: (type, props) => ({ type, props }) };
        if (id === "@/lib/browser-media") return load(window);
        if (id === "@/lib/theme") return theme;
        if (id === "@/components/session-notice") return { default: () => null };
        if (id === "@/components/locale-provider") return { LocaleProvider: ({ children }) => children };
        if (id === "lucide-react" || id === "radix-ui" || id.endsWith(".css")) return {};
        throw new Error("Unexpected import: " + id);
      },
    });
    assert.doesNotThrow(() => exports.ThemeProvider({ children: null }), kind);
    assert.equal(effects.length, 2);
    assert.doesNotThrow(() => {
      const stop = effects[0]();
      effects[1]();
      stop();
    }, kind);
    assert.deepEqual(updates, [[0, "dark"], [1, kind === "legacy"], [2, true]], kind);
    const storageAdd = subscriptions.find(([name]) => name === "storage add");
    assert.ok(storageAdd, kind);
    assert.ok(subscriptions.some(([name, handler]) => name === "storage remove" && handler === storageAdd[1]), kind);
    if (kind === "legacy") {
      const mediaAdd = subscriptions.find(([name]) => name === "media add");
      assert.ok(mediaAdd);
      assert.ok(subscriptions.some(([name, handler]) => name === "media remove" && handler === mediaAdd[1]));
    }
  }
});

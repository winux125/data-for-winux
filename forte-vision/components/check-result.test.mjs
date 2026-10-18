import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import vm from "node:vm";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const require = createRequire(import.meta.url);
const modules = new Map();
let playerOverride; let navigationOverride;
const icon = () => React.createElement("svg", { "aria-hidden": true });
function load(name) {
  if (name === "react") return { ...React, useState: initial=>React.useState(initial?.state === "loading" && playerOverride ? {...initial,state:playerOverride}:initial), useReducer:(reducer,initial)=>React.useReducer(reducer,navigationOverride?{...initial,screen:"event",eventIndex:0}:initial) };
  if (name === "@/components/locale-provider") return { useI18n: () => ({ t: (text, values = {}) => text.replace(/\{([^}]+)\}/g, (match, key) => values[key] ?? match) }) };
  if (name === "@/components/ui/cashdesk-scene") return { default: () => React.createElement("div", null, "Illustration"), __esModule: true };
  if (name === "lucide-react") return new Proxy({}, { get: () => icon });
  if (!name.startsWith("@/")) return require(name);
  if (modules.has(name)) return modules.get(name).exports;
  const filename = new URL(`../${name.slice(2)}${name.startsWith("@/components/") ? ".tsx" : ".ts"}`, import.meta.url);
  const module = { exports: {} };
  modules.set(name, module);
  const code = ts.transpileModule(readFileSync(filename, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
  }).outputText;
  vm.runInNewContext(code, { module, exports: module.exports, require: load }, { filename: filename.pathname });
  return module.exports;
}
const CheckResult = load("@/components/check-result").default;
const description = "Unique full event explanation must only appear after opening the event.";
const base = { id: "job-1", name: "cashdesk.mov", duration: "01:24", seconds: 84, videoUrl: "blob:local-recording", events: 2, status: "violation", result: { job_id: "job-1", status: "done", verdict: "violation", violations: [
  { type: "First event", timecode_sec: 22, description, evidence_frames: [] },
  { type: "Second event", timecode_sec: 47, description, evidence_frames: [] },
] } };
const render = check => renderToStaticMarkup(React.createElement(CheckResult, {
  check, onBack() {}, onExport() {}, onMetadata() {}, onExpandFrame() {},
}));

test("the initial result presents one video and clickable intervals without the event explanations", () => {
  const html = render(base);
  assert.equal((html.match(/<video\b/g) || []).length, 1);
  assert.ok(html.includes("Обнаружены признаки возможных нарушений"));
  assert.ok(html.includes("Событий для проверки: 2."));
  assert.ok(html.includes('aria-label="Событие 1: First event. Фрагмент 00:19–00:25"'));
  assert.ok(html.includes('aria-label="Событие 2: Second event. Фрагмент 00:44–00:50"'));
  assert.ok(!html.includes(description));
  assert.ok(!html.includes("Что произошло"));
});

test("a clear result opens on the video without event controls or empty event details", () => {
  const html = render({ ...base, events: 0, status: "no_violation", result: { ...base.result, verdict: "no_violation", violations: [] } });
  assert.ok(html.includes("Нарушение не обнаружено"));
  assert.equal((html.match(/<video\b/g) || []).length, 1);
  assert.ok(!html.includes('aria-label="Событие 1:'));
  assert.ok(!html.includes("Что произошло"));
});

test("unfinished, paused, reconnecting and failed checks never render a completed verdict or export", () => {
  for (const status of ["uploading", "processing", "reconnecting", "paused", "failed"]) {
    const html = render({ ...base, status, result: undefined, jobId: "job-1", canResume: status === "paused" });
    assert.ok(!html.includes("Обнаружены признаки возможных нарушений"), status);
    assert.ok(!html.includes("Нарушение не обнаружено"), status);
    assert.ok(!html.includes("Проверка завершена"), status);
    assert.ok(!html.includes("Скачать результат"), status);
    assert.ok(!html.includes("<video"), status);
    assert.ok(html.includes("job-1"));
  }
});

test("a missing or contradictory completed result is not a verdict", () => {
  for (const check of [
    { ...base, result: undefined },
    { ...base, status: "no_violation" },
    { ...base, result: { job_id: "job-1", status: "processing" } },
    { ...base, result: { job_id: "job-1", status: "done", verdict: "violation", violations: [] } },
  ]) {
    const html = render(check);
    assert.ok(html.includes("Результат недоступен"));
    assert.ok(!html.includes("Проверка завершена"));
    assert.ok(!html.includes("Скачать результат"));
  }
});

test("out-of-range times stay in the event list and never get a false end-of-video marker", () => {
  const html = render({ ...base, events: 1, result: { ...base.result, violations: [{ ...base.result.violations[0], timecode_sec: 1e9 }] } });
  assert.ok(html.includes("Есть таймкоды вне границ записи"));
  assert.ok(html.includes("Вне границ записи"));
  assert.ok(!html.includes('class="fv-timeline-marker"'));
  assert.ok(!html.includes("Фрагмент 01:21–01:24"));
});

test("unknown duration is announced and no synthetic timestamp scale is presented", () => {
  const html = render({ ...base, seconds: undefined });
  assert.ok(html.includes("Длительность записи не определена"));
  assert.ok(html.includes("Длительность неизвестна"));
  assert.ok(html.includes("Интервал не подтверждён"));
  assert.ok(!html.includes('class="fv-timeline-marker"'));
});

test("a resumed real result without the local file never displays the demo illustration", () => {
  const html = render({ ...base, videoUrl: undefined });
  assert.ok(html.includes("Исходная запись недоступна после перезагрузки"));
  assert.ok(!html.includes("Illustration"));
});

test("server progress is visible, zero is real, and absent progress stays indeterminate", () => {
  for (const value of [0,47,100]) {
    const html=render({...base,status:"processing",result:undefined,progress:value});
    assert.ok(html.includes(`Обработано ${value}%`)); assert.ok(html.includes(`aria-valuenow="${value}"`)); assert.ok(html.includes(`width:${value}%`));
  }
  const html=render({...base,status:"processing",result:undefined});
  assert.ok(html.includes("Сервер анализирует видео. Результат появится автоматически."));
  assert.ok(html.includes('role="progressbar"')); assert.ok(html.includes("fv-indeterminate"));
  assert.ok(!html.includes("aria-valuenow="));
});
test("100 intersecting events render a compact grouped marker and a complete-list control", () => {
  const html=render({...base,events:100,result:{...base.result,violations:Array(100).fill(base.result.violations[0])}});
  assert.ok(html.includes("Группа: 100 событий")); assert.ok(html.includes("Все события (100)")); assert.ok(!html.includes("4800px"));
  assert.ok(html.includes("height:48px"));
});
test("loading and failed video never advertise playable clips or native playback controls", () => {
  try {
    for (const state of ["loading","error"]) {
      playerOverride=state; const overview=render(base); assert.ok(!/<video[^>]* controls/.test(overview));
      navigationOverride=true; const event=render(base); navigationOverride=false;
      assert.ok(!event.includes("Смотреть фрагмент")); assert.ok(event.includes(state==="error"?"К кадрам и описанию":"Видео загружается…")); assert.ok(event.includes(description));
    }
  } finally { playerOverride=undefined; navigationOverride=false; }
});
test("a rejected frame renders a placeholder without losing the event explanation", () => {
  try { navigationOverride=true; playerOverride="ready";
    const html=render({...base,result:{...base.result,violations:[{...base.result.violations[0],evidence_frames:[{timestamp_sec:22,image_base64:"",image_issue:"size"}]}]}});
    assert.ok(html.includes("Кадр превышает лимит 2 МБ")); assert.ok(html.includes(description)); assert.ok(!html.includes('<img'));
  } finally { playerOverride=undefined; navigationOverride=false; }
});

test("the event renders the entire source quote, hierarchy and related exceptions as plain text", () => {
  const quote = "Начало пункта. " + "Полная строка. ".repeat(200) + "Хвост полного пункта <script>alert(1)</script>";
  try {
    navigationOverride=true;
    const rule={title:"Правила",section:"п. 75",quote,path:["Глава 3","п. 75"],
      context:[{title:"Связанный источник",section:"п. 2",quote:"Полное исключение для операции."}]};
    const html=render({...base,result:{...base.result,violations:[{...base.result.violations[0],rule}]}});
    assert.ok(html.includes("Цитата из источника"));
    assert.ok(html.includes("Глава 3 → п. 75"));
    assert.ok(html.includes("Хвост полного пункта &lt;script&gt;alert(1)&lt;/script&gt;"));
    assert.ok(html.includes("Полное исключение для операции."));
    assert.ok(!html.includes("<script>alert(1)</script>"));
    assert.ok(html.includes("Связанные положения и исключения"));
  } finally { navigationOverride=false; }
});

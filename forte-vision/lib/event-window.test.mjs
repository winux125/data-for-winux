import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";

const exports = {};
const source = readFileSync(new URL("./event-window.ts", import.meta.url), "utf8");
vm.runInNewContext(ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText, { exports });
const { getEventWindow, isKnownDuration, timecodeIssue, layoutEventWindows } = exports;
const plain = value => JSON.parse(JSON.stringify(value));

test("an event gets three seconds of review context on each side", () => {
  assert.deepEqual(plain(getEventWindow(22, 84)), { start: 19, end: 25 });
  assert.deepEqual(plain(getEventWindow(44.2, 84)), { start: 41.2, end: 47.2 });
});

test("review clips stop at the actual video boundaries, including short videos", () => {
  assert.deepEqual(plain(getEventWindow(1, 84)), { start: 0, end: 4 });
  assert.deepEqual(plain(getEventWindow(83, 84)), { start: 80, end: 84 });
  assert.deepEqual(plain(getEventWindow(0.5, 1)), { start: 0, end: 1 });
  assert.equal(getEventWindow(90, 84), null);
});

test("unknown duration never becomes an invented video length or a confirmed clip", () => {
  for (const duration of [undefined, 0, NaN, Infinity, -1]) {
    assert.equal(isKnownDuration(duration), false);
    assert.equal(getEventWindow(47, duration), null);
    assert.equal(timecodeIssue(47, duration), "unknown_duration");
    assert.deepEqual(plain(layoutEventWindows([22, 47], duration, 320)), []);
  }
  assert.equal(isKnownDuration(84), true);
});

test("invalid event and frame timestamps are never moved to the end of a video", () => {
  for (const time of [-1, NaN, Infinity, 85, 1e9]) {
    assert.equal(timecodeIssue(time, 84), "outside_video");
    assert.equal(getEventWindow(time, 84), null);
  }
  assert.equal(timecodeIssue(84, 84), null);
  assert.deepEqual(plain(getEventWindow(84, 84)), { start: 81, end: 84 });
  assert.deepEqual(plain(layoutEventWindows([1e9, 22, -1, 84], 84, 320).map(item => item.index)), [1, 3]);
});

test("well separated events share a lane and retain their original order", () => {
  const items = layoutEventWindows([47, 22], 84, 500);
  assert.deepEqual(plain(items.map(item => item.index)), [0, 1]);
  assert.equal(items[0].lane, items[1].lane);
  assert.equal(items[0].start, 44);
  assert.equal(items[1].end, 25);
});

test("overlapping events have independent selectable markers", () => {
  const items = layoutEventWindows([22, 23, 23], 84, 500);
  assert.equal(new Set(items.map(item => item.lane)).size, 3);
});

test("nearby touch targets separate into lanes even when their time windows do not overlap", () => {
  const narrow = layoutEventWindows([20, 28], 145, 220);
  const wide = layoutEventWindows([20, 28], 145, 1200);
  assert.notEqual(narrow[0].lane, narrow[1].lane);
  assert.equal(wide[0].lane, wide[1].lane);
});

test("end markers stay inside the track and interval lengths match their durations", () => {
  const width = 220;
  const items = layoutEventWindows([0, 1, 22, 28, 83, 84], 84, width);
  for (const item of items) {
    const center = item.center / 100 * width;
    assert.ok(center >= 22 && center <= width - 22);
    assert.ok(item.left >= 0 && item.left + item.width <= 100 + 1e-10);
    assert.ok(Math.abs(item.width / 100 * 84 - (item.end - item.start)) < 1e-10);
  }
});

test("one hundred overlapping events occupy at most three timeline rows without losing an index", () => {
  for (const width of [48,220,320,1200]) {
    const markers=exports.layoutTimelineMarkers(Array(100).fill(22),84,width);
    assert.equal(markers.length,1); assert.equal(markers[0].indices.length,100); assert.ok(markers.every(item=>item.lane<3));
    assert.deepEqual(plain(markers.flatMap(item=>item.indices).sort((a,b)=>a-b)),Array.from({length:100},(_,i)=>i));
  }
});
test("mixed dense and sparse markers remain bounded and preserve original event indices", () => {
  const times=[80,1,...Array(100).fill(22),45,60,1e9];
  const markers=exports.layoutTimelineMarkers(times,84,1200);
  assert.ok(markers.every(item=>item.lane<3));
  assert.deepEqual(plain(markers.flatMap(item=>item.indices).sort((a,b)=>a-b)),times.map((_,i)=>i).slice(0,-1));
  assert.ok(markers.some(item=>item.indices.length===1 && item.indices[0]===0));
});

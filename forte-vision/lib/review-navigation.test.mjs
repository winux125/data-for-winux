import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";

const exports = {};
vm.runInNewContext(ts.transpileModule(readFileSync(new URL("./review-navigation.ts", import.meta.url), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText, { exports });
const { initialReviewState: initial, reviewNavigation: move } = exports;
const plain = value => JSON.parse(JSON.stringify(value));

test("a result opens on the video without opening an event description", () => {
  assert.equal(initial.screen, "video");
  assert.equal(initial.eventIndex, null);
  assert.equal(initial.clip, null);
});

test("a marker opens its event and remembers the paused video position", () => {
  const state = move(initial, { type: "inspect", index: 1, count: 3, position: 18.75 });
  assert.deepEqual(plain(state), { screen: "event", eventIndex: 1, position: 18.75, clip: null });
});

test("back to video restores the same position and selected marker", () => {
  const event = move(initial, { type: "inspect", index: 0, count: 2, position: 21.3 });
  const video = move(event, { type: "back_to_video" });
  assert.equal(video.screen, "video");
  assert.equal(video.position, 21.3);
  assert.equal(video.eventIndex, 0);
  assert.equal(video.clip, null);
});

test("next and previous events keep the video return position", () => {
  let state = move(initial, { type: "inspect", index: 0, count: 3, position: 14 });
  state = move(state, { type: "inspect", index: 1, count: 3 });
  assert.equal(state.screen, "event");
  assert.equal(state.eventIndex, 1);
  assert.equal(state.position, 14);
  state = move(state, { type: "inspect", index: 0, count: 3 });
  assert.equal(state.eventIndex, 0);
  assert.equal(state.position, 14);
});

test("watch clip opens the recording at the interval start; whole recording clears the limit", () => {
  const event = move(initial, { type: "inspect", index: 1, count: 2, position: 10 });
  const clip = move(event, { type: "watch_clip", start: 44, end: 50 });
  assert.equal(clip.screen, "video");
  assert.equal(clip.position, 44);
  assert.deepEqual(plain(clip.clip), { start: 44, end: 50 });
  const whole = move(move(clip, { type: "time", seconds: 47 }), { type: "full_video" });
  assert.equal(whole.position, 47);
  assert.equal(whole.clip, null);
});

test("no events, invalid indices and invalid clips cannot open an empty detail screen", () => {
  for (const action of [
    { type: "inspect", index: 0, count: 0 },
    { type: "inspect", index: -1, count: 2 },
    { type: "inspect", index: 2, count: 2 },
    { type: "inspect", index: 0.5, count: 2 },
    { type: "watch_clip", start: 2, end: 5 },
  ]) assert.equal(move(initial, action), initial);
  const event = move(initial, { type: "inspect", index: 0, count: 2 });
  assert.equal(move(event, { type: "watch_clip", start: 7, end: 3 }), event);
});

test("late playback events do not change the saved position on the event screen", () => {
  const event = move(initial, { type: "inspect", index: 0, count: 2, position: 17 });
  assert.equal(move(event, { type: "time", seconds: 18 }), event);
  for (const seconds of [-1, NaN, Infinity]) assert.equal(move(initial, { type: "time", seconds }), initial);
});

import test from "node:test";
import assert from "node:assert/strict";
import { createFullscreenIdle } from "./fullscreen-idle.js";

function setup(t) {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const changes = [];
  const idle = createFullscreenIdle((visible) => changes.push(visible));
  t.after(() => idle.stop());
  return { idle, changes, tick: (ms) => t.mock.timers.tick(ms) };
}

test("fullscreen controls hide after one second and deliberate movement reveals them", (t) => {
  const { idle, changes, tick } = setup(t);
  tick(999);
  assert.deepEqual(changes, []);
  tick(1);
  assert.deepEqual(changes, [false]);
  idle.onActivity({ type: "mousemove", clientX: 20, clientY: 30 });
  assert.equal(changes.at(-1), true);
  tick(1000);
  assert.equal(changes.at(-1), false);
});

test("hover protects the bar and leaving starts a fresh full delay", (t) => {
  const { idle, changes, tick } = setup(t);
  idle.setHovered(true);
  tick(10000);
  assert.deepEqual(changes, [true]);
  idle.setHovered(false);
  tick(999);
  assert.equal(changes.at(-1), true);
  tick(1);
  assert.equal(changes.at(-1), false);
});

test("resting pointer jitter stays hidden but a click at that position reveals controls", (t) => {
  const { idle, changes, tick } = setup(t);
  idle.onActivity({ type: "mousemove", clientX: 20, clientY: 30 });
  tick(1000);
  idle.onActivity({ type: "mousemove", clientX: 21, clientY: 31 });
  assert.equal(changes.at(-1), false);
  idle.onActivity({ type: "mousedown", clientX: 21, clientY: 31 });
  assert.equal(changes.at(-1), true);
});

test("leaving fullscreen cancels pending hides and ignores stale handlers", (t) => {
  const { idle, changes, tick } = setup(t);
  idle.stop();
  idle.setHovered(false);
  idle.onActivity({ type: "mousedown" });
  tick(5000);
  assert.deepEqual(changes, []);
});

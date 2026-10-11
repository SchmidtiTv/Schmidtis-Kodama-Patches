import assert from "node:assert/strict";
import test from "node:test";
import { isMotionReduced } from "./reduced-motion.js";

test("explicit app motion settings override both OS preferences", () => {
  for (const system of [true, false]) {
    const browser = { matchMedia: () => ({ matches: system }) };
    assert.equal(isMotionReduced(browser, { dataset: { reduceMotion: "true" } }), true);
    assert.equal(isMotionReduced(browser, { dataset: { reduceMotion: "false" } }), false);
  }
});

test("motion gates fall back to the OS when app state is absent or invalid", () => {
  for (const system of [true, false]) {
    const browser = { matchMedia: () => ({ matches: system }) };
    assert.equal(isMotionReduced(browser, { dataset: {} }), system);
    assert.equal(isMotionReduced(browser, { dataset: { reduceMotion: "invalid" } }), system);
  }
  assert.equal(isMotionReduced({}, null), false);
});

import test from "node:test";
import assert from "node:assert/strict";
import { readableAccent } from "./accent.js";
test("readable accents preserve contrast and adjust unreadable colors", () => {
  assert.equal(readableAccent("#ffffff", "#000000"), "#ffffff");
  assert.notEqual(readableAccent("#111111", "#121212"), "#111111");
  assert.notEqual(readableAccent("#eeeeee", "#ffffff"), "#eeeeee");
  assert.equal(readableAccent("invalid", "#000000"), "invalid");
});

test("shorthand theme colors receive the same contrast adjustment", () => {
  assert.equal(readableAccent("#aaa", "#fff"), readableAccent("#aaaaaa", "#ffffff"));
});

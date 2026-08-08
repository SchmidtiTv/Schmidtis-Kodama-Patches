import test from "node:test";
import assert from "node:assert/strict";
import { Buffer } from "node:buffer";
import { readFile } from "node:fs/promises";
import { URL } from "node:url";

const source = await readFile(new URL("./sustained-line.js", import.meta.url), "utf8");
const sustainedLineModule = await import(
  `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`
);
const { sustainedWordScale } = sustainedLineModule;

test("does not scale a word in a line shorter than the sustained-vocal threshold", () => {
  assert.equal(sustainedWordScale({ time: 10, endTime: 13.99 }, { time: 10, end: 13 }, 12), 1);
});

test("smoothly grows only the active word in a sustained line", () => {
  const line = { time: 10, endTime: 15 };
  const word = { time: 11, end: 14 };

  assert.equal(sustainedWordScale(line, word, 11), 1);
  assert.ok(sustainedWordScale(line, word, 12.5) > 1);
  assert.equal(sustainedWordScale(line, word, 14), 1.12);
});

test("falls back to word timing when a line end time is unavailable", () => {
  const line = { time: 10, words: [{ end: 14.5 }] };

  assert.ok(sustainedWordScale(line, { time: 10, end: 14.5 }, 12) > 1);
});

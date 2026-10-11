import assert from "node:assert/strict";
import test from "node:test";
import { toBraccatoLyrics } from "./braccato-lyrics.js";
import { repeatsLine } from "./same-text.js";

test("Braccato preserves syllable timing, folds spaces, and marks background voices", () => {
  const result = toBraccatoLyrics([
    {
      time: 1.234,
      endTime: 3,
      wordSync: true,
      agentRole: "featured",
      words: [
        { text: " ", isSpace: true },
        { text: "Hello", time: 1.234, end: 2 },
        { text: " ", isSpace: true },
        { text: "world", time: 2, end: 3 },
      ],
      bgWords: [{ text: "echo", time: 2.5, end: 3 }],
    },
  ]);
  assert.equal(result[0].startTimeMs, 1234);
  assert.equal(result[0].durationMs, 1766);
  assert.equal(result[0].agent, "v2");
  assert.deepEqual(result[0].parts, [
    { startTimeMs: 1234, durationMs: 766, words: "Hello " },
    { startTimeMs: 2000, durationMs: 1000, words: "world" },
    { startTimeMs: 2500, durationMs: 500, words: "echo", isBackground: true },
  ]);
});

test("Braccato infers line duration and preserves empty instrumental lines", () => {
  const result = toBraccatoLyrics([
    { time: 2, text: "First" },
    { time: 6, text: " " },
  ]);
  assert.equal(result[0].durationMs, 4000);
  assert.equal(result[1].words, "");
  assert.equal(result[1].durationMs, 5000);
  assert.deepEqual(toBraccatoLyrics(null), []);
});

test("duplicate translations include normalized main and background vocals", () => {
  const line = { wordSync: true, words: [{ text: "Hello " }, { text: "WORLD" }], bgText: "echo" };
  assert.equal(repeatsLine(line, " hello   world "), true);
  assert.equal(repeatsLine(line, "Hello world ECHO"), true);
  assert.equal(repeatsLine(line, "Hallo Welt"), false);
  assert.equal(repeatsLine(line, ""), false);
  assert.equal(repeatsLine(null, "anything"), false);
  assert.equal(
    repeatsLine(
      { text: "Main", bgWords: [{ text: "back" }, { text: "ground" }] },
      "main background"
    ),
    true
  );
});

test("Braccato stage motion follows explicit app preferences and binds browser methods", async () => {
  const { createBraccatoMotionWindow } = await import("./braccato-motion-window.js");
  const root = { dataset: {} };
  const media = {
    matches: false,
    addEventListener() {
      assert.equal(this, media);
    },
  };
  const browser = {
    matchMedia() {
      assert.equal(this, browser);
      return media;
    },
    getComputedStyle() {
      assert.equal(this, browser);
      return "style";
    },
  };
  const adapter = createBraccatoMotionWindow(browser, root);
  const reduced = adapter.matchMedia("(prefers-reduced-motion: reduce)");
  assert.equal(reduced.matches, false);
  root.dataset.reduceMotion = "true";
  assert.equal(reduced.matches, true);
  media.matches = true;
  root.dataset.reduceMotion = "false";
  assert.equal(reduced.matches, false);
  assert.equal(adapter.matchMedia("(min-width: 100px)"), media);
  assert.equal(adapter.getComputedStyle(), "style");
  reduced.addEventListener("change", () => {});
});

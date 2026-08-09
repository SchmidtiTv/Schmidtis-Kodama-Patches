/* global Buffer, URL */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const parseSource = await readFile(new URL("./parse.js", import.meta.url), "utf8");
const { findTimestampIndex, prepareLyrics } = await import(
  `data:text/javascript;base64,${Buffer.from(parseSource).toString("base64")}`
);

test("prepareLyrics caches word render data and line timestamps", () => {
  const lines = prepareLyrics([
    {
      time: 10,
      words: [
        { text: "hel", time: 10, end: 10.2, isSpace: false },
        { text: "lo", time: 10.2, end: 10.5, isSpace: false },
        { text: " ", time: 10.5, end: 10.5, isSpace: true },
        { text: "world", time: 10.5, end: 11, isSpace: false },
      ],
    },
    { time: 20 },
  ]);

  assert.deepEqual(lines.timestamps, [10, 20]);
  assert.deepEqual(lines[0].renderTiming.mainTimestamps, [10, 10.2, 10.5]);
  assert.deepEqual(lines[0].renderTiming.mainWordGroups, [0, 0, 1]);
  assert.equal(JSON.stringify(lines).includes("renderTiming"), false);
});

test("findTimestampIndex immediately re-syncs backward and forward seeks", () => {
  const timestamps = [5, 20, 40, 75];

  assert.equal(findTimestampIndex(timestamps, 72), 2);
  assert.equal(findTimestampIndex(timestamps, 6), 0);
  assert.equal(findTimestampIndex(timestamps, 80), 3);
  assert.equal(findTimestampIndex(timestamps, 4), -1);
});

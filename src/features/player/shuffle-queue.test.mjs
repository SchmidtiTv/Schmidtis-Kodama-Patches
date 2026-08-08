import assert from "node:assert/strict";
import test from "node:test";

import { shuffleQueueAfterCurrent } from "./shuffle-queue.js";

test("shuffleQueueAfterCurrent keeps the active track first and shuffles the rest", () => {
  const queue = [{ videoId: "a" }, { videoId: "b" }, { videoId: "c" }, { videoId: "d" }];
  const random = Math.random;
  Math.random = () => 0;

  try {
    const shuffled = shuffleQueueAfterCurrent(queue, "b");
    assert.deepEqual(shuffled.map((track) => track.videoId), ["b", "c", "d", "a"]);
    assert.deepEqual(queue.map((track) => track.videoId), ["a", "b", "c", "d"]);
  } finally {
    Math.random = random;
  }
});

test("shuffleQueueAfterCurrent leaves an unrelated queue unchanged", () => {
  const queue = [{ videoId: "a" }, { videoId: "b" }];
  assert.deepEqual(shuffleQueueAfterCurrent(queue, "missing"), queue);
});

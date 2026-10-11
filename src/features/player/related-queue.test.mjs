import assert from "node:assert/strict";
import test from "node:test";
import { appendRelatedTracks, roomQueueForSelection } from "./related-queue.js";

test("related results preserve queued requests and exclude duplicate seed and related entries", () => {
  const queue = [{ videoId: "seed" }, { videoId: "request" }];
  assert.deepEqual(
    appendRelatedTracks(queue, [
      null,
      { videoId: "seed" },
      { videoId: "related" },
      { videoId: "related" },
    ]).map((track) => track.videoId),
    ["seed", "request", "related"]
  );
  assert.equal(queue.length, 2);
});

test("host single selections preserve upcoming room requests and remove the selected duplicate", () => {
  const queue = ["past", "current", "request", "selected", "later"].map((videoId) => ({ videoId }));
  assert.deepEqual(
    roomQueueForSelection({ videoId: "selected" }, queue, "current").map((track) => track.videoId),
    ["selected", "request", "later"]
  );
});

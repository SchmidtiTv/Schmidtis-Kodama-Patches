import assert from "node:assert/strict";
import test from "node:test";

import {
  buildListenerRoomQueue,
  connectionIsSilent,
  hostRoomRestorePlan,
  nextPlayedTracks,
  parseRememberedRoom,
} from "./room-session.js";

test("remembered rooms are accepted for 24 hours and normalized", () => {
  const now = 2_000_000_000_000;
  assert.deepEqual(
    parseRememberedRoom(JSON.stringify({ room: "AB12", name: "  Juniper  ", at: now - 1000 }), now),
    { room: "ab12", name: "Juniper" }
  );
  assert.equal(
    parseRememberedRoom(
      JSON.stringify({ room: "ab12", name: "Juniper", at: now - 24 * 60 * 60 * 1000 - 1 }),
      now
    ),
    null
  );
});

test("malformed remembered rooms are rejected", () => {
  const now = 2_000_000_000_000;
  for (const raw of [
    "not json",
    JSON.stringify({ room: "x", name: "Juniper", at: now }),
    JSON.stringify({ room: "../room", name: "Juniper", at: now }),
    JSON.stringify({ room: "ab12", name: "Juniper", at: "now" }),
  ]) {
    assert.equal(parseRememberedRoom(raw, now), null);
  }
});

test("only an established connection beyond the silence limit is stale", () => {
  assert.equal(connectionIsSilent(0, 20_000), false);
  assert.equal(connectionIsSilent(5_000, 20_000), false);
  assert.equal(connectionIsSilent(5_000, 20_001), true);
});

test("played history records completed transitions once and keeps the newest 50", () => {
  const previous = { videoId: "previous", title: "Previous" };
  const next = { videoId: "next", title: "Next" };
  assert.deepEqual(nextPlayedTracks([], previous, next), [previous]);
  assert.deepEqual(nextPlayedTracks([previous], previous, next), [previous]);
  assert.deepEqual(nextPlayedTracks([], previous, previous), []);

  const history = Array.from({ length: 50 }, (_, index) => ({ videoId: `old-${index}` }));
  const updated = nextPlayedTracks(history, previous, next);
  assert.equal(updated.length, 50);
  assert.equal(updated[0].videoId, "old-1");
  assert.equal(updated.at(-1), previous);
});

test("a returning host adopts the durable room track and queue", () => {
  const track = { videoId: "current" };
  const next = { videoId: "next" };
  assert.deepEqual(
    hostRoomRestorePlan({
      restoring: true,
      isHost: true,
      state: { track, playing: true, pos: 12, at: 1000, rate: 1 },
      queue: [track, next],
    }),
    {
      state: { track, playing: true, pos: 12, at: 1000, rate: 1 },
      queue: [track, next],
    }
  );
  assert.equal(hostRoomRestorePlan({ restoring: true, isHost: false, state: { track } }), null);
  assert.equal(hostRoomRestorePlan({ restoring: false, isHost: true, state: { track } }), null);
});

test("a listener queue keeps played tracks before the room's current track", () => {
  const played = [{ videoId: "played" }];
  const local = { videoId: "current", title: "Local metadata" };
  const room = { videoId: "current", title: "Room metadata" };
  const next = { videoId: "next" };
  assert.deepEqual(buildListenerRoomQueue(played, local, room, [next]), [played[0], local, next]);
  assert.deepEqual(buildListenerRoomQueue(played, null, room, [next]), [played[0], room, next]);
});

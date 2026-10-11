import assert from "node:assert/strict";
import test from "node:test";
import { roomPositionAt, clockSample, validRoomMessage, roomRole } from "./room-clock.js";

test("scheduled starts do not advance before the room clock arrives", () => {
  const state = { pos: 10, at: 5000, playing: true, rate: 1.01 };
  assert.equal(roomPositionAt(state, 4000), 10);
  assert.equal(roomPositionAt(state, 6000), 11.01);
  assert.equal(roomPositionAt({ ...state, playing: false }, 9000), 10);
});

test("clock sampling picks the fastest recent round trip and expires old readings", () => {
  const old = [{ at: 0, offset: 100, rtt: 1 }];
  const sample = clockSample(old, { c: 40000, s: 40110 }, 40020);
  assert.equal(sample.offset, 100);
  assert.equal(sample.rtt, 20);
  assert.equal(sample.samples.length, 1);
  assert.equal(clockSample([], { c: 50000, s: 50000 }, 40000), null);
});

test("room state rejects invalid positions and rates before native IPC", () => {
  const message = {
    t: "state",
    track: { videoId: "song-id" },
    pos: 0,
    at: 1000,
    rate: 1,
    playing: true,
  };
  assert.equal(validRoomMessage(message), true);
  assert.equal(validRoomMessage({ ...message, pos: -1 }), false);
  assert.equal(validRoomMessage({ ...message, rate: Infinity }), false);
  assert.equal(validRoomMessage({ ...message, track: { videoId: "../file" } }), false);
  assert.equal(validRoomMessage({ t: "queue", list: {} }), false);
});

test("host transfer overrides the previous listener role", () => {
  assert.equal(roomRole({ isHost: true, you: { role: "listener" } }), "host");
  assert.equal(roomRole({ isHost: false, you: { role: "cohost" } }), "cohost");
  assert.equal(roomRole({ isHost: false }), "listener");
});

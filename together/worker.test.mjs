import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import { Buffer } from "node:buffer";
import { URL } from "node:url";
const clone = (value) => (value == null ? value : JSON.parse(JSON.stringify(value)));

// The room protocol runs without a network. Only the Cloudflare base class is replaced;
// socket attachments and durable storage use the same interfaces as production.
const source = (await readFile(new URL("./worker.js", import.meta.url), "utf8")).replace(
  'import { DurableObject } from "cloudflare:workers";',
  "class DurableObject { constructor(ctx) { this.ctx = ctx; } }"
);
const { Room } = await import(
  `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`
);

function roomFixture() {
  const records = new Map([
    ["state", { track: null, playing: false, pos: 0, at: 0 }],
    ["hostId", "host"],
  ]);
  const sockets = [];
  const ctx = {
    id: "test-room",
    getWebSockets: () => sockets,
    storage: {
      get: async (key) => clone(records.get(key)),
      put: async (key, value) => {
        if (typeof key === "object") {
          for (const [k, v] of Object.entries(key)) records.set(k, clone(v));
        } else records.set(key, clone(value));
      },
      delete: async (key) => records.delete(key),
      deleteAlarm: async () => {},
      setAlarm: async () => {},
    },
  };
  const socket = (id, extra = {}) => {
    let attachment = { id, name: id, joined: true, ...extra };
    const messages = [];
    const ws = {
      deserializeAttachment: () => attachment,
      serializeAttachment: (value) => {
        attachment = value;
      },
      send: (message) => messages.push(JSON.parse(message)),
      close: () => {},
      messages,
    };
    sockets.push(ws);
    return ws;
  };
  return { room: new Room(ctx), records, socket };
}
const message = (room, ws, data) => room.webSocketMessage(ws, JSON.stringify(data));

test("listeners cannot change transport or forge direct queue additions", async () => {
  const { room, records, socket } = roomFixture();
  const listener = socket("listener");
  await message(room, listener, { t: "set", track: { videoId: "song" }, pos: 10, playing: true });
  assert.equal(records.get("state").track, null);
  await message(room, listener, { t: "add", track: { videoId: "song" }, mode: "next" });
  assert.deepEqual(
    listener.messages.map((entry) => entry.reason),
    ["host-only", "add-not-allowed"]
  );
});

test("explicit host transfer promotes target and demotes old host", async () => {
  const { room, records, socket } = roomFixture();
  const host = socket("host");
  socket("listener");
  await message(room, host, { t: "transfer", id: "listener" });
  assert.equal(records.get("hostId"), "listener");
  assert.equal(records.get("roles").host, "cohost");
});

test("suggestions deduplicate votes and admin acceptance becomes a host queue intent", async () => {
  const { room, socket } = roomFixture();
  const host = socket("host");
  const listener = socket("listener");
  await message(room, listener, { t: "suggest", track: { videoId: "song", title: "Song" } });
  const suggestion = (await room.suggestions())[0];
  await message(room, listener, { t: "vote", id: suggestion.id, on: true });
  assert.deepEqual((await room.suggestions())[0].votes, ["listener"]);
  await message(room, host, { t: "accept", id: suggestion.id });
  assert.equal((await room.suggestions()).length, 0);
  assert.ok(
    host.messages.some(
      (entry) => entry.t === "add" && entry.track.videoId === "song" && entry.fromId === "listener"
    )
  );
});

test("malformed and nonfinite playback messages cannot poison durable room state", async () => {
  const { room, socket, records } = roomFixture();
  const host = socket("host");
  await room.webSocketMessage(host, "null");
  await room.webSocketMessage(
    host,
    '{"t":"set","pos":1e999,"playing":true,"track":{"videoId":"song"}}'
  );
  assert.equal(records.get("state").track, null);
});

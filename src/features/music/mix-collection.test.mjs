import test from "node:test";
import assert from "node:assert/strict";
import { SYSTEM_MIX_COLLECTION_IDS, resolveMixCollectionId } from "./mix-collection.js";

test("system collections have distinct stable Mix identities", () => {
  assert.deepEqual(Object.values(SYSTEM_MIX_COLLECTION_IDS), [
    "kodama.system.liked-songs",
    "kodama.system.history",
    "kodama.system.all-songs",
  ]);
  assert.equal(new Set(Object.values(SYSTEM_MIX_COLLECTION_IDS)).size, 3);
});

test("an explicit Mix collection identity enables non-YouTube collections", () => {
  assert.equal(
    resolveMixCollectionId({
      playlistId: undefined,
      isAlbum: false,
      mixCollectionId: SYSTEM_MIX_COLLECTION_IDS.likedSongs,
    }),
    SYSTEM_MIX_COLLECTION_IDS.likedSongs
  );
});

test("ordinary playlists retain Mix while albums remain excluded", () => {
  assert.equal(resolveMixCollectionId({ playlistId: "PL123", isAlbum: false }), "PL123");
  assert.equal(resolveMixCollectionId({ playlistId: "MPREb_album", isAlbum: true }), null);
});

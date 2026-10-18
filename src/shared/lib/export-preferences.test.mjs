import test from "node:test";
import assert from "node:assert/strict";

import {
  buildExportFilename,
  joinExportPath,
  shouldRememberExportDirectory,
  storedFilenamePattern,
  withExportExtension,
} from "./export-preferences.js";

const track = { title: "Night Drive", artists: [{ name: "Kodama" }, { name: "Mori" }] };

test("buildExportFilename applies the selected naming pattern", () => {
  assert.equal(buildExportFilename(track, "mp3"), "Kodama, Mori - Night Drive.mp3");
  assert.equal(
    buildExportFilename(track, "opus", "title-artist"),
    "Night Drive - Kodama, Mori.opus"
  );
  assert.equal(buildExportFilename(track, "mp3", "title"), "Night Drive.mp3");
});

test("joinExportPath uses the directory's native-looking separator", () => {
  assert.equal(joinExportPath("/Users/music/", "track.mp3"), "/Users/music/track.mp3");
  assert.equal(joinExportPath("C:\\Music\\", "track.mp3"), "C:\\Music\\track.mp3");
  assert.equal(joinExportPath("", "track.mp3"), "track.mp3");
});

test("storage preferences retain backward-compatible defaults", () => {
  const values = new Map();
  const storage = { getItem: (key) => values.get(key) ?? null };
  assert.equal(shouldRememberExportDirectory(storage), true);
  assert.equal(storedFilenamePattern(storage), "artist-title");
  values.set("kodama-remember-export-directory", "false");
  values.set("kodama-export-filename-pattern", "invalid");
  assert.equal(shouldRememberExportDirectory(storage), false);
  assert.equal(storedFilenamePattern(storage), "artist-title");
});

test("withExportExtension adds the format's extension only when it is missing", () => {
  assert.equal(withExportExtension("/home/u/song", "mp3"), "/home/u/song.mp3");
  assert.equal(withExportExtension("/home/u/song.MP3", "mp3"), "/home/u/song.MP3");
  assert.equal(withExportExtension("/home/u/song", "opus"), "/home/u/song.opus");
  assert.equal(withExportExtension("C:\\Music\\song.webm", "opus"), "C:\\Music\\song.webm");
});

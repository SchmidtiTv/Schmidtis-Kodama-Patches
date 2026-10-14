import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";
import { URL } from "node:url";

const read = (name) => JSON.parse(fs.readFileSync(new URL(name, import.meta.url), "utf8"));

test("upstream locale additions retain fork-only translations", () => {
  const french = read("fr-FR.json");
  assert.equal(french.removeFromQueue, "Retirer de la file d’attente");
  assert.equal(typeof french.bigPictureMode, "string");
});

test("language metadata credits translators and gates incomplete locales", () => {
  const languages = read("languages.json");
  const byCode = Object.fromEntries(languages.map((language) => [language.code, language]));
  assert.deepEqual(byCode["fr-FR"].translators, ["Felzow47", "Anokino"]);
  assert.equal(byCode.tok.comingSoon, true);
  assert.equal(byCode["pt-PT"].comingSoon, true);
  assert.equal(byCode["he-IL"].comingSoon, true);
});

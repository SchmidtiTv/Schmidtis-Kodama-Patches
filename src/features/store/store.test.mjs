import assert from "node:assert/strict";
import test, { beforeEach } from "node:test";
import { parseStoreLink } from "./web.js";
import { addFromLink } from "./link-install.js";
import { CATALOGUE_URL } from "./catalogue.js";
import {
  installPreset,
  installedPresets,
  uninstallPreset,
  readVisualizerPresets,
} from "./presets.js";
import { loadEqualizerState, saveEqualizerState } from "../player/equalizer.js";
import { cleanVisualizerConfig } from "../visualizer/config.js";
import {
  compareCatalogueVersions,
  supportsCatalogueEntry,
} from "../../shared/lib/catalogue-version.js";

beforeEach(() => {
  const data = new Map();
  globalThis.localStorage = {
    getItem: (key) => data.get(key) ?? null,
    setItem: (key, value) => data.set(key, value),
  };
  globalThis.window = new globalThis.EventTarget();
  globalThis.__APP_VERSION__ = "1.0.0-alpha.39";
});

test("store links accept only known categories and a plain catalogue id", () => {
  assert.deepEqual(parseStoreLink("kodama://store/visualizer/soft-curve/"), {
    kind: "visualizer",
    id: "soft-curve",
  });
  for (const value of [
    "https://kodama.kiyoshi.dev/store/themes/foo",
    "kodama://store/themes/../foo",
    "kodama://store/themes/foo?url=https://evil.invalid",
    "kodama://store/themes/foo#bar",
    "kodama://store/unknown/foo",
    "kodama://store/themes/%66oo",
    "kodama://store/themes/a/b",
  ])
    assert.equal(parseStoreLink(value), null, value);
});

test("links install only data found in the official catalogue", async () => {
  const requested = [];
  globalThis.fetch = async (url) => {
    requested.push(url);
    return {
      ok: true,
      json: async () => ({
        schema: 1,
        themes: [
          {
            id: "test-theme",
            title: "Test",
            version: "1.0.0",
            tokens: { "--accent": "#123456", "--bad": "url(https://evil.invalid)" },
          },
        ],
        visualizer: [],
      }),
    };
  };
  assert.equal((await addFromLink("kodama://store/themes/test-theme")).status, "installed");
  assert.deepEqual(requested, [CATALOGUE_URL]);
  const themes = JSON.parse(globalThis.localStorage.getItem("kodama-installed-themes"));
  assert.deepEqual(themes[0].tokens, { "--accent": "#123456" });
  assert.equal((await addFromLink({ kind: "themes", id: "missing" })).status, "missing");
  assert.equal((await addFromLink({ kind: "themes", id: "test-theme" })).status, "already");
});

test("executable extension and widget links give an explicit unsupported result without fetching", async () => {
  globalThis.fetch = () => {
    throw new Error("Unsupported code must not be fetched");
  };
  for (const kind of ["extensions", "widgets"])
    assert.equal((await addFromLink({ kind, id: "composer" })).status, "unsupported");
});

test("minimum versions and unknown catalogue schemas block installs", async () => {
  globalThis.fetch = async () => ({
    ok: true,
    json: async () => ({
      schema: 1,
      themes: [{ id: "future", minVersion: "1.0.0-alpha.40", tokens: { "--accent": "#fff" } }],
    }),
  });
  assert.equal((await addFromLink({ kind: "themes", id: "future" })).status, "needsNewer");
  globalThis.fetch = async () => ({ ok: true, json: async () => ({ schema: 2, themes: [] }) });
  assert.equal((await addFromLink({ kind: "themes", id: "future" })).status, "failed");
  assert.equal(compareCatalogueVersions("1.0.0-alpha.9", "1.0.0-alpha.39"), -1);
  assert.equal(compareCatalogueVersions("1.0.0", "1.0.0-alpha.39"), 1);
  assert.equal(supportsCatalogueEntry({ minVersion: "garbage" }, "1.0.0"), false);
});

test("equalizer preset updates replace old versions and preserve the active selection", () => {
  assert.equal(
    installPreset("equalizer", {
      id: "speech",
      version: "1.0.0",
      config: { preamp: -100, gains: [99, -99, "3", "bad"] },
    }),
    true
  );
  let state = loadEqualizerState();
  assert.deepEqual(state.custom[0].gainsDb, [12, -12, 3, 0, 0, 0, 0, 0, 0, 0]);
  assert.equal(state.custom[0].preampDb, -12);
  saveEqualizerState({ ...state, enabled: true, presetId: state.custom[0].id });
  installPreset("equalizer", {
    id: "speech",
    version: "2.0.0",
    config: { gains: [2], preamp: -2 },
  });
  state = loadEqualizerState();
  assert.equal(state.custom.length, 1);
  assert.equal(state.presetId, "store:speech@2.0.0");
  assert.equal(state.gainsDb[0], 2);
  assert.deepEqual(installedPresets("equalizer"), [{ id: "speech", version: "2.0.0" }]);
  uninstallPreset("equalizer", "speech");
  assert.equal(loadEqualizerState().presetId, "default");
  assert.deepEqual(loadEqualizerState().gainsDb, Array(10).fill(0));
});

test("visualizer data accepts known safe types and clamps numeric settings", () => {
  const config = cleanVisualizerConfig({
    shape: "ring",
    coverShape: "circle",
    barCount: 100000,
    responsiveness: -10,
    customColor: "url(https://evil.invalid)",
    blobs: "false",
    unknown: 1,
  });
  assert.deepEqual(config, {
    shape: "ring",
    barCount: 160,
    responsiveness: 0,
    coverShape: "circle",
  });
  assert.equal(installPreset("visualizer", { id: "round", version: "1.0.0", config }), true);
  assert.equal(readVisualizerPresets()[0].config.coverShape, "circle");
  uninstallPreset("visualizer", "round");
  assert.deepEqual(readVisualizerPresets(), []);
});

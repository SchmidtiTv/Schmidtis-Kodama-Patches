import test from "node:test";
import assert from "node:assert/strict";
import { applyTheme, readTheme } from "./theme.js";

test("OLED and custom dark themes select HeroUI's dark tokens; light removes them", (t) => {
  const attributes = new Map();
  const classes = new Set();
  const styles = new Map();
  const previous = globalThis.document;
  globalThis.document = {
    getElementById: (id) => styles.get(id),
    createElement: () => ({}),
    head: { appendChild: (style) => styles.set(style.id, style) },
    documentElement: {
      setAttribute: (key, value) => attributes.set(key, value),
      classList: { toggle: (name, enabled) => enabled ? classes.add(name) : classes.delete(name) },
    },
  };
  t.after(() => { globalThis.document = previous; });
  for (const theme of ["dark", "oled", "custom-dark"]) {
    applyTheme(theme);
    assert.equal(attributes.get("data-theme"), theme);
    assert.equal(classes.has("dark"), true);
  }
  applyTheme("oled");
  assert.match(styles.get("kodama-theme-vars").textContent, /--bg-base/);
  applyTheme("light");
  assert.equal(attributes.get("data-theme"), "light");
  assert.equal(classes.has("dark"), false);
  applyTheme(null);
  assert.equal(attributes.get("data-theme"), "dark");
});

test("themes use a constructed stylesheet when CSP blocks runtime style elements", (t) => {
  const previousDocument = globalThis.document;
  const previousStyleSheet = globalThis.CSSStyleSheet;
  class TestStyleSheet {
    replaceSync(css) {
      this.css = css;
    }
  }
  globalThis.CSSStyleSheet = TestStyleSheet;
  globalThis.document = {
    adoptedStyleSheets: [],
    documentElement: {
      setAttribute() {},
      classList: { toggle() {} },
    },
  };
  t.after(() => {
    globalThis.document = previousDocument;
    globalThis.CSSStyleSheet = previousStyleSheet;
  });
  applyTheme("oled");
  assert.equal(globalThis.document.adoptedStyleSheets.length, 1);
  assert.match(globalThis.document.adoptedStyleSheets[0].css, /--bg-base/);
});

test("standalone windows use dark when stored theme access fails", (t) => {
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, "localStorage");
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: { getItem() { throw new Error("storage unavailable"); } },
  });
  t.after(() => {
    if (descriptor) Object.defineProperty(globalThis, "localStorage", descriptor);
    else delete globalThis.localStorage;
  });
  assert.equal(readTheme(), "dark");
});

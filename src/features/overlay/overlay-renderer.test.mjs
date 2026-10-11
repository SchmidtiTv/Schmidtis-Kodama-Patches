import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import { URL } from "node:url";

const html = readFileSync(
  new URL("../../../python-backend/static/overlay.html", import.meta.url),
  "utf8"
);
const functions = [
  "coverChannels",
  "rgba",
  "visFills",
  "visStrokes",
  "topFillColor",
  "gradStops",
  "paintCss",
];
const source = functions
  .map((name) => {
    const match = html.match(new RegExp(`function ${name}\\([^]*?\\n}`));
    assert.ok(match, `renderer exports ${name}`);
    return match[0];
  })
  .join("\n");
const renderer = vm.runInNewContext(`${source}\n({visFills,visStrokes,topFillColor,paintCss})`);

test("legacy paints render while explicitly emptied lists stay empty", () => {
  assert.equal(renderer.visFills({ fill: "#123456" }).length, 1);
  assert.equal(renderer.visFills({ fill: "#123456", fills: [] }).length, 0);
  assert.equal(renderer.visStrokes({ border: { on: true, color: "#123456" } }).length, 1);
  assert.equal(
    renderer.visStrokes({ border: { on: true, color: "#123456" }, strokes: [] }).length,
    0
  );
  assert.equal(renderer.topFillColor({ color: "#123456" }, "#123456"), "#123456");
  assert.equal(renderer.topFillColor({ color: "#123456", fills: [] }, "#123456"), "transparent");
  assert.equal(
    renderer.topFillColor({ fills: [{ color: "#123456", visible: false }] }, "#123456"),
    "transparent"
  );
});

test("gradient stops preserve cover bindings and multiply both paint opacities", () => {
  const paint = renderer.paintCss({
    type: "linear",
    angle: 45,
    opacity: 50,
    stops: [
      { color: "cover:2:dark", opacity: 50, pos: 0 },
      { color: "#ffffff", pos: 100 },
    ],
  });
  assert.ok(paint.startsWith("linear-gradient(45deg,"));
  assert.ok(paint.includes("var(--cv2r) * .42"));
  assert.ok(paint.includes(",0.25) 0%"));
  assert.ok(paint.includes("rgba(255,255,255,0.5) 100%"));
});

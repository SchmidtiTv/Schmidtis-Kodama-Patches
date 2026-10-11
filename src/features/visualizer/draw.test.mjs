import assert from "node:assert/strict";
import test from "node:test";
import { drawSpectrum } from "./draw.js";
import { VIZ_DEFAULTS } from "./defaults.js";

function recordingCanvas() {
  const calls = [];
  const context = { calls };
  for (const name of [
    "beginPath",
    "moveTo",
    "lineTo",
    "quadraticCurveTo",
    "closePath",
    "stroke",
    "fill",
  ]) {
    context[name] = (...args) => calls.push([name, ...args]);
  }
  return context;
}
function draw(context, config) {
  drawSpectrum(context, {
    w: 600,
    h: 480,
    box: { x: 200, y: 100, w: 200, h: 200 },
    cfg: { ...VIZ_DEFAULTS, ...config },
    n: 8,
    vals: [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8],
    baseCol: "#ff0000",
  });
}

test("frame curve presets draw a closed smooth curve instead of bars", () => {
  const context = recordingCanvas();
  draw(context, { shape: "frame", render: "curve" });
  assert.equal(context.calls.filter(([name]) => name === "quadraticCurveTo").length, 8);
  assert.equal(context.calls.filter(([name]) => name === "closePath").length, 1);
  assert.equal(context.calls.filter(([name]) => name === "stroke").length, 1);
  assert.equal(context.globalAlpha, 1);
});

test("linear mirror reflects bars around the cover center", () => {
  const context = recordingCanvas();
  draw(context, { shape: "linear", linearPos: "center", mirror: true, barCap: "square" });
  const starts = context.calls.filter(([name]) => name === "moveTo");
  const ends = context.calls.filter(([name]) => name === "lineTo");
  for (let i = 0; i < starts.length; i++) assert.equal((starts[i][2] + ends[i][2]) / 2, 200);
  assert.equal(context.lineCap, "square");
});

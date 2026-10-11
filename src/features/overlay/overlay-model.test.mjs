import test from "node:test";
import assert from "node:assert/strict";
import { defaultCanvas, makeShapeLayer, makeShaderLayer, normalizeOverlayDoc } from "./schema.js";
import { groupLayers, membersOf, cloneLayers, ungroupLayers } from "./groups.js";
import { makeElement, placeElement } from "./elements.js";
import { copyProps, pasteProps } from "./style-clipboard.js";
import { measure } from "./measure.js";

const document = () => ({
  version: 2,
  canvas: defaultCanvas(),
  layers: [
    makeShapeLayer({ id: "a", x: 10, y: 20, z: 0 }),
    makeShapeLayer({ id: "b", x: 110, y: 20, z: 1 }),
  ],
});

test("group cloning preserves membership and ungrouping preserves layers", () => {
  const { doc, gid } = groupLayers(document(), ["a", "b"], "Pair");
  assert.equal(membersOf(doc, gid).length, 2);
  let n = 0;
  const copy = cloneLayers(doc, doc.layers, { makeLayerId: () => `copy_${++n}` });
  assert.equal(copy.clones.length, 2);
  assert.equal(new Set([...doc.layers, ...copy.clones].map((l) => l.id)).size, 4);
  assert.notEqual(copy.clones[0].group, gid);
  assert.equal(
    ungroupLayers(doc, [gid]).layers.some((l) => l.group),
    false
  );
});

test("reusable elements place independent layers at requested center", () => {
  const doc = document();
  const element = makeElement(doc, ["a", "b"], "Pair", "Basic");
  let n = 0;
  const result = placeElement(doc, element, { x: 400, y: 200 }, () => `placed_${++n}`);
  assert.equal(result.ids.length, 2);
  const placed = result.doc.layers.filter((l) => result.ids.includes(l.id));
  assert.equal(Math.min(...placed.map((l) => l.x)), 310);
  assert.equal(Math.min(...placed.map((l) => l.y)), 160);
  placed[0].style.fill = "#000000";
  assert.notEqual(element.layers[0].style.fill, "#000000");
});

test("style clipboard transfers paint without moving the destination", () => {
  const doc = document();
  doc.layers[0].style.fills[0].color = "#123456";
  const result = pasteProps(doc, ["b"], copyProps(doc, ["a"]), "colors");
  assert.equal(result.layers[1].style.fills[0].color, "#123456");
  assert.equal(result.layers[1].x, 110);
});

test("legacy shader cover colors migrate and shaders have reactive defaults", () => {
  const layer = makeShaderLayer();
  layer.style.coverColors = true;
  const result = normalizeOverlayDoc({ ...document(), layers: [layer] });
  assert.deepEqual(result.layers[0].style.shaderColors, ["cover:1", "cover:2", "cover:3"]);
  assert.equal(result.layers[0].style.reactive, false);
});

test("distance measurement reports horizontal gap", () => {
  assert.ok(
    measure({ x: 0, y: 0, w: 20, h: 20 }, { x: 30, y: 0, w: 20, h: 20 }).some((s) => s.value === 10)
  );
});

test("saved v1 layouts migrate without losing text or progress bindings", () => {
  const doc = normalizeOverlayDoc({
    widgetWidth: 500,
    artSize: 60,
    textColor: "#123456",
    showAlbum: true,
  });
  assert.equal(doc.version, 2);
  assert.equal(doc.canvas.width, 500);
  assert.equal(doc.layers.find((l) => l.bind === "title").style.color, "#123456");
  assert.deepEqual(doc.layers.find((l) => l.bind === "subtitle").style.parts, ["artist", "album"]);
  assert.equal(doc.layers.find((l) => l.type === "progress").bind, "progress");
});

test("saved v2 groups and legacy paints survive normalization", () => {
  const stored = {
    version: 2,
    canvas: { width: 320, height: 100 },
    groups: [{ id: "g", name: "Pair" }],
    layers: [
      {
        id: "old",
        type: "shape",
        group: "g",
        style: { fill: "#123456", border: { on: true, color: "#abcdef", width: 4 } },
      },
    ],
  };
  const doc = normalizeOverlayDoc(stored);
  assert.deepEqual(doc.groups, stored.groups);
  assert.equal(doc.layers[0].group, "g");
  assert.equal(doc.layers[0].style.fills[0].color, "#123456");
  assert.equal(doc.layers[0].style.strokes[0].color, "#abcdef");
  assert.equal(doc.layers[0].style.strokeWeight, 4);
  assert.equal(doc.canvas.entranceOn, "track");
});

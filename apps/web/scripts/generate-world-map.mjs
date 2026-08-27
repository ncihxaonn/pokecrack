import { writeFileSync } from "node:fs";
import { resolve } from "node:path";

import DottedMap from "dotted-map";

const map = new DottedMap({
  height: 72,
  grid: "diagonal",
  projection: { name: "equirectangular" },
});

const svg = map.getSVG({
  radius: 0.2,
  color: "#cbd2dc",
  shape: "circle",
  backgroundColor: "transparent",
});
const output = svg.replace(/^[ \t]+$/gm, "").trimEnd();

writeFileSync(resolve(import.meta.dirname, "../public/world-map-dots.svg"), `${output}\n`);

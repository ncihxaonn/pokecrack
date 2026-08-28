import { createHash } from "node:crypto";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const appDirectory = resolve(scriptDirectory, "..");
const defaultOutput = resolve(appDirectory, "src/data/world-map-110m.json");
const isoCodesPath = resolve(appDirectory, "src/data/iso-alpha2.json");

const source = {
  name: "Natural Earth Admin 0 Countries and Tiny Countries",
  version: "5.1.1",
  projection: "Equal Earth",
  scale: "1:110m",
  boundaryModel: "de facto",
  license: "Public domain",
  countriesUrl: "https://naturalearth.s3.amazonaws.com/5.1.1/110m_cultural/ne_110m_admin_0_countries.zip",
  tinyCountriesUrl: "https://naturalearth.s3.amazonaws.com/5.1.1/110m_cultural/ne_110m_admin_0_tiny_countries.zip",
  termsUrl: "https://www.naturalearthdata.com/about/terms-of-use/",
  countriesShpSha256: "08e341606e8391e458c3f08deb312de664b56bfae376064c5aa0aee6681a5f55",
  tinyCountriesShpSha256: "78be45ef82045e529f8805737699b71b517458a5a76ff8d5f26caad782408e61",
  mapshaperVersion: "0.7.55",
  simplification: "90% weighted-visvalingam keep-shapes",
};

function argument(name) {
  const index = process.argv.indexOf(name);
  return index === -1 ? null : process.argv[index + 1] ?? null;
}

function digest(value) {
  return createHash("sha256").update(value).digest("hex");
}

function decodeAttribute(value) {
  return value
    .replaceAll("&quot;", '"')
    .replaceAll("&apos;", "'")
    .replaceAll("&lt;", "<")
    .replaceAll("&gt;", ">")
    .replaceAll("&amp;", "&")
    .replace(/&#(\d+);/g, (_, code) => String.fromCodePoint(Number(code)));
}

function attribute(attributes, name) {
  const match = attributes.match(new RegExp(`\\b${name}="([^"]*)"`));
  return match ? decodeAttribute(match[1]) : null;
}

function runMapshaper(countriesPath, tinyCountriesPath, svgPath) {
  const result = spawnSync(
    "npx",
    [
      "--yes",
      `mapshaper@${source.mapshaperVersion}`,
      "-i",
      countriesPath,
      tinyCountriesPath,
      "combine-files",
      "-proj",
      "eqearth",
      "densify",
      "target=*",
      "-target",
      "ne_110m_admin_0_countries",
      "-simplify",
      "90%",
      "keep-shapes",
      "-filter-fields",
      "ISO_A2_EH,NAME_EN",
      "-rename-fields",
      "country_code=ISO_A2_EH,country_name=NAME_EN",
      "-style",
      "fill=#f8f9fb",
      "stroke=#d5dae3",
      "stroke-width=0.5",
      "-target",
      "ne_110m_admin_0_tiny_countries",
      "-filter-fields",
      "ISO_A2_EH,NAME_EN",
      "-rename-fields",
      "country_code=ISO_A2_EH,country_name=NAME_EN",
      "-style",
      "fill=#7b8492",
      "stroke=#ffffff",
      "stroke-width=0.5",
      "r=2",
      "-o",
      "format=svg",
      "target=*",
      "svg-data=country_code,country_name",
      "precision=0.1",
      "width=1000",
      svgPath,
    ],
    { encoding: "utf8" },
  );
  if (result.status !== 0) {
    throw new Error(result.stderr || result.stdout || "mapshaper failed");
  }
}

async function verifyShapefile(path, expected, label) {
  const bytes = await readFile(path);
  const actual = digest(bytes);
  if (actual !== expected) {
    throw new Error(`${label} SHA-256 mismatch: expected ${expected}, received ${actual}`);
  }
}

async function generate() {
  const outputPath = resolve(argument("--output") ?? defaultOutput);
  const providedSvg = argument("--svg");
  const countriesPath = argument("--countries-shp");
  const tinyCountriesPath = argument("--tiny-shp");
  const isoCodes = new Set(JSON.parse(await readFile(isoCodesPath, "utf8")));
  let temporaryDirectory = null;
  let svgPath;

  if (providedSvg) {
    svgPath = resolve(providedSvg);
  } else {
    if (!countriesPath || !tinyCountriesPath) {
      throw new Error(
        "Pass --svg, or both --countries-shp and --tiny-shp from Natural Earth 5.1.1.",
      );
    }
    await verifyShapefile(
      resolve(countriesPath),
      source.countriesShpSha256,
      "Admin 0 Countries",
    );
    await verifyShapefile(
      resolve(tinyCountriesPath),
      source.tinyCountriesShpSha256,
      "Admin 0 Tiny Countries",
    );
    temporaryDirectory = await mkdtemp(resolve(tmpdir(), "pokecrack-world-map-"));
    svgPath = resolve(temporaryDirectory, "world.svg");
    runMapshaper(resolve(countriesPath), resolve(tinyCountriesPath), svgPath);
  }

  try {
    const svg = await readFile(svgPath, "utf8");
    const viewBox = svg.match(/\bviewBox="([^"]+)"/)?.[1];
    if (!viewBox) throw new Error("Generated SVG has no viewBox");

    const countries = [];
    const tinyCountries = [];
    for (const match of svg.matchAll(/<(path|circle)\b([^>]*)\/>/g)) {
      const [, element, attributes] = match;
      const rawCode = attribute(attributes, "data-country_code");
      const countryName = attribute(attributes, "data-country_name");
      if (!countryName) continue;
      const countryCode = rawCode && isoCodes.has(rawCode) ? rawCode : null;

      if (element === "path") {
        const path = attribute(attributes, "d");
        if (!path) throw new Error(`Missing path data for ${countryName}`);
        countries.push({ countryCode, countryName, path });
      } else {
        const x = Number(attribute(attributes, "cx"));
        const y = Number(attribute(attributes, "cy"));
        if (!Number.isFinite(x) || !Number.isFinite(y)) {
          throw new Error(`Invalid tiny-country point for ${countryName}`);
        }
        tinyCountries.push({ countryCode, countryName, x, y });
      }
    }

    if (countries.length !== 177 || tinyCountries.length !== 37) {
      throw new Error(
        `Unexpected feature count: ${countries.length} countries, ${tinyCountries.length} tiny points`,
      );
    }

    const payload = {
      source,
      viewBox,
      countries,
      tinyCountries,
    };
    await writeFile(outputPath, `${JSON.stringify(payload)}\n`, { mode: 0o644 });
    process.stdout.write(`Generated ${outputPath}\n`);
  } finally {
    if (temporaryDirectory) {
      await rm(temporaryDirectory, { recursive: true, force: true });
    }
  }
}

await generate();

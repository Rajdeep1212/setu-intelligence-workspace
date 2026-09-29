// Builds the offline data bundle for Roadside Mode from data/traffic_offences.
//
//   node scripts/roadside-bundle.mjs          write src/data/roadside-bundle.json
//   node scripts/roadside-bundle.mjs --check  exit 1 if the committed bundle is stale
//
// The output is deterministic (no build timestamps), so the committed file only
// changes when the source tables change. The frontend is built on its own
// (for example on Vercel), so the generated file is committed.
import { createHash } from "node:crypto";
import { readFileSync, readdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
export const DATA_DIR = path.resolve(here, "..", "..", "data", "traffic_offences");
export const BUNDLE_PATH = path.resolve(here, "..", "src", "data", "roadside-bundle.json");
export const BUNDLE_SCHEMA = "setu.roadside-bundle/v1";

export function readTables(dataDir = DATA_DIR) {
  return readdirSync(dataDir)
    .filter((name) => name.endsWith(".json") && name !== "schema.json")
    .sort()
    .map((name) => JSON.parse(readFileSync(path.join(dataDir, name), "utf8")))
    .sort((a, b) => a.jurisdiction.localeCompare(b.jurisdiction));
}

export function buildBundle(dataDir = DATA_DIR) {
  const tables = readTables(dataDir);
  if (tables.length === 0) throw new Error(`No offence tables found in ${dataDir}`);
  const validAsOf = tables.map((table) => table.retrieved_at).sort().at(-1);
  const sha256 = createHash("sha256").update(JSON.stringify(tables)).digest("hex");
  return { schema: BUNDLE_SCHEMA, valid_as_of: validAsOf, sha256, tables };
}

export function serialize(bundle) {
  return `${JSON.stringify(bundle, null, 2)}\n`;
}

function main(argv) {
  const expected = serialize(buildBundle());
  if (argv.includes("--check")) {
    let current = "";
    try {
      current = readFileSync(BUNDLE_PATH, "utf8");
    } catch {
      current = "";
    }
    if (current !== expected) {
      console.error("Roadside bundle is stale. Run: npm run roadside:bundle");
      return 1;
    }
    console.log("Roadside bundle is up to date.");
    return 0;
  }
  writeFileSync(BUNDLE_PATH, expected);
  console.log(`Wrote ${path.relative(process.cwd(), BUNDLE_PATH)}`);
  return 0;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exitCode = main(process.argv.slice(2));
}

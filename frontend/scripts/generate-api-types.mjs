// Regenerate src/api/schema.ts from the backend's OpenAPI document: `npm run gen:api`.
//
// The document is dumped by the backend rather than fetched over HTTP, so this needs no running server, no UDP
// port and no game. `f1telemetry/openapi.py` merges the /ws/live message models into it, because a WebSocket
// has no place in an OpenAPI document and the frontend still needs those types.
//
// Run it after any change to a response shape. CI does not run it; tests in tests/test_openapi.py fail when a
// payload stops matching its declared model, which is the drift this file exists to catch.

import { spawnSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import openapiTS, { astToString } from "openapi-typescript";

const FRONTEND = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const REPO = resolve(FRONTEND, "..");
const OUTPUT = resolve(FRONTEND, "src/api/schema.ts");

const HEADER = `/**
 * Generated from the backend's OpenAPI document. Do not edit by hand.
 *
 * Run \`npm run gen:api\` after changing a response shape in f1telemetry/schemas.py.
 */
`;

function dumpSchema() {
  const result = spawnSync("uv", ["run", "python", "-m", "f1telemetry.openapi"], {
    cwd: REPO,
    encoding: "utf8",
    maxBuffer: 32 * 1024 * 1024,
    shell: process.platform === "win32",
  });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(`dumping the OpenAPI document failed (exit ${result.status}):\n${result.stderr}`);
  }
  return JSON.parse(result.stdout);
}

const ast = await openapiTS(dumpSchema(), { alphabetize: true });
mkdirSync(dirname(OUTPUT), { recursive: true });
writeFileSync(OUTPUT, HEADER + astToString(ast), "utf8");
console.log(`wrote ${OUTPUT}`);

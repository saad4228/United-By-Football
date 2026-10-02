/**
 * Regenerate the frontend's API types from the backend.
 *
 *   backend/scripts/dump_openapi.py  ->  frontend/openapi.json  ->  src/lib/api-schema.ts
 *
 * Run it after changing anything the API returns. CI runs it too and fails if the result
 * differs from what's committed, so the two sides can't drift apart unnoticed.
 *
 * openapi-typescript runs through npx rather than as a dependency, and that is deliberate: it
 * builds its output with the TypeScript compiler's AST factory, which only exists in
 * TypeScript 5. Installed locally it would resolve to this project's TypeScript 7 and die on
 * `ts.factory` being undefined. npx gives it an isolated tree with the version it needs.
 */
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../..", import.meta.url));
const backend = join(root, "backend");
const frontend = join(root, "frontend");
const windows = process.platform === "win32";

// An absolute path, so the shell never has to resolve it (cmd.exe rejects forward slashes).
const venv = join(backend, ".venv", windows ? "Scripts/python.exe" : "bin/python");
const python = process.env.UBF_PYTHON ?? (existsSync(venv) ? venv : "python");

function run(cmd, args, cwd) {
  // No shell: arguments stay separate rather than being concatenated into a command line.
  const r = spawnSync(cmd, args, { cwd, stdio: "inherit" });
  if (r.error) {
    console.error(`\nCould not run ${cmd}: ${r.error.message}`);
    process.exit(1);
  }
  if (r.status !== 0) {
    console.error(`\n${cmd} failed (exit ${r.status}).`);
    process.exit(r.status ?? 1);
  }
}

function runShell(command, cwd) {
  const r = spawnSync(command, { cwd, stdio: "inherit", shell: true });
  if (r.status !== 0) {
    console.error(`
${command} failed (exit ${r.status}).`);
    process.exit(r.status ?? 1);
  }
}

run(python, [join("scripts", "dump_openapi.py")], backend);
// A single fixed command string: shell-quoting is not a concern because nothing here comes
// from outside, and passing one string avoids Node's array-with-shell deprecation.
runShell("npx -y openapi-typescript@7 openapi.json -o src/lib/api-schema.ts", frontend);
console.log("API types regenerated.");

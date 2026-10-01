// Starts the backend for the browser tests: demo mode (synthetic fixtures and sources, no
// network), a throwaway database, and the built frontend (run `npm run build` first).
import { spawn } from "node:child_process";
import { rmSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const backend = fileURLToPath(new URL("../../backend/", import.meta.url));
const port = process.env.E2E_PORT ?? "8010";
const python = process.env.UBF_PYTHON ?? (process.platform === "win32" ? ".venv/Scripts/python.exe" : ".venv/bin/python");

for (const file of ["e2e.db", "e2e.db-wal", "e2e.db-shm"]) rmSync(join(backend, file), { force: true });

const child = spawn(python, ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", port], {
  cwd: backend,
  stdio: "inherit",
  env: {
    ...process.env,
    UBF_DEMO_MODE: "true",
    UBF_ESPN_ENABLED: "false",
    UBF_MEDIA_ENABLED: "false",
    UBF_YOUTUBE_API_KEY: "",
    UBF_DATABASE_URL: "sqlite+aiosqlite:///./e2e.db",
    UBF_PUBLIC_BASE_URL: `http://127.0.0.1:${port}`,
    UBF_ADMIN_TOKEN: "e2e-admin",
    // Every test browser shares one IP; production limits would throttle a parallel run.
    UBF_RATE_LIMIT_MATCHES: "100000",
    UBF_RATE_LIMIT_SOURCES: "100000",
    UBF_RATE_LIMIT_SEARCH: "100000",
  },
});

for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => child.kill(signal));
child.on("exit", (code) => process.exit(code ?? 0));

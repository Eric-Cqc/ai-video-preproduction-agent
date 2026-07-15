// @vitest-environment node

import { spawn } from "node:child_process";
import { once } from "node:events";
import { createServer } from "node:net";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { fetchApiHealth } from "../src/lib/api/health-client";

async function reservePort(): Promise<number> {
  const server = createServer();
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  const address = server.address();
  if (!address || typeof address === "string") {
    server.close();
    throw new Error("Unable to allocate a local integration port");
  }
  const port = address.port;
  server.close();
  await once(server, "close");
  return port;
}

async function waitForApi(url: URL, errorOutput: () => string): Promise<void> {
  const deadline = Date.now() + 10_000;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(new URL("/api/v1/health", url));
      if (response.ok) return;
    } catch {
      // The local process may still be binding its socket.
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error(`Local API did not become ready: ${errorOutput()}`);
}

describe("Web-to-API health boundary", () => {
  it("accepts the live API response through the Web client", async () => {
    const repositoryRoot = path.resolve(process.cwd(), "../..");
    const port = await reservePort();
    const apiBaseUrl = new URL(`http://127.0.0.1:${port}`);
    let stderr = "";
    const api = spawn(
      path.join(repositoryRoot, ".venv/bin/python"),
      [
        "-m",
        "uvicorn",
        "services.api.app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        String(port),
        "--log-level",
        "warning",
      ],
      {
        cwd: repositoryRoot,
        env: {
          ...process.env,
          APP_ENVIRONMENT: "integration",
          PYTHONPATH: [
            repositoryRoot,
            path.join(repositoryRoot, "packages/contracts/python"),
            path.join(repositoryRoot, "packages/model-registry"),
          ].join(path.delimiter),
        },
        stdio: ["ignore", "ignore", "pipe"],
      },
    );
    api.stderr.on("data", (chunk: Buffer) => {
      stderr += chunk.toString();
    });

    try {
      await waitForApi(apiBaseUrl, () => stderr);
      const result = await fetchApiHealth(apiBaseUrl);
      expect(result.state).toBe("available");
      if (result.state === "available") {
        expect(result.health.service).toBe("foundation-api");
        expect(result.health.contract_version).toBe("1.0.0");
      }
    } finally {
      api.kill("SIGTERM");
      await Promise.race([
        once(api, "exit"),
        new Promise((resolve) => setTimeout(resolve, 2_000)),
      ]);
    }
  }, 20_000);
});

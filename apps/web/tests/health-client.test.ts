import { describe, expect, it } from "vitest";

import validHealth from "../../../packages/test-fixtures/health/valid-health.json";
import { fetchApiHealth } from "../src/lib/api/health-client";

const baseUrl = new URL("http://api.test");

describe("fetchApiHealth", () => {
  it("accepts a valid API health response", async () => {
    const fetcher = async () => Response.json(validHealth);
    await expect(fetchApiHealth(baseUrl, fetcher)).resolves.toEqual({
      state: "available",
      health: validHealth,
    });
  });

  it("reports an unavailable API", async () => {
    const fetcher = async () => {
      throw new TypeError("connection refused");
    };
    await expect(fetchApiHealth(baseUrl, fetcher)).resolves.toEqual({
      state: "unavailable",
      message: "API is unavailable",
    });
  });

  it("rejects an invalid API health response", async () => {
    const fetcher = async () => Response.json({ status: "ok" });
    await expect(fetchApiHealth(baseUrl, fetcher)).resolves.toEqual({
      state: "unavailable",
      message: "API returned an invalid health response",
    });
  });
});

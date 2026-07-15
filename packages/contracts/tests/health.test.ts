import { describe, expect, it } from "vitest";

import validHealth from "../../test-fixtures/health/valid-health.json";
import invalidHealth from "../../test-fixtures/health/invalid-health.json";
import {
  HEALTH_CONTRACT_VERSION,
  HealthContractError,
  parseHealthResponse,
} from "../src/health.js";

describe("health contract v1", () => {
  it("accepts the deterministic valid fixture", () => {
    expect(parseHealthResponse(validHealth)).toEqual(validHealth);
  });

  it("rejects the invalid fixture", () => {
    expect(() => parseHealthResponse(invalidHealth)).toThrow(
      HealthContractError,
    );
  });

  it("enforces the contract version", () => {
    expect(() =>
      parseHealthResponse({ ...validHealth, contract_version: "2.0.0" }),
    ).toThrow(HealthContractError);
    expect(HEALTH_CONTRACT_VERSION).toBe("1.0.0");
  });
});

import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import {
  STRUCTURED_BRIEF_SCHEMA_VERSION,
  StructuredBriefContractError,
  parseStructuredBrief,
} from "../src/structured-brief.js";

const fixtures = path.resolve(process.cwd(), "../test-fixtures/brief");

function fixture(name: string): unknown {
  return JSON.parse(readFileSync(path.join(fixtures, name), "utf8"));
}

describe("Structured Brief contract v1", () => {
  it.each([
    "valid-structured-brief-v1.json",
    "incomplete-structured-brief-v1.json",
  ])("accepts fixture %s", (name) => {
    expect(parseStructuredBrief(fixture(name))).toEqual(fixture(name));
  });

  it.each(["invalid-unknown-field.json", "invalid-schema-version.json"])(
    "rejects fixture %s",
    (name) => {
      expect(() => parseStructuredBrief(fixture(name))).toThrow(
        StructuredBriefContractError,
      );
    },
  );

  it("enforces schema version", () => {
    expect(STRUCTURED_BRIEF_SCHEMA_VERSION).toBe("1.0.0");
  });
});

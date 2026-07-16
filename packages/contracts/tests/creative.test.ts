import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import {
  CreativeContractError,
  parseCreativeContent,
} from "../src/creative.js";

const fixtures = path.resolve(process.cwd(), "../test-fixtures/creative");

function fixture(name: string): unknown {
  return JSON.parse(readFileSync(path.join(fixtures, name), "utf8"));
}

describe("Creative contracts v1", () => {
  it("accepts the canonical concept fixture", () => {
    expect(
      parseCreativeContent("concept", fixture("valid-concept-v1.json")),
    ).toEqual(fixture("valid-concept-v1.json"));
  });

  it.each([
    ["script", "valid-script-v1.json"],
    ["storyboard", "valid-storyboard-v1.json"],
    ["shotPlan", "valid-shot-plan-v1.json"],
  ] as const)("accepts canonical %s content", (kind, name) => {
    expect(parseCreativeContent(kind, fixture(name))).toEqual(fixture(name));
  });

  it("rejects invalid and unknown concept fields", () => {
    expect(() =>
      parseCreativeContent("concept", fixture("invalid-concept-v1.json")),
    ).toThrow(CreativeContractError);
    const valid = fixture("valid-concept-v1.json") as Record<string, unknown>;
    expect(() =>
      parseCreativeContent("concept", { ...valid, internal: true }),
    ).toThrow(CreativeContractError);
  });
});

import { describe, expect, it } from "vitest";

import {
  demoWorkflowSummary,
  deterministicDemoWorkflow,
} from "../src/lib/demo-workflow";

describe("deterministic local demo workflow", () => {
  it("has the complete approved-predecessor production sequence", () => {
    expect(deterministicDemoWorkflow.map((artifact) => artifact.stage)).toEqual(
      [
        "Intake",
        "Brief",
        "Concepts",
        "Script",
        "Storyboard",
        "Shot Plan",
        "Review",
        "Delivery",
      ],
    );
    expect(deterministicDemoWorkflow.at(-1)).toMatchObject({
      state: "delivered",
    });
    expect(demoWorkflowSummary()).toContain("Delivery: Delivery package v1");
  });
});

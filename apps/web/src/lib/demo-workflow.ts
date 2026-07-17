export interface DemoArtifact {
  readonly stage: string;
  readonly title: string;
  readonly version: number;
  readonly state: "approved" | "ready" | "delivered";
}

/**
 * Non-secret deterministic fixture for the local product walkthrough.  It is
 * intentionally data, not a provider response or a source of production truth.
 */
export const deterministicDemoWorkflow: readonly DemoArtifact[] = Object.freeze(
  [
    {
      stage: "Intake",
      title: "Campaign source record",
      version: 1,
      state: "approved",
    },
    { stage: "Brief", title: "Launch brief", version: 1, state: "approved" },
    {
      stage: "Concepts",
      title: "Concept selection",
      version: 1,
      state: "approved",
    },
    {
      stage: "Script",
      title: "Narrative script",
      version: 1,
      state: "approved",
    },
    { stage: "Storyboard", title: "Storyboard", version: 1, state: "ready" },
    { stage: "Shot Plan", title: "Shot plan", version: 1, state: "ready" },
    {
      stage: "Review",
      title: "Planning review",
      version: 1,
      state: "approved",
    },
    {
      stage: "Delivery",
      title: "Delivery package",
      version: 1,
      state: "delivered",
    },
  ],
);

export function demoWorkflowSummary(): string {
  return deterministicDemoWorkflow
    .map(
      (artifact) => `${artifact.stage}: ${artifact.title} v${artifact.version}`,
    )
    .join("\n");
}

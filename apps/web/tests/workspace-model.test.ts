import { describe, expect, it } from "vitest";

import type { WorkspaceSnapshot } from "../src/lib/workspace-model";
import {
  nextActionableStage,
  stageStatus,
  stageStatuses,
  withWorkspacePatch,
} from "../src/lib/workspace-model";

function baseSnapshot(): WorkspaceSnapshot {
  return {
    project: {
      id: "project-1",
      name: "Film",
      description: null,
      status: "draft",
      version: 1,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    },
    artifacts: {},
    sourceAssets: [],
    sourceAsset: undefined,
    sourceObject: undefined,
    extraction: undefined,
    briefRun: undefined,
    candidate: undefined,
    briefCandidateAvailable: undefined,
    candidateReview: undefined,
    brief: undefined,
    conceptRun: undefined,
    concepts: [],
    script: undefined,
    storyboardRun: undefined,
    storyboard: undefined,
    shotPlanRun: undefined,
    shotPlan: undefined,
    reviews: [],
    review: undefined,
    revisionRequest: undefined,
    deliveryPackage: undefined,
    exports: [],
    hydrationIssues: [],
    errors: {},
    activeOperation: null,
    hasSourceFile: false,
  };
}

describe("workspace stage state machine", () => {
  it("moves through truthful predecessor states without inferring gates", () => {
    let snapshot = baseSnapshot();
    expect(stageStatus(snapshot, "upload")).toBe("available");
    expect(stageStatus(snapshot, "parse")).toBe("blocked");

    snapshot = withWorkspacePatch(snapshot, {
      sourceObject: {
        id: "object-1",
        source_asset_id: "asset-1",
        source_asset_version_id: "version-1",
        state: "available",
        observed_byte_size: 12,
        created_at: "2026-01-01T00:00:00Z",
      },
    });
    expect(stageStatuses(snapshot)).toMatchObject({
      upload: "done",
      parse: "available",
      brief: "blocked",
    });

    snapshot = withWorkspacePatch(snapshot, {
      extraction: {
        id: "extraction-1",
        source_asset_id: "asset-1",
        source_asset_version_id: "version-1",
        parser_id: "deterministic",
        parser_version: "1",
        status: "processing",
        extracted_document: {},
        character_count: 0,
        warning_count: 0,
        truncated: false,
        created_at: "2026-01-01T00:00:00Z",
        schema_version: "1",
      },
    });
    expect(stageStatus(snapshot, "parse")).toBe("pending");

    snapshot = withWorkspacePatch(snapshot, {
      extraction: { ...snapshot.extraction!, status: "failed" },
      briefCandidateAvailable: false,
    });
    expect(stageStatus(snapshot, "parse")).toBe("failed");
    expect(nextActionableStage(snapshot)).toBe("parse");

    snapshot = withWorkspacePatch(snapshot, {
      extraction: { ...snapshot.extraction!, status: "completed" },
      candidate: {
        run_id: "run-1",
        candidate: { objective: {} },
        candidate_issues: [],
      },
      briefCandidateAvailable: true,
    });
    expect(stageStatuses(snapshot)).toMatchObject({
      parse: "done",
      brief: "available",
      concepts: "blocked",
    });

    snapshot = withWorkspacePatch(snapshot, {
      brief: {} as WorkspaceSnapshot["brief"],
      concepts: [
        {
          id: "concept-1",
          candidate_index: 0,
          content: {},
          created_at: "2026-01-01T00:00:00Z",
        },
      ],
    });
    expect(stageStatus(snapshot, "concepts")).toBe("available");
    expect(stageStatus(snapshot, "script")).toBe("blocked");

    snapshot = withWorkspacePatch(snapshot, {
      artifacts: { selectedConceptCandidateId: "concept-1" },
      conceptRun: {
        id: "concept-run-1",
        status: "completed",
        brief_id: "brief-1",
        brief_version_id: "brief-version-1",
        created_at: "2026-01-01T00:00:00Z",
        completed_at: "2026-01-01T00:00:00Z",
      },
    });
    expect(stageStatuses(snapshot)).toMatchObject({
      concepts: "done",
      script: "available",
    });

    snapshot = withWorkspacePatch(snapshot, {
      script: {} as WorkspaceSnapshot["script"],
      storyboard: {} as WorkspaceSnapshot["storyboard"],
      shotPlan: {} as WorkspaceSnapshot["shotPlan"],
    });
    expect(stageStatus(snapshot, "review")).toBe("available");

    snapshot = withWorkspacePatch(snapshot, {
      review: { outcome: "approved" } as WorkspaceSnapshot["review"],
    });
    expect(stageStatuses(snapshot)).toMatchObject({
      review: "done",
      delivery: "available",
    });

    snapshot = withWorkspacePatch(snapshot, {
      deliveryPackage: {} as WorkspaceSnapshot["deliveryPackage"],
      exports: [],
    });
    expect(stageStatus(snapshot, "delivery")).toBe("available");

    snapshot = withWorkspacePatch(snapshot, {
      exports: [
        {
          id: "export-without-checksum",
          format: "delivery-package.zip",
          filename: "package.zip",
          checksum: "",
          byte_size: 10,
          created_at: "2026-01-01T00:00:00Z",
        },
      ],
    });
    expect(stageStatus(snapshot, "delivery")).toBe("available");

    snapshot = withWorkspacePatch(snapshot, {
      exports: [
        {
          id: "export-1",
          format: "delivery-package.zip",
          filename: "package.zip",
          checksum: "sha256:known",
          byte_size: 10,
          created_at: "2026-01-01T00:00:00Z",
        },
      ],
    });
    expect(stageStatus(snapshot, "delivery")).toBe("done");
  });

  it("keeps a failed stage failed and does not mark later gates complete", () => {
    const snapshot = withWorkspacePatch(baseSnapshot(), {
      errors: { brief: new Error("candidate rejected") },
      briefCandidateAvailable: false,
    });
    expect(stageStatuses(snapshot)).toMatchObject({
      brief: "failed",
      concepts: "blocked",
      delivery: "blocked",
    });
  });
});

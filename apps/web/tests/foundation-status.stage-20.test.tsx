import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Project } from "../src/lib/api/product-client";
import {
  artifactStorageKey,
  operationStorageKey,
  writeResumeOperationKeys,
} from "../src/lib/api/product-client";
import { FoundationStatus } from "../src/components/foundation-status";

const context = {
  actorSubject: "local-user",
  organizationId: "org-1",
  workspaceId: "workspace-1",
};

const projects: Project[] = [
  {
    id: "project-a",
    name: "Alpha",
    description: "First project",
    status: "draft",
    version: 1,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "project-b",
    name: "Beta",
    description: "Second project",
    status: "draft",
    version: 1,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

function emptyHydrationResponse(url: URL): Response {
  if (url.pathname.endsWith("/source-assets")) {
    return Response.json({ items: [], limit: 50, offset: 0 });
  }
  if (url.pathname.endsWith("/briefs")) return Response.json({ items: [] });
  if (url.pathname.endsWith("/planning-reviews"))
    return Response.json({ items: [] });
  const project = projects.find((item) =>
    url.pathname.endsWith(`/projects/${item.id}`),
  );
  if (project) return Response.json(project);
  return Response.json({ items: [] });
}

function mockWorkspaceFetch(mutations: string[]) {
  return vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input, init) => {
      const url = new URL(input instanceof Request ? input.url : String(input));
      const method =
        init?.method ?? (input instanceof Request ? input.method : "GET");
      if (method !== "GET") mutations.push(`${method} ${url.pathname}`);
      if (url.pathname.endsWith("/projects"))
        return Response.json({ items: projects });
      return emptyHydrationResponse(url);
    });
}

function renderWithStoredContext() {
  window.localStorage.setItem(
    "production-desk-context",
    JSON.stringify(context),
  );
  return render(
    <FoundationStatus
      environment="test"
      api={{ state: "unavailable", message: "mocked" }}
      apiBaseUrl="http://api.test"
    />,
  );
}

function mockRevisionWorkspaceFetch(
  mode: "cancel" | "complete",
  requests: string[],
) {
  let revisionStatus = "open";
  const review = {
    id: "review-1",
    artifact_type: "planning_bundle",
    script_version_id: "script-1",
    storyboard_version_id: "storyboard-1",
    shot_plan_version_id: "shot-1",
    review_round: 1,
    outcome: "revision_requested",
    summary: "当前规划包需要修改。",
    requested_changes: { reason: "补充第二场的动作连续性。" },
    reviewed_by_actor_subject: "local-user",
    reviewed_at: "2026-01-01T00:00:00Z",
    created_at: "2026-01-01T00:00:00Z",
  };
  const revision = () => ({
    id: "revision-1",
    review_id: "review-1",
    artifact_type: "planning_bundle",
    source_script_version_id: "script-1",
    source_storyboard_version_id: "storyboard-1",
    source_shot_plan_version_id: "shot-1",
    status: revisionStatus,
    created_at: "2026-01-01T00:00:00Z",
    completed_at:
      revisionStatus === "completed" ? "2026-01-01T00:01:00Z" : null,
    successor_script_version_id:
      revisionStatus === "completed" ? "script-2" : null,
    successor_storyboard_version_id:
      revisionStatus === "completed" ? "storyboard-2" : null,
    successor_shot_plan_version_id:
      revisionStatus === "completed" ? "shot-2" : null,
  });
  const sourceAsset = {
    id: "asset-1",
    organization_id: "org-1",
    workspace_id: "workspace-1",
    project_id: "project-a",
    display_name: "brief.json",
    status: "ready",
    current_version_id: "asset-version-1",
    latest_version_number: 1,
    created_by_actor_subject: "local-user",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    version: 1,
  };
  const sourceVersion = {
    id: "asset-version-1",
    organization_id: "org-1",
    workspace_id: "workspace-1",
    project_id: "project-a",
    source_asset_id: "asset-1",
    version_number: 1,
    original_filename: "brief.json",
    media_type: "application/json",
    byte_size: 2,
    checksum_algorithm: "sha256",
    checksum_value: "checksum",
    source_type: "api_declared",
    source_reference: null,
    external_record_id: null,
    declared_created_at: null,
    created_by_actor_subject: "local-user",
    created_at: "2026-01-01T00:00:00Z",
    supersedes_version_id: null,
    metadata_schema_version: "1",
  };
  const extraction = {
    id: "extraction-1",
    source_asset_id: "asset-1",
    source_asset_version_id: "asset-version-1",
    parser_id: "deterministic",
    parser_version: "1",
    status: "completed",
    extracted_document: {},
    character_count: 2,
    warning_count: 0,
    truncated: false,
    created_at: "2026-01-01T00:00:00Z",
    schema_version: "1",
  };
  const brief = {
    brief: {
      id: "brief-1",
      organization_id: "org-1",
      workspace_id: "workspace-1",
      project_id: "project-a",
      title: "Brief",
      status: "active",
      current_version_id: "brief-version-1",
      latest_version_number: 1,
      created_by_actor_subject: "local-user",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
      version: 1,
    },
    current_version: {
      id: "brief-version-1",
      organization_id: "org-1",
      workspace_id: "workspace-1",
      project_id: "project-a",
      brief_id: "brief-1",
      version_number: 1,
      lifecycle_state: "accepted",
      structured_content: {},
      source_type: "human_review",
      source_reference: null,
      change_summary: "accepted",
      created_by_actor_subject: "local-user",
      created_at: "2026-01-01T00:00:00Z",
      submitted_for_review_at: null,
      approved_at: null,
      approved_by_actor_subject: null,
      supersedes_version_id: null,
      content_schema_version: "1",
    },
    issues: [],
  };
  const conceptRun = {
    id: "concept-run-1",
    status: "completed",
    brief_id: "brief-1",
    brief_version_id: "brief-version-1",
    created_at: "2026-01-01T00:00:00Z",
    completed_at: "2026-01-01T00:00:00Z",
  };
  const concept = {
    id: "concept-1",
    candidate_index: 0,
    content: { title: "Concept" },
    created_at: "2026-01-01T00:00:00Z",
  };
  const makeScript = (id: string) => ({
    id,
    content: { title: id },
    brief_version_id: "brief-version-1",
    concept_candidate_id: "concept-1",
    concept_selection_id: "selection-1",
  });
  const makePlanningVersion = (id: string) => ({
    id,
    storyboard_run_id: "storyboard-run-1",
    storyboard_version_id: id,
    shot_plan_run_id: "shot-plan-run-1",
    brief_id: "brief-1",
    brief_version_id: "brief-version-1",
    concept_run_id: "concept-run-1",
    concept_candidate_id: "concept-1",
    concept_selection_id: "selection-1",
    script_run_id: "script-run-1",
    script_version_id: id === "storyboard-1" ? "script-1" : "script-2",
    version_number: id === "storyboard-1" ? 1 : 2,
    schema_version: "1",
    content: { scenes: [] },
    total_duration_seconds: 10,
    scene_count: 0,
    shot_count: 0,
    created_at: "2026-01-01T00:00:00Z",
  });

  return vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input, init) => {
      const url = new URL(input instanceof Request ? input.url : String(input));
      const method =
        init?.method ?? (input instanceof Request ? input.method : "GET");
      requests.push(`${method} ${url.pathname}`);
      if (method === "POST" && url.pathname.endsWith("/cancel")) {
        revisionStatus = "cancelled";
        return Response.json({ revision_request: revision() });
      }
      if (method === "POST" && url.pathname.endsWith("/complete")) {
        revisionStatus = "completed";
        return Response.json({
          revision_request: revision(),
          successor_script_version_id: "script-2",
          successor_storyboard_version_id: "storyboard-2",
          successor_shot_plan_version_id: "shot-2",
          replayed: false,
        });
      }
      if (url.pathname.endsWith("/projects"))
        return Response.json({ items: projects });
      if (url.pathname.endsWith("/projects/project-a"))
        return Response.json(projects[0]);
      if (url.pathname.endsWith("/projects/project-a/source-assets"))
        return Response.json({ items: [sourceAsset], limit: 50, offset: 0 });
      if (url.pathname.endsWith("/source-assets/asset-1"))
        return Response.json({
          source_asset: sourceAsset,
          current_version: sourceVersion,
        });
      if (url.pathname.endsWith("/versions/asset-version-1/object"))
        return Response.json({
          id: "object-1",
          source_asset_id: "asset-1",
          source_asset_version_id: "asset-version-1",
          state: "available",
          observed_byte_size: 2,
          created_at: "2026-01-01T00:00:00Z",
        });
      if (url.pathname.endsWith("/extractions/extraction-1"))
        return Response.json(extraction);
      if (url.pathname.endsWith("/brief-extraction-runs/run-1"))
        return Response.json({
          id: "run-1",
          status: "completed",
          created_at: "2026-01-01T00:00:00Z",
        });
      if (url.pathname.endsWith("/brief-extraction-runs/run-1/candidate"))
        return Response.json({
          run_id: "run-1",
          candidate: {},
          candidate_issues: [],
        });
      if (url.pathname.endsWith("/briefs"))
        return Response.json({
          items: [
            {
              ...brief.brief,
            },
          ],
        });
      if (url.pathname.endsWith("/briefs/brief-1")) return Response.json(brief);
      if (url.pathname.endsWith("/concept-runs/concept-run-1"))
        return Response.json(conceptRun);
      if (url.pathname.endsWith("/concept-runs/concept-run-1/candidates"))
        return Response.json({ items: [concept] });
      if (url.pathname.endsWith("/scripts/script-1"))
        return Response.json(makeScript("script-1"));
      if (url.pathname.endsWith("/scripts/script-2"))
        return Response.json(makeScript("script-2"));
      if (url.pathname.endsWith("/storyboards/storyboard-1"))
        return Response.json({ version: makePlanningVersion("storyboard-1") });
      if (url.pathname.endsWith("/storyboards/storyboard-2"))
        return Response.json({ version: makePlanningVersion("storyboard-2") });
      if (url.pathname.endsWith("/shot-plans/shot-1"))
        return Response.json({ version: makePlanningVersion("shot-1") });
      if (url.pathname.endsWith("/shot-plans/shot-2"))
        return Response.json({ version: makePlanningVersion("shot-2") });
      if (url.pathname.endsWith("/planning-reviews"))
        return Response.json({ items: [review] });
      if (url.pathname.endsWith("/planning-reviews/review-1"))
        return Response.json({ review });
      if (url.pathname.endsWith("/revision-requests/revision-1"))
        return Response.json({ revision_request: revision() });
      return Response.json({ items: [] });
    });
}

function seedRevisionWorkspace() {
  window.localStorage.setItem(
    artifactStorageKey(context, "project-a"),
    JSON.stringify({
      sourceAssetId: "asset-1",
      sourceAssetVersionId: "asset-version-1",
      sourceObjectId: "object-1",
      extractionId: "extraction-1",
      briefRunId: "run-1",
      briefId: "brief-1",
      briefVersionId: "brief-version-1",
      conceptRunId: "concept-run-1",
      conceptCandidateIds: ["concept-1"],
      selectedConceptCandidateId: "concept-1",
      conceptSelectionId: "selection-1",
      scriptVersionId: "script-1",
      storyboardVersionId: "storyboard-1",
      shotPlanVersionId: "shot-1",
      reviewId: "review-1",
      revisionRequestId: "revision-1",
    }),
  );
}

describe("Stage-20 workspace behavior", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("clears source-file and notice state when switching projects", async () => {
    const mutations: string[] = [];
    mockWorkspaceFetch(mutations);
    renderWithStoredContext();

    await screen.findByRole("button", { name: /Alpha/ });
    fireEvent.click(screen.getByRole("button", { name: /Alpha/ }));
    await screen.findByText(/已恢复「Alpha」/);

    const file = new File(["{}"], "brief.json", { type: "application/json" });
    const fileInput = document.querySelector('input[type="file"]');
    if (!(fileInput instanceof HTMLInputElement))
      throw new Error("file input not found");
    fireEvent.change(fileInput, {
      target: { files: [file] },
    });
    expect(screen.getByText(/brief\.json/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Beta/ }));
    await screen.findByText(/已恢复「Beta」/);

    expect(screen.getByText("尚未选择文件")).toBeInTheDocument();
    expect(screen.queryByText(/已选择源文件/)).not.toBeInTheDocument();
    expect(mutations).toEqual([]);
  });

  it("does not auto-fire human gate or generation mutations on re-entry", async () => {
    const mutations: string[] = [];
    mockWorkspaceFetch(mutations);
    renderWithStoredContext();

    await screen.findByRole("button", { name: /Alpha/ });
    fireEvent.click(screen.getByRole("button", { name: /Alpha/ }));
    await waitFor(() =>
      expect(screen.getByText(/已恢复「Alpha」/)).toBeInTheDocument(),
    );
    await new Promise((resolve) => window.setTimeout(resolve, 0));

    expect(mutations).toEqual([]);
    expect(
      screen.getAllByText(/所有接受、选择、批准和导出都需要制作人明确操作/)
        .length,
    ).toBeGreaterThan(0);
  });

  it("discards a pending Project A mutation after switching to Project B", async () => {
    let resolveExtraction!: (response: Response) => void;
    const pendingExtraction = new Promise<Response>((resolve) => {
      resolveExtraction = resolve;
    });
    const mutations: string[] = [];
    const sourceAsset = {
      id: "asset-a",
      organization_id: "org-1",
      workspace_id: "workspace-1",
      project_id: "project-a",
      display_name: "alpha.json",
      status: "ready",
      current_version_id: "asset-version-a",
      latest_version_number: 1,
      created_by_actor_subject: "local-user",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
      version: 1,
    };
    const sourceVersion = {
      id: "asset-version-a",
      organization_id: "org-1",
      workspace_id: "workspace-1",
      project_id: "project-a",
      source_asset_id: "asset-a",
      version_number: 1,
      original_filename: "alpha.json",
      media_type: "application/json",
      byte_size: 2,
      checksum_algorithm: "sha256",
      checksum_value: "checksum-a",
      source_type: "api_declared",
      source_reference: null,
      external_record_id: null,
      declared_created_at: null,
      created_by_actor_subject: "local-user",
      created_at: "2026-01-01T00:00:00Z",
      supersedes_version_id: null,
      metadata_schema_version: "1",
    };
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = new URL(input instanceof Request ? input.url : String(input));
      const method =
        init?.method ?? (input instanceof Request ? input.method : "GET");
      if (method !== "GET") mutations.push(url.pathname);
      if (method === "POST" && url.pathname.endsWith("/extractions"))
        return pendingExtraction;
      if (
        method === "POST" &&
        url.pathname.endsWith("/brief-extraction-runs")
      ) {
        return Response.json({
          run_id: "brief-run-a",
          status: "completed",
          candidate_available: true,
        });
      }
      if (url.pathname.endsWith("/projects"))
        return Response.json({ items: projects });
      if (url.pathname.endsWith("/projects/project-a"))
        return Response.json(projects[0]);
      if (url.pathname.endsWith("/projects/project-b"))
        return Response.json(projects[1]);
      if (url.pathname.endsWith("/projects/project-a/source-assets"))
        return Response.json({ items: [sourceAsset], limit: 50, offset: 0 });
      if (url.pathname.endsWith("/projects/project-b/source-assets"))
        return Response.json({ items: [], limit: 50, offset: 0 });
      if (url.pathname.endsWith("/source-assets/asset-a"))
        return Response.json({
          source_asset: sourceAsset,
          current_version: sourceVersion,
        });
      if (url.pathname.endsWith("/versions/asset-version-a/object"))
        return Response.json({
          id: "object-a",
          source_asset_id: "asset-a",
          source_asset_version_id: "asset-version-a",
          state: "available",
          observed_byte_size: 2,
          created_at: "2026-01-01T00:00:00Z",
        });
      if (url.pathname.endsWith("/brief-extraction-runs/brief-run-a"))
        return Response.json({
          id: "brief-run-a",
          status: "completed",
          created_at: "2026-01-01T00:00:00Z",
        });
      if (url.pathname.endsWith("/brief-extraction-runs/brief-run-a/candidate"))
        return Response.json({
          run_id: "brief-run-a",
          candidate: { objective: { primary_goal: "A only" } },
          candidate_issues: [],
        });
      return emptyHydrationResponse(url);
    });
    renderWithStoredContext();

    await screen.findByRole("button", { name: /Alpha/ });
    fireEvent.click(screen.getByRole("button", { name: /Alpha/ }));
    await screen.findByText(/已恢复「Alpha」/);
    fireEvent.click(screen.getByRole("button", { name: "开始 Parse" }));
    await waitFor(() =>
      expect(mutations).toContain(
        "/api/v1/organizations/org-1/workspaces/workspace-1/projects/project-a/source-assets/asset-a/versions/asset-version-a/extractions",
      ),
    );

    fireEvent.click(screen.getByRole("button", { name: /Beta/ }));
    await screen.findByText(/已恢复「Beta」/);

    resolveExtraction(
      Response.json({
        extraction: {
          id: "extraction-a",
          source_asset_id: "asset-a",
          source_asset_version_id: "asset-version-a",
          parser_id: "deterministic",
          parser_version: "1",
          status: "completed",
          extracted_document: {},
          character_count: 2,
          warning_count: 0,
          truncated: false,
          created_at: "2026-01-01T00:00:00Z",
          schema_version: "1",
        },
        replayed: false,
        completed_at: "2026-01-01T00:00:00Z",
        correlation_id: "corr-a",
      }),
    );
    await waitFor(() =>
      expect(mutations).toContain(
        "/api/v1/organizations/org-1/workspaces/workspace-1/projects/project-a/source-assets/asset-a/versions/asset-version-a/extractions/extraction-a/brief-extraction-runs",
      ),
    );

    expect(screen.getByRole("heading", { name: "Upload" })).toBeInTheDocument();
    expect(screen.queryByText(/候选已载入 Brief 阶段/)).not.toBeInTheDocument();
    expect(screen.getByText(/已恢复「Beta」/)).toBeInTheDocument();
  });

  it("renders and cancels an open revision request through the backend", async () => {
    const requests: string[] = [];
    seedRevisionWorkspace();
    mockRevisionWorkspaceFetch("cancel", requests);
    renderWithStoredContext();

    await screen.findByRole("button", { name: /Alpha/ });
    fireEvent.click(screen.getByRole("button", { name: /Alpha/ }));
    await screen.findByText(/已恢复「Alpha」/);
    fireEvent.click(screen.getByRole("button", { name: /Review/ }));
    await screen.findByText("修改请求待处理");
    expect(screen.getAllByText("当前规划包需要修改。").length).toBeGreaterThan(
      0,
    );
    expect(
      screen.getAllByText(/补充第二场的动作连续性/).length,
    ).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "取消修改请求" }));
    await waitFor(() =>
      expect(requests).toContain(
        "POST /api/v1/organizations/org-1/workspaces/workspace-1/projects/project-a/revision-requests/revision-1/cancel",
      ),
    );
    expect(screen.queryByText("修改请求待处理")).not.toBeInTheDocument();
  });

  it("hydrates successor versions after completing an open revision request", async () => {
    const requests: string[] = [];
    seedRevisionWorkspace();
    mockRevisionWorkspaceFetch("complete", requests);
    renderWithStoredContext();

    await screen.findByRole("button", { name: /Alpha/ });
    fireEvent.click(screen.getByRole("button", { name: /Alpha/ }));
    await screen.findByText(/已恢复「Alpha」/);
    fireEvent.click(screen.getByRole("button", { name: /Review/ }));
    await screen.findByText("修改请求待处理");

    fireEvent.click(
      screen.getByRole("button", { name: "完成修改并创建 successor 版本" }),
    );
    await waitFor(() =>
      expect(requests).toContain(
        "POST /api/v1/organizations/org-1/workspaces/workspace-1/projects/project-a/revision-requests/revision-1/complete",
      ),
    );
    await waitFor(() =>
      expect(requests).toContain(
        "GET /api/v1/organizations/org-1/workspaces/workspace-1/projects/project-a/scripts/script-2",
      ),
    );
    expect(requests).toContain(
      "GET /api/v1/organizations/org-1/workspaces/workspace-1/projects/project-a/storyboards/storyboard-2",
    );
    expect(requests).toContain(
      "GET /api/v1/organizations/org-1/workspaces/workspace-1/projects/project-a/shot-plans/shot-2",
    );
    expect(screen.getByRole("heading", { name: "Review" })).toBeInTheDocument();
    expect(screen.queryByText("修改请求待处理")).not.toBeInTheDocument();
    expect(screen.getByText("等待制作人决定")).toBeInTheDocument();
  });

  it("does not suppress a concept-selection 409 using a local selection ID", async () => {
    window.localStorage.setItem(
      artifactStorageKey(context, "project-a"),
      JSON.stringify({
        conceptRunId: "concept-run-1",
        conceptCandidateIds: ["candidate-1"],
        selectedConceptCandidateId: "candidate-1",
        conceptSelectionId: "stale-selection-id",
      }),
    );
    writeResumeOperationKeys(
      window.localStorage,
      operationStorageKey(context, "project-a"),
      { conceptSelection: "stable-selection-key" },
    );
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = new URL(input instanceof Request ? input.url : String(input));
      const method =
        init?.method ?? (input instanceof Request ? input.method : "GET");
      if (method !== "GET") {
        return Response.json(
          {
            error: {
              code: "state_conflict",
              message: "selection conflict",
              correlation_id: "corr-conflict",
            },
          },
          { status: 409 },
        );
      }
      if (url.pathname.endsWith("/projects"))
        return Response.json({ items: projects });
      if (url.pathname.endsWith("/concept-runs/concept-run-1"))
        return Response.json({
          id: "concept-run-1",
          status: "completed",
          brief_id: "brief-1",
          brief_version_id: "brief-version-1",
          created_at: "2026-01-01T00:00:00Z",
          completed_at: "2026-01-01T00:00:00Z",
        });
      if (url.pathname.endsWith("/concept-runs/concept-run-1/candidates"))
        return Response.json({
          items: [
            {
              id: "candidate-1",
              candidate_index: 0,
              content: { title: "Concept" },
              created_at: "2026-01-01T00:00:00Z",
            },
          ],
        });
      return emptyHydrationResponse(url);
    });
    renderWithStoredContext();

    await screen.findByRole("button", { name: /Alpha/ });
    fireEvent.click(screen.getByRole("button", { name: /Alpha/ }));
    await screen.findByText("state_conflict");
    expect(screen.getByText("selection conflict")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Concepts/ }));
    const conceptsRail = screen.getByRole("button", { name: /Concepts/ });
    const scriptRail = screen.getByRole("button", { name: /Script/ });
    expect(conceptsRail).not.toHaveTextContent("完成");
    expect(conceptsRail).toHaveTextContent("可操作");
    expect(scriptRail).toHaveTextContent("等待前置");
    expect(
      screen.queryByRole("button", { name: "已选择此 Concept" }),
    ).not.toBeInTheDocument();

    const storedArtifacts = JSON.parse(
      window.localStorage.getItem(artifactStorageKey(context, "project-a")) ??
        "{}",
    ) as Record<string, unknown>;
    expect(storedArtifacts.selectedConceptCandidateId).toBeUndefined();
    expect(storedArtifacts.conceptSelectionId).toBeUndefined();
    const storedResume = JSON.parse(
      window.localStorage.getItem(operationStorageKey(context, "project-a")) ??
        "{}",
    ) as Record<string, unknown>;
    expect(storedResume.conceptSelection).toBeUndefined();
  });

  it("revalidates a persisted Concept selection with its original operation key", async () => {
    const mutations: Array<{ path: string; key: string | null }> = [];
    window.localStorage.setItem(
      artifactStorageKey(context, "project-a"),
      JSON.stringify({
        conceptRunId: "concept-run-1",
        conceptCandidateIds: ["candidate-1"],
        selectedConceptCandidateId: "candidate-1",
        conceptSelectionId: "selection-1",
      }),
    );
    writeResumeOperationKeys(
      window.localStorage,
      operationStorageKey(context, "project-a"),
      { conceptSelection: "stable-selection-key" },
    );
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = new URL(input instanceof Request ? input.url : String(input));
      const method =
        init?.method ?? (input instanceof Request ? input.method : "GET");
      if (method !== "GET") {
        mutations.push({
          path: url.pathname,
          key: new Headers(init?.headers).get("Idempotency-Key"),
        });
        return Response.json({
          selection_id: "selection-1",
          candidate_id: "candidate-1",
          replayed: true,
        });
      }
      if (url.pathname.endsWith("/projects"))
        return Response.json({ items: projects });
      if (url.pathname.endsWith("/concept-runs/concept-run-1")) {
        return Response.json({
          id: "concept-run-1",
          status: "completed",
          brief_id: "brief-1",
          brief_version_id: "brief-version-1",
          created_at: "2026-01-01T00:00:00Z",
          completed_at: "2026-01-01T00:00:00Z",
        });
      }
      if (url.pathname.endsWith("/concept-runs/concept-run-1/candidates")) {
        return Response.json({
          items: [
            {
              id: "candidate-1",
              candidate_index: 0,
              content: { title: "Concept" },
              created_at: "2026-01-01T00:00:00Z",
            },
          ],
        });
      }
      return emptyHydrationResponse(url);
    });
    renderWithStoredContext();

    await screen.findByRole("button", { name: /Alpha/ });
    fireEvent.click(screen.getByRole("button", { name: /Alpha/ }));
    await screen.findByText(/已恢复「Alpha」/);

    expect(mutations).toEqual([
      {
        path: "/api/v1/organizations/org-1/workspaces/workspace-1/projects/project-a/concept-runs/concept-run-1/candidates/candidate-1/select",
        key: "stable-selection-key",
      },
    ]);
  });
});

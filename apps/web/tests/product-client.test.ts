import { describe, expect, it, vi } from "vitest";

import {
  artifactStorageKey,
  createOperationKey,
  createProductClient,
  operationStorageKey,
  parseApiErrorEnvelope,
  readResumeOperationKeys,
  writeResumeOperationKeys,
} from "../src/lib/api/product-client";

const context = {
  actorSubject: "local-user",
  organizationId: "org-1",
  workspaceId: "workspace-1",
};

const project = {
  id: "project-1",
  name: "Film",
  description: null,
  status: "draft",
  version: 1,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

describe("product client", () => {
  it("sends tenant context and preserves mutation idempotency keys", async () => {
    const fetcher = vi.fn(async (_url: URL, init?: RequestInit) => {
      const headers = new Headers(init?.headers);
      expect(headers.get("X-Actor-Subject")).toBe("local-user");
      expect(headers.get("Idempotency-Key")).toBe("stable-key");
      return Response.json({
        id: "project-1",
        name: "Film",
        description: null,
        status: "draft",
        version: 1,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      });
    });
    const client = createProductClient("http://api.test", context, fetcher);

    await expect(
      client.createProject({
        name: "Film",
        description: null,
        idempotencyKey: "stable-key",
      }),
    ).resolves.toMatchObject({ id: "project-1", name: "Film" });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("retries safe reads after a transient response", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 503 }))
      .mockResolvedValueOnce(Response.json({ items: [] }));
    const client = createProductClient("http://api.test", context, fetcher);

    await expect(client.listProjects()).resolves.toEqual({ items: [] });
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("parses nested API errors and keeps correlation IDs actionable", async () => {
    const envelope = parseApiErrorEnvelope(
      {
        error: {
          code: "state_conflict",
          message: "state changed",
          correlation_id: "corr-7",
        },
      },
      "header-corr",
    );
    expect(envelope).toEqual({
      code: "state_conflict",
      message: "state changed",
      correlation_id: "corr-7",
    });

    const fetcher = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            error: { code: "state_conflict", message: "refresh required" },
          }),
          {
            status: 409,
            headers: {
              "content-type": "application/json",
              "x-correlation-id": "corr-8",
            },
          },
        ),
    );
    const client = createProductClient("http://api.test", context, fetcher);
    await expect(client.getProject("project-1")).rejects.toMatchObject({
      status: 409,
      code: "state_conflict",
      correlationId: "corr-8",
      isConflict: true,
    });
  });

  it("derives operation keys from crypto.randomUUID and persists the resume key per tenant/project", () => {
    const randomUUID = vi.fn(() => "00000000-0000-4000-8000-000000000007");
    vi.stubGlobal("crypto", { randomUUID });
    expect(createOperationKey("project 1:concept/select")).toBe(
      "project-1-concept-select-00000000-0000-4000-8000-000000000007",
    );
    expect(randomUUID).toHaveBeenCalledTimes(1);

    const values = new Map<string, string>();
    const storage = {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
    };
    const projectKey = operationStorageKey(context, "project-1");
    writeResumeOperationKeys(storage, projectKey, {
      conceptSelection: "stable-selection-key",
    });
    expect(readResumeOperationKeys(storage, projectKey)).toEqual({
      conceptSelection: "stable-selection-key",
    });
    expect(artifactStorageKey(context, "project-1")).not.toBe(
      artifactStorageKey(context, "project-2"),
    );
    vi.unstubAllGlobals();
  });

  it("reuses the caller's idempotency key when a mutation is retried", async () => {
    const fetcher = vi.fn(async (_url: URL, init?: RequestInit) => {
      expect(new Headers(init?.headers).get("Idempotency-Key")).toBe(
        "selection-run-key",
      );
      return Response.json({
        selection_id: "selection-1",
        candidate_id: "candidate-1",
        replayed: true,
      });
    });
    const client = createProductClient("http://api.test", context, fetcher);

    await client.selectConcept({
      projectId: "project-1",
      conceptRunId: "run-1",
      candidateId: "candidate-1",
      idempotencyKey: "selection-run-key",
    });
    await client.selectConcept({
      projectId: "project-1",
      conceptRunId: "run-1",
      candidateId: "candidate-1",
      idempotencyKey: "selection-run-key",
    });
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("does not synthesize a candidate-review record from browser-only state", async () => {
    const fetcher = vi.fn(async (url: URL) => {
      if (url.pathname.endsWith("/projects/project-1"))
        return Response.json(project);
      if (url.pathname.endsWith("/source-assets"))
        return Response.json({ items: [], limit: 50, offset: 0 });
      if (url.pathname.endsWith("/briefs")) return Response.json({ items: [] });
      if (url.pathname.endsWith("/planning-reviews"))
        return Response.json({ items: [] });
      throw new Error(`unexpected request: ${url.pathname}`);
    });
    const client = createProductClient("http://api.test", context, fetcher);

    const hydrated = await client.hydrateProject("project-1", {
      briefCandidateReviewId: "poisoned-review-id",
      briefCandidateReviewAction: "accept",
    });

    expect(hydrated.candidateReview).toBeUndefined();
    expect(hydrated.briefCandidateAvailable).toBeUndefined();
    expect(hydrated.artifacts.briefCandidateReviewId).toBe(
      "poisoned-review-id",
    );
    expect(JSON.stringify(hydrated)).not.toContain("stored-review");
  });

  it("sends an idempotency key for each brief-extraction run", async () => {
    const fetcher = vi.fn(async (_url: URL, init?: RequestInit) => {
      expect(new Headers(init?.headers).get("Idempotency-Key")).toBe(
        "brief-run-key",
      );
      return Response.json({
        run_id: "brief-run-1",
        status: "completed",
        candidate_available: true,
      });
    });
    const client = createProductClient("http://api.test", context, fetcher);

    await expect(
      client.extractBriefCandidate({
        projectId: "project-1",
        sourceAssetId: "asset-1",
        sourceAssetVersionId: "asset-version-1",
        extractionId: "extraction-1",
        idempotencyKey: "brief-run-key",
      }),
    ).resolves.toMatchObject({ run_id: "brief-run-1" });
  });

  it("drops stale source IDs and falls back to the latest listed source asset", async () => {
    const sourceAsset = {
      id: "asset-real",
      organization_id: "org-1",
      workspace_id: "workspace-1",
      project_id: "project-1",
      display_name: "brief.json",
      status: "ready",
      current_version_id: "asset-version-real",
      latest_version_number: 1,
      created_by_actor_subject: "local-user",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
      version: 1,
    };
    const sourceVersion = {
      id: "asset-version-real",
      organization_id: "org-1",
      workspace_id: "workspace-1",
      project_id: "project-1",
      source_asset_id: "asset-real",
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
    const requests: string[] = [];
    const fetcher = vi.fn(async (url: URL) => {
      requests.push(url.pathname);
      if (url.pathname.endsWith("/projects/project-1"))
        return Response.json(project);
      if (url.pathname.endsWith("/source-assets"))
        return Response.json({
          items: [sourceAsset],
          limit: 50,
          offset: 0,
        });
      if (url.pathname.endsWith("/source-assets/asset-stale"))
        return new Response(null, { status: 404 });
      if (url.pathname.endsWith("/source-assets/asset-real"))
        return Response.json({
          source_asset: sourceAsset,
          current_version: sourceVersion,
        });
      if (url.pathname.endsWith("/versions/asset-version-real/object"))
        return Response.json({
          id: "object-real",
          source_asset_id: "asset-real",
          source_asset_version_id: "asset-version-real",
          state: "available",
          observed_byte_size: 2,
          created_at: "2026-01-01T00:00:00Z",
        });
      if (url.pathname.endsWith("/briefs")) return Response.json({ items: [] });
      if (url.pathname.endsWith("/planning-reviews"))
        return Response.json({ items: [] });
      throw new Error(`unexpected request: ${url.pathname}`);
    });
    const client = createProductClient("http://api.test", context, fetcher);

    const hydrated = await client.hydrateProject("project-1", {
      sourceAssetId: "asset-stale",
      sourceAssetVersionId: "asset-version-stale",
      sourceObjectId: "object-stale",
      extractionId: "extraction-stale",
    });

    expect(hydrated.sourceAsset?.source_asset.id).toBe("asset-real");
    expect(hydrated.sourceObject?.id).toBe("object-real");
    expect(hydrated.artifacts).toMatchObject({
      sourceAssetId: "asset-real",
      sourceAssetVersionId: "asset-version-real",
      sourceObjectId: "object-real",
    });
    expect(hydrated.artifacts.extractionId).toBeUndefined();
    expect(requests).toContain(
      "/api/v1/organizations/org-1/workspaces/workspace-1/projects/project-1/source-assets/asset-real",
    );
  });

  it("uses the revision complete and cancel routes with idempotency headers", async () => {
    const calls: Array<{ path: string; key: string | null; body: unknown }> =
      [];
    const fetcher = vi.fn(async (url: URL, init?: RequestInit) => {
      calls.push({
        path: url.pathname,
        key: new Headers(init?.headers).get("Idempotency-Key"),
        body: init?.body ? JSON.parse(String(init.body)) : undefined,
      });
      if (url.pathname.endsWith("/complete"))
        return Response.json({
          revision_request: {
            id: "revision-1",
            review_id: "review-1",
            artifact_type: "planning_bundle",
            source_script_version_id: "script-1",
            source_storyboard_version_id: "storyboard-1",
            source_shot_plan_version_id: "shot-1",
            status: "completed",
            created_at: "2026-01-01T00:00:00Z",
            completed_at: "2026-01-01T00:01:00Z",
            successor_script_version_id: "script-2",
            successor_storyboard_version_id: "storyboard-2",
            successor_shot_plan_version_id: "shot-2",
          },
          successor_script_version_id: "script-2",
          successor_storyboard_version_id: "storyboard-2",
          successor_shot_plan_version_id: "shot-2",
          replayed: false,
        });
      return Response.json({
        revision_request: {
          id: "revision-1",
          review_id: "review-1",
          artifact_type: "planning_bundle",
          source_script_version_id: "script-1",
          source_storyboard_version_id: "storyboard-1",
          source_shot_plan_version_id: "shot-1",
          status: "cancelled",
          created_at: "2026-01-01T00:00:00Z",
          completed_at: null,
          successor_script_version_id: null,
          successor_storyboard_version_id: null,
          successor_shot_plan_version_id: null,
        },
      });
    });
    const client = createProductClient("http://api.test", context, fetcher);

    await client.completeRevision({
      projectId: "project-1",
      revisionRequestId: "revision-1",
      idempotencyKey: "complete-key",
    });
    await client.cancelRevision({
      projectId: "project-1",
      revisionRequestId: "revision-1",
      idempotencyKey: "cancel-key",
    });

    expect(calls).toEqual([
      {
        path: "/api/v1/organizations/org-1/workspaces/workspace-1/projects/project-1/revision-requests/revision-1/complete",
        key: "complete-key",
        body: { provider_mode: "valid" },
      },
      {
        path: "/api/v1/organizations/org-1/workspaces/workspace-1/projects/project-1/revision-requests/revision-1/cancel",
        key: "cancel-key",
        body: {},
      },
    ]);
  });
});

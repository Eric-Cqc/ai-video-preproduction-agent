import { describe, expect, it, vi } from "vitest";

import { createProductClient } from "../src/lib/api/product-client";

const context = {
  actorSubject: "local-user",
  organizationId: "org-1",
  workspaceId: "workspace-1",
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

  it("binds Golden Path idempotency keys to immutable lineage", async () => {
    const mutationKeys = new Map<string, string>();
    const fetcher = vi.fn(async (url: URL, init?: RequestInit) => {
      const path = url.pathname;
      const key = new Headers(init?.headers).get("Idempotency-Key");
      if (key) mutationKeys.set(path, key);
      if (path.endsWith("/source-assets"))
        return Response.json({
          source_asset: { id: "asset-1" },
          current_version: { id: "asset-version-1" },
        });
      if (path.endsWith("/uploads")) return Response.json({});
      if (path.endsWith("/extractions"))
        return Response.json({ extraction: { id: "extraction-1" } });
      if (path.endsWith("/brief-extraction-runs"))
        return Response.json({ run_id: "brief-run-1" });
      if (path.endsWith("/candidate"))
        return Response.json({ candidate: { schema_version: "1.0.0" } });
      if (path.endsWith("/accept"))
        return Response.json({
          brief_id: "brief-1",
          brief_version_id: "brief-version-1",
        });
      if (path.endsWith("/concept-runs"))
        return Response.json({
          run: { id: "concept-run-1" },
          candidates: [
            { id: "concept-candidate-1" },
            { id: "concept-candidate-2" },
            { id: "concept-candidate-3" },
          ],
        });
      if (path.endsWith("/select")) return Response.json({});
      if (path.endsWith("/scripts"))
        return Response.json({ script_version_id: "script-version-1" });
      if (path.endsWith("/storyboards"))
        return Response.json({ version: { id: "storyboard-version-1" } });
      if (path.endsWith("/shot-plans"))
        return Response.json({ version: { id: "shot-plan-version-1" } });
      if (path.endsWith("/planning-reviews"))
        return Response.json({ review: { id: "review-1" } });
      if (path.endsWith("/delivery-packages"))
        return Response.json({ package: { id: "package-1" } });
      if (path.endsWith("/exports"))
        return Response.json({
          export: { id: "export-1", filename: "delivery.zip" },
        });
      if (path.endsWith("/delivery-exports/export-1"))
        return new Response(new Uint8Array([80, 75]), { status: 200 });
      return new Response(null, { status: 404 });
    });
    const createObjectUrl = vi
      .spyOn(URL, "createObjectURL")
      .mockReturnValue("blob:delivery");
    const client = createProductClient("http://api.test", context, fetcher);
    const fixture = {
      name: "brief.json",
      size: 2,
      arrayBuffer: async () => new TextEncoder().encode("{}").buffer,
    } as File;

    await expect(
      client.runGoldenPath("project-1", fixture, () => undefined),
    ).resolves.toEqual({
      downloadUrl: "blob:delivery",
      filename: "delivery.zip",
    });

    expect([...mutationKeys.values()]).toEqual(
      expect.arrayContaining([
        expect.stringMatching(
          /^production-desk-project-1-source-[0-9a-f]{64}$/,
        ),
        "production-desk-project-1-upload-asset-version-1",
        "production-desk-project-1-parse-asset-version-1",
        "production-desk-project-1-extract-extraction-1",
        "production-desk-project-1-accept-brief-run-1",
        "production-desk-project-1-concepts-brief-version-1",
        "production-desk-project-1-select-concept-candidate-1",
        "production-desk-project-1-script-concept-run-1",
        "production-desk-project-1-storyboard-script-version-1",
        "production-desk-project-1-shots-storyboard-version-1",
        "production-desk-project-1-review-shot-plan-version-1",
        "production-desk-project-1-delivery-review-1",
        "production-desk-project-1-export-package-1",
      ]),
    );
    createObjectUrl.mockRestore();
  });
});

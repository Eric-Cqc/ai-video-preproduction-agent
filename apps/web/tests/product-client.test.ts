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
});

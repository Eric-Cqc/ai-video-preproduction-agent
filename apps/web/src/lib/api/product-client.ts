export interface LocalWorkspaceContext {
  actorSubject: string;
  organizationId: string;
  workspaceId: string;
}

export interface Project {
  id: string;
  name: string;
  description: string | null;
  status: string;
  version: number;
  created_at: string;
  updated_at: string;
}

interface ProjectListResponse {
  items: Project[];
}

export class ApiClientError extends Error {
  constructor(
    readonly status: number,
    readonly correlationId?: string,
  ) {
    super(`Local API request failed (${status})`);
  }
}

interface ProductClient {
  listProjects(): Promise<ProjectListResponse>;
  createProject(input: {
    name: string;
    description: string | null;
    idempotencyKey: string;
  }): Promise<Project>;
  runGoldenPath(
    projectId: string,
    file: File,
    onStep: (step: string) => void,
  ): Promise<{ downloadUrl: string; filename: string }>;
}

type ProductFetcher = (input: URL, init?: RequestInit) => Promise<Response>;

const retryableStatuses = new Set([502, 503, 504]);

export function createProductClient(
  baseUrl: string,
  context: LocalWorkspaceContext,
  fetcher: ProductFetcher = fetch,
  useTemporaryHeaders = true,
): ProductClient {
  const workspacePath = `/api/v1/organizations/${encodeURIComponent(context.organizationId)}/workspaces/${encodeURIComponent(context.workspaceId)}`;
  const request = async <T>(
    path: string,
    init: RequestInit = {},
    retry = init.method === undefined || init.method === "GET",
  ): Promise<T> => {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 8_000);
    const headers = new Headers(init.headers);
    headers.set("accept", "application/json");
    if (useTemporaryHeaders) {
      headers.set("X-Actor-Subject", context.actorSubject);
      headers.set("X-Organization-Id", context.organizationId);
      headers.set("X-Workspace-Id", context.workspaceId);
    }
    try {
      const response = await fetcher(new URL(path, baseUrl), {
        ...init,
        headers,
        cache: "no-store",
        signal: controller.signal,
      });
      if (retry && retryableStatuses.has(response.status)) {
        const retried = await fetcher(new URL(path, baseUrl), {
          ...init,
          headers,
          cache: "no-store",
        });
        if (!retried.ok)
          throw new ApiClientError(
            retried.status,
            retried.headers.get("x-correlation-id") ?? undefined,
          );
        return (await retried.json()) as T;
      }
      if (!response.ok)
        throw new ApiClientError(
          response.status,
          response.headers.get("x-correlation-id") ?? undefined,
        );
      return (await response.json()) as T;
    } finally {
      window.clearTimeout(timeout);
    }
  };

  return {
    listProjects: () =>
      request<ProjectListResponse>(`${workspacePath}/projects`),
    createProject: ({ name, description, idempotencyKey }) =>
      request<Project>(
        `${workspacePath}/projects`,
        {
          method: "POST",
          headers: {
            "content-type": "application/json",
            "Idempotency-Key": idempotencyKey,
          },
          body: JSON.stringify({ name, description }),
        },
        false,
      ),
    runGoldenPath: async (projectId, file, onStep) => {
      const root = `${workspacePath}/projects/${projectId}`;
      const key = (step: string) => `production-desk-${projectId}-${step}`;
      const post = <T>(path: string, body: object, step: string) =>
        request<T>(
          path,
          {
            method: "POST",
            headers: {
              "content-type": "application/json",
              "Idempotency-Key": key(step),
            },
            body: JSON.stringify(body),
          },
          false,
        );
      const field = (value: unknown, ...path: string[]): unknown =>
        path.reduce<unknown>(
          (current, name) =>
            current && typeof current === "object"
              ? (current as Record<string, unknown>)[name]
              : undefined,
          value,
        );
      const id = (value: unknown, ...path: string[]) => {
        const result = field(value, ...path);
        if (typeof result !== "string")
          throw new Error(`Invalid API response: ${path.join(".")}`);
        return result;
      };
      onStep("登记来源素材");
      const bytes = await file.arrayBuffer();
      const checksum = Array.from(
        new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)),
      )
        .map((item) => item.toString(16).padStart(2, "0"))
        .join("");
      const asset = await post<unknown>(
        `${root}/source-assets`,
        {
          display_name: file.name,
          original_filename: file.name,
          media_type: "application/json",
          byte_size: file.size,
          checksum_algorithm: "sha256",
          checksum_value: checksum,
          source_type: "api_declared",
          source_reference: null,
          external_record_id: null,
          declared_created_at: null,
        },
        "source",
      );
      const assetId = id(asset, "source_asset", "id");
      const versionId = id(asset, "current_version", "id");
      onStep("上传并解析");
      await request<unknown>(
        `${root}/source-assets/${assetId}/versions/${versionId}/uploads`,
        {
          method: "POST",
          headers: {
            "content-type": "application/octet-stream",
            "Idempotency-Key": key("upload"),
          },
          body: bytes,
        },
        false,
      );
      const extraction = await post<unknown>(
        `${root}/source-assets/${assetId}/versions/${versionId}/extractions`,
        {},
        "parse",
      );
      const extractionId = id(extraction, "extraction", "id");
      onStep("提取并接受 Brief");
      const run = await post<unknown>(
        `${root}/source-assets/${assetId}/versions/${versionId}/extractions/${extractionId}/brief-extraction-runs`,
        {},
        "extract",
      );
      const runId = id(run, "run_id");
      const candidate = await request<unknown>(
        `${root}/brief-extraction-runs/${runId}/candidate`,
      );
      const accepted = await post<unknown>(
        `${root}/brief-extraction-runs/${runId}/accept`,
        {
          brief_id: null,
          expected_brief_version: null,
          expected_current_version_id: null,
          accepted_content: field(candidate, "candidate"),
          title: file.name,
        },
        "accept",
      );
      const briefId = id(accepted, "brief_id");
      const briefVersionId = id(accepted, "brief_version_id");
      onStep("生成并选择 Concept");
      const concepts = await post<unknown>(
        `${root}/briefs/${briefId}/versions/${briefVersionId}/concept-runs`,
        {},
        "concepts",
      );
      const conceptRunId = id(concepts, "run", "id");
      const candidates = field(concepts, "candidates");
      if (!Array.isArray(candidates) || candidates.length !== 3)
        throw new Error("Concept API did not return three candidates");
      await post<unknown>(
        `${root}/concept-runs/${conceptRunId}/candidates/${id(candidates[0], "id")}/select`,
        {},
        "select",
      );
      onStep("生成 Script、Storyboard 与 Shot Plan");
      const scriptId = id(
        await post<unknown>(
          `${root}/concept-runs/${conceptRunId}/scripts`,
          {},
          "script",
        ),
        "script_version_id",
      );
      const storyboardId = id(
        await post<unknown>(
          `${root}/scripts/${scriptId}/storyboards`,
          { provider_mode: "valid" },
          "storyboard",
        ),
        "version",
        "id",
      );
      const shotPlanId = id(
        await post<unknown>(
          `${root}/storyboards/${storyboardId}/shot-plans`,
          { provider_mode: "valid" },
          "shots",
        ),
        "version",
        "id",
      );
      onStep("批准并创建交付包");
      const reviewId = id(
        await post<unknown>(
          `${root}/planning-reviews`,
          {
            artifact_type: "planning_bundle",
            script_version_id: scriptId,
            storyboard_version_id: storyboardId,
            shot_plan_version_id: shotPlanId,
            outcome: "approved",
            summary: "Approved in deterministic local workflow.",
            requested_changes: {},
          },
          "review",
        ),
        "review",
        "id",
      );
      const packageId = id(
        await post<unknown>(
          `${root}/delivery-packages`,
          {
            script_version_id: scriptId,
            storyboard_version_id: storyboardId,
            shot_plan_version_id: shotPlanId,
            approval_review_id: reviewId,
          },
          "delivery",
        ),
        "package",
        "id",
      );
      onStep("生成并下载 ZIP");
      const exported = await post<unknown>(
        `${root}/delivery-packages/${packageId}/exports`,
        { format: "delivery-package.zip" },
        "export",
      );
      const exportId = id(exported, "export", "id");
      const filename = id(exported, "export", "filename");
      const download = await fetcher(
        new URL(`${root}/delivery-exports/${exportId}`, baseUrl),
        {
          headers: {
            "X-Actor-Subject": context.actorSubject,
            "X-Organization-Id": context.organizationId,
            "X-Workspace-Id": context.workspaceId,
          },
        },
      );
      if (!download.ok) throw new ApiClientError(download.status);
      return {
        downloadUrl: URL.createObjectURL(await download.blob()),
        filename,
      };
    },
  };
}

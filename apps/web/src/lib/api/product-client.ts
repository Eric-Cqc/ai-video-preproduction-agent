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
}

type ProductFetcher = (input: URL, init?: RequestInit) => Promise<Response>;

const retryableStatuses = new Set([502, 503, 504]);

export function createProductClient(
  baseUrl: string,
  context: LocalWorkspaceContext,
  fetcher: ProductFetcher = fetch,
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
    headers.set("X-Actor-Subject", context.actorSubject);
    headers.set("X-Organization-Id", context.organizationId);
    headers.set("X-Workspace-Id", context.workspaceId);
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
  };
}

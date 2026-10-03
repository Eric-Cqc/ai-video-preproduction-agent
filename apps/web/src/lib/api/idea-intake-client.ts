import {
  ApiClientError,
  parseApiErrorEnvelope,
  type BriefBundle,
  type LocalWorkspaceContext,
} from "./product-client";

export interface IdeaIntake {
  id: string;
  raw_idea: string;
  objective: string | null;
  platform: string | null;
  audience: string | null;
  duration_seconds: number | null;
  content_type: string | null;
  tone: string[];
  key_messages: string[];
  call_to_action: string | null;
  constraints: string[];
  must_include: string[];
  must_avoid: string[];
  assumptions: string[];
  missing_fields: string[];
  status: "structured" | "confirmed";
  brief_id: string | null;
  brief_version_id: string | null;
  version: number;
}
export type IdeaEdits = Omit<
  IdeaIntake,
  "id" | "raw_idea" | "status" | "brief_id" | "brief_version_id" | "version"
>;

/** Existing IdeaIntake routes composed beside the stable planning client. */
export function createIdeaIntakeClient(
  baseUrl: string,
  context: LocalWorkspaceContext,
  temporary = true,
) {
  const root = (projectId: string) =>
    `/api/v1/organizations/${encodeURIComponent(context.organizationId)}/workspaces/${encodeURIComponent(context.workspaceId)}/projects/${encodeURIComponent(projectId)}/idea-intakes`;
  async function request<T>(
    path: string,
    method = "GET",
    body?: object,
  ): Promise<T> {
    const headers = new Headers({ accept: "application/json" });
    if (temporary) {
      headers.set("X-Actor-Subject", context.actorSubject);
      headers.set("X-Organization-Id", context.organizationId);
      headers.set("X-Workspace-Id", context.workspaceId);
    }
    if (body) headers.set("content-type", "application/json");
    const response = await fetch(new URL(path, baseUrl), {
      method,
      headers,
      ...(body ? { body: JSON.stringify(body) } : {}),
      cache: "no-store",
      signal: AbortSignal.timeout(30_000),
    });
    if (!response.ok)
      throw new ApiClientError(
        response.status,
        parseApiErrorEnvelope(
          await response.json().catch(() => null),
          response.headers.get("x-correlation-id") ?? undefined,
        ),
      );
    return (await response.json()) as T;
  }
  return {
    readSelection: async (projectId: string, runId: string) => {
      try {
        return await request<{ selection_id: string; candidate_id: string }>(
          root(projectId).replace(
            /idea-intakes$/,
            `concept-runs/${encodeURIComponent(runId)}/selection`,
          ),
        );
      } catch (error) {
        if (error instanceof ApiClientError && error.status === 404)
          return undefined;
        throw error;
      }
    },
    list: (projectId: string) =>
      request<{ items: IdeaIntake[] }>(root(projectId)),
    create: (projectId: string, idea: string) =>
      request<IdeaIntake>(root(projectId), "POST", { idea }),
    update: (projectId: string, intake: IdeaIntake, edits: IdeaEdits) =>
      request<IdeaIntake>(
        `${root(projectId)}/${encodeURIComponent(intake.id)}`,
        "PATCH",
        { ...edits, expected_version: intake.version },
      ),
    confirm: (projectId: string, intake: IdeaIntake) =>
      request<{ idea_intake: IdeaIntake; result: BriefBundle }>(
        `${root(projectId)}/${encodeURIComponent(intake.id)}/confirm`,
        "POST",
        {
          expected_version: intake.version,
          title: intake.objective ?? "Idea Brief",
        },
      ),
  };
}

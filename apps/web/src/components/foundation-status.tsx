"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";

import type { HealthResult } from "../lib/api/health-client";
import {
  ApiClientError,
  artifactStorageKey,
  createOperationKey,
  createProductClient,
  operationStorageKey,
  parseApiErrorEnvelope,
  readArtifactIds,
  readResumeOperationKeys,
  writeArtifactIds,
  writeResumeOperationKeys,
  type ArtifactIds,
  type JsonRecord,
  type LocalWorkspaceContext,
  type PlanningRevisionRequest,
  type Project,
  type ResumeOperationKeys,
} from "../lib/api/product-client";
import { ErrorPanel } from "./ui/error-panel";
import { WorkspaceStage } from "./workbench/workspace-stage";
import {
  fromHydratedProject,
  latestReview,
  nextActionableStage,
  stageDefinitions,
  stageDescription,
  stageLabel,
  stageStatuses,
  stateLabel,
  type StageId,
  type StageState,
  type WorkspaceSnapshot,
} from "../lib/workspace-model";

interface FoundationStatusProps {
  environment: string;
  api: HealthResult;
  apiBaseUrl: string;
}

const contextStorageKey = "production-desk-context";
const selectedProjectKeyPrefix = "production-desk-selected-project";
const emptyContext: LocalWorkspaceContext = {
  actorSubject: "",
  organizationId: "",
  workspaceId: "",
};

type DeskError = ApiClientError | Error;
type ProjectIdentity = Pick<
  LocalWorkspaceContext,
  "organizationId" | "workspaceId"
> & { projectId: string };
type WorkspacePatch = (
  patch: (current: WorkspaceSnapshot) => WorkspaceSnapshot,
) => void;
type StageAction = (
  idempotencyKey: string,
  isCurrent: () => boolean,
  applyWorkspace: WorkspacePatch,
) => Promise<void>;

function sameProjectIdentity(
  left: ProjectIdentity | undefined,
  right: ProjectIdentity | undefined,
): boolean {
  return Boolean(
    left &&
    right &&
    left.organizationId === right.organizationId &&
    left.workspaceId === right.workspaceId &&
    left.projectId === right.projectId,
  );
}

function loadStoredContext(): LocalWorkspaceContext {
  if (typeof window === "undefined") return emptyContext;
  const saved = window.localStorage.getItem(contextStorageKey);
  if (!saved) return emptyContext;
  try {
    const value: unknown = JSON.parse(saved);
    if (!isRecord(value)) return emptyContext;
    if (
      typeof value.actorSubject === "string" &&
      typeof value.organizationId === "string" &&
      typeof value.workspaceId === "string"
    ) {
      return {
        actorSubject: value.actorSubject,
        organizationId: value.organizationId,
        workspaceId: value.workspaceId,
      };
    }
  } catch {
    window.localStorage.removeItem(contextStorageKey);
  }
  return emptyContext;
}

function tenantKey(context: LocalWorkspaceContext): string {
  return `${context.organizationId}:${context.workspaceId}`;
}

function selectedProjectStorageKey(context: LocalWorkspaceContext): string {
  return `${selectedProjectKeyPrefix}:${encodeURIComponent(tenantKey(context))}`;
}

function hasTenantContext(context: LocalWorkspaceContext): boolean {
  return Boolean(
    context.actorSubject && context.organizationId && context.workspaceId,
  );
}

function errorFor(error: unknown): DeskError {
  if (error instanceof ApiClientError) return error;
  if (error instanceof Error) return error;
  return new Error("操作未完成。请稍后重试。");
}

function errorReason(error: unknown): string {
  return errorFor(error).message;
}

function statusClass(state: StageState): string {
  return `stage-state stage-state-${state}`;
}

function StageRail({
  snapshot,
  activeStage,
  onSelect,
}: {
  snapshot: WorkspaceSnapshot | null;
  activeStage: StageId;
  onSelect: (stage: StageId) => void;
}) {
  const statuses = snapshot ? stageStatuses(snapshot) : undefined;
  return (
    <nav className="production-rail" aria-label="制作阶段">
      <p className="rail-label">Production rail</p>
      {!snapshot ? (
        <p className="rail-empty">选择项目后载入真实阶段状态。</p>
      ) : null}
      <ol>
        {stageDefinitions.map((stage) => {
          const state = statuses?.[stage.id] ?? "blocked";
          return (
            <li
              key={stage.id}
              className={`rail-stage rail-stage-${state}${stage.id === activeStage ? " active" : ""}`}
            >
              <button
                type="button"
                className="rail-button"
                aria-current={stage.id === activeStage ? "step" : undefined}
                aria-label={`${stage.label}：${state === "blocked" ? "需先完成前序步骤" : stateLabel(state)}`}
                onClick={() => onSelect(stage.id)}
              >
                <span className="rail-number">{stage.index}</span>
                <span className="rail-stage-name">{stage.label}</span>
                <span className={statusClass(state)}>
                  {stateLabel(state)}
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

function ContextForm({
  value,
  onChange,
}: {
  value: LocalWorkspaceContext;
  onChange: (value: LocalWorkspaceContext) => void;
}) {
  return (
    <details className="context-panel">
      <summary>本地工作区设置</summary>
      <p>仅用于本机开发环境；不会保存凭据，也不会连接外部 Provider。</p>
      <div className="context-fields">
        {(
          [
            ["actorSubject", "操作人"],
            ["organizationId", "组织 ID"],
            ["workspaceId", "工作区 ID"],
          ] as const
        ).map(([field, label]) => (
          <label key={field}>
            {label}
            <input
              value={value[field]}
              onChange={(event) =>
                onChange({ ...value, [field]: event.target.value })
              }
              autoComplete="off"
            />
          </label>
        ))}
      </div>
    </details>
  );
}

function ProjectList({
  projects,
  selectedProjectId,
  onSelect,
}: {
  projects: readonly Project[];
  selectedProjectId: string | undefined;
  onSelect: (project: Project) => void;
}) {
  if (projects.length === 0) {
    return (
      <p className="empty-state">尚无项目。创建一个制作蓝图项目以开始工作。</p>
    );
  }
  return (
    <ul className="project-list" aria-label="项目列表">
      {projects.map((project) => (
        <li key={project.id}>
          <button
            type="button"
            className={
              project.id === selectedProjectId
                ? "project-card selected"
                : "project-card"
            }
            aria-current={project.id === selectedProjectId ? "page" : undefined}
            onClick={() => onSelect(project)}
          >
            <strong>{project.name}</strong>
            <span>{project.status}</span>
            <small>{project.description || "尚未添加说明"}</small>
          </button>
        </li>
      ))}
    </ul>
  );
}

export function FoundationStatus({
  environment,
  api,
  apiBaseUrl,
}: FoundationStatusProps) {
  const hostedPilot = environment === "hosted" || environment === "hosted_test";
  const [context, setContext] =
    useState<LocalWorkspaceContext>(loadStoredContext);
  const [projects, setProjects] = useState<readonly Project[]>([]);
  const [selected, setSelected] = useState<Project | null>(null);
  const [workspace, setWorkspace] = useState<WorkspaceSnapshot | null>(null);
  const [activeStage, setActiveStage] = useState<StageId>("upload");
  const [projectName, setProjectName] = useState("");
  const [projectDescription, setProjectDescription] = useState("");
  const [notice, setNotice] = useState(
    "输入本地工作区设置后，可读取或创建项目。",
  );
  const [busy, setBusy] = useState(false);
  const [hydrating, setHydrating] = useState(false);
  const [sourceFile, setSourceFile] = useState<File | null>(null);
  const [download, setDownload] = useState<{
    downloadUrl: string;
    filename: string;
  } | null>(null);
  const [error, setError] = useState<DeskError | null>(null);
  const [pilotPassword, setPilotPassword] = useState("");
  const [pilotReady, setPilotReady] = useState(!hostedPilot);
  const [rejectReason, setRejectReason] = useState("inaccurate");
  const [rejectNote, setRejectNote] = useState("");
  const [reviewSummary, setReviewSummary] =
    useState("当前规划包已由制作人审查。");
  const [reviewChanges, setReviewChanges] = useState("");
  const operationKeys = useRef(new Map<string, string>());
  const lastAction = useRef<(() => void) | null>(null);
  const selectedProjectId = useRef<string | undefined>(undefined);
  const activeProjectIdentity = useRef<ProjectIdentity | undefined>(undefined);
  const mutationIdentity = useRef<ProjectIdentity | undefined>(undefined);
  const hydrationRequest = useRef(0);

  const client = useMemo(
    () => createProductClient(apiBaseUrl, context, fetch, !hostedPilot),
    [apiBaseUrl, context, hostedPilot],
  );

  const clearDownload = useCallback(() => {
    setDownload((current) => {
      if (current && typeof URL !== "undefined" && URL.revokeObjectURL)
        URL.revokeObjectURL(current.downloadUrl);
      return null;
    });
  }, []);

  const resetTransientState = useCallback(() => {
    operationKeys.current.clear();
    lastAction.current = null;
    setSourceFile(null);
    clearDownload();
    setError(null);
    setNotice("已清除上一个项目的临时状态。");
  }, [clearDownload]);

  const patchWorkspace = useCallback(
    (
      patch: (current: WorkspaceSnapshot) => WorkspaceSnapshot,
      expectedIdentity?: ProjectIdentity,
    ) => {
      setWorkspace((current) => {
        if (!current) return current;
        const guardIdentity = expectedIdentity ?? mutationIdentity.current;
        if (
          guardIdentity &&
          !sameProjectIdentity(activeProjectIdentity.current, guardIdentity)
        ) {
          return current;
        }
        const next = patch(current);
        const projectId =
          guardIdentity?.projectId ?? activeProjectIdentity.current?.projectId;
        if (projectId) {
          try {
            writeArtifactIds(
              window.localStorage,
              artifactStorageKey(
                {
                  ...context,
                  organizationId:
                    guardIdentity?.organizationId ?? context.organizationId,
                  workspaceId:
                    guardIdentity?.workspaceId ?? context.workspaceId,
                },
                projectId,
              ),
              next.artifacts,
            );
          } catch {
            // Local persistence is a resume aid; API state remains authoritative.
          }
        }
        return next;
      });
    },
    [context],
  );

  const setActiveStageIfCurrent = useCallback(
    (stage: StageId, isCurrent?: () => boolean) => {
      if (isCurrent ? !isCurrent() : false) return;
      const expectedIdentity = mutationIdentity.current;
      if (
        expectedIdentity &&
        !sameProjectIdentity(activeProjectIdentity.current, expectedIdentity)
      ) {
        return;
      }
      setActiveStage(stage);
    },
    [],
  );

  const updateResumeState = useCallback(
    (projectId: string, patch: Partial<ResumeOperationKeys>) => {
      try {
        const key = operationStorageKey(context, projectId);
        const current = readResumeOperationKeys(window.localStorage, key);
        writeResumeOperationKeys(window.localStorage, key, {
          ...current,
          ...patch,
        });
      } catch {
        // Resume state is a convenience; the API remains authoritative.
      }
    },
    [context],
  );

  const hydrateProject = useCallback(
    async (project: Project, artifactIds: ArtifactIds) => {
      const requestId = hydrationRequest.current + 1;
      hydrationRequest.current = requestId;
      const isCurrentRequest = () =>
        hydrationRequest.current === requestId &&
        selectedProjectId.current === project.id;
      setHydrating(true);
      setBusy(true);
      try {
        let resumeState: ResumeOperationKeys = {};
        try {
          resumeState = readResumeOperationKeys(
            window.localStorage,
            operationStorageKey(context, project.id),
          );
        } catch {
          resumeState = {};
        }
        const hydrated = await client.hydrateProject(project.id, artifactIds);
        let resumed = hydrated;
        if (
          hydrated.conceptRun &&
          hydrated.artifacts.selectedConceptCandidateId &&
          hydrated.concepts.some(
            (candidate) =>
              candidate.id === hydrated.artifacts.selectedConceptCandidateId,
          )
        ) {
          let selectionKey = resumeState.conceptSelection;
          selectionKey ??= createOperationKey(
            `${project.id}:concepts:resume-selection`,
          );
          try {
            const selection = await client.selectConcept({
              projectId: project.id,
              conceptRunId: hydrated.conceptRun.id,
              candidateId: hydrated.artifacts.selectedConceptCandidateId,
              idempotencyKey: selectionKey,
            });
            resumed = {
              ...hydrated,
              artifacts: {
                ...hydrated.artifacts,
                selectedConceptCandidateId: selection.candidate_id,
                conceptSelectionId: selection.selection_id,
              },
            };
            try {
              updateResumeState(project.id, { conceptSelection: selectionKey });
            } catch {
              // The selection remains API-backed when browser storage is unavailable.
            }
          } catch (caught) {
            const selectionError = errorFor(caught);
            const cleanedArtifacts = { ...hydrated.artifacts };
            delete cleanedArtifacts.selectedConceptCandidateId;
            delete cleanedArtifacts.conceptSelectionId;
            resumed = {
              ...hydrated,
              artifacts: cleanedArtifacts,
              issues: [
                ...hydrated.issues,
                selectionError instanceof ApiClientError
                  ? selectionError
                  : new ApiClientError(0, {
                      message: selectionError.message,
                    }),
              ],
            };
            updateResumeState(project.id, { conceptSelection: undefined });
          }
        }
        if (!isCurrentRequest()) return;
        const next = fromHydratedProject(resumed);
        setWorkspace(next);
        try {
          writeArtifactIds(
            window.localStorage,
            artifactStorageKey(context, project.id),
            next.artifacts,
          );
        } catch {
          // Continue with API-backed state when browser storage is unavailable.
        }
        setActiveStage(nextActionableStage(next));
        setError(resumed.issues[0] ?? null);
        setNotice(
          resumed.issues.length > 0
            ? "项目已恢复，但部分可选记录读取失败。"
            : `已恢复「${project.name}」的制作状态。`,
        );
      } catch (caught) {
        if (!isCurrentRequest()) return;
        const nextError = errorFor(caught);
        setWorkspace(null);
        setError(nextError);
        setNotice("项目状态读取失败。请使用错误面板中的恢复动作。");
      } finally {
        if (isCurrentRequest()) {
          setHydrating(false);
          setBusy(false);
        }
      }
    },
    [client, context, updateResumeState],
  );

  const selectProject = useCallback(
    async (project: Project) => {
      resetTransientState();
      activeProjectIdentity.current = {
        organizationId: context.organizationId,
        workspaceId: context.workspaceId,
        projectId: project.id,
      };
      selectedProjectId.current = project.id;
      setSelected(project);
      setWorkspace(null);
      setActiveStage("upload");
      try {
        window.localStorage.setItem(
          selectedProjectStorageKey(context),
          project.id,
        );
      } catch {
        // Continue without a remembered selection.
      }
      let artifactIds: ArtifactIds = {};
      try {
        artifactIds = readArtifactIds(
          window.localStorage,
          artifactStorageKey(context, project.id),
        );
      } catch {
        artifactIds = {};
      }
      await hydrateProject(project, artifactIds);
    },
    [context, hydrateProject, resetTransientState],
  );

  const loadProjects = useCallback(async () => {
    if (!hasTenantContext(context)) {
      setNotice("请先完整填写本地工作区设置。");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await client.listProjects();
      setProjects(result.items);
      let rememberedId = "";
      try {
        rememberedId =
          window.localStorage.getItem(selectedProjectStorageKey(context)) ?? "";
      } catch {
        rememberedId = "";
      }
      const nextProject =
        result.items.find((project) => project.id === rememberedId) ??
        result.items.find(
          (project) => project.id === selectedProjectId.current,
        );
      if (nextProject) {
        await selectProject(nextProject);
      } else {
        activeProjectIdentity.current = undefined;
        selectedProjectId.current = undefined;
        hydrationRequest.current += 1;
        setSelected(null);
        setWorkspace(null);
        setActiveStage("upload");
        setNotice(`已读取 ${result.items.length} 个项目。`);
      }
    } catch (caught) {
      const nextError = errorFor(caught);
      setError(nextError);
      setNotice("项目列表读取失败。");
    } finally {
      setBusy(false);
    }
  }, [client, context, selectProject]);

  useEffect(() => {
    try {
      window.localStorage.setItem(contextStorageKey, JSON.stringify(context));
    } catch {
      // Context remains usable for the current session.
    }
  }, [context]);

  useEffect(() => {
    if (hostedPilot && !pilotReady) return;
    if (!hasTenantContext(context)) return;
    void loadProjects();
  }, [context, hostedPilot, loadProjects, pilotReady]);

  useEffect(() => {
    return () => {
      if (download && typeof URL !== "undefined" && URL.revokeObjectURL)
        URL.revokeObjectURL(download.downloadUrl);
    };
  }, [download]);

  const loadPilotContext = useCallback(async () => {
    const response = await fetch(new URL("/api/v1/pilot-context", apiBaseUrl), {
      credentials: "same-origin",
      cache: "no-store",
    });
    if (!response.ok) {
      let payload: unknown;
      try {
        payload = await response.json();
      } catch {
        payload = undefined;
      }
      const envelope = parseApiErrorEnvelope(
        payload,
        response.headers.get("x-correlation-id") ?? undefined,
      );
      throw new ApiClientError(response.status, envelope);
    }
    const value = (await response.json()) as {
      actor_subject: string;
      organization_id: string;
      workspace_id: string;
    };
    setContext({
      actorSubject: value.actor_subject,
      organizationId: value.organization_id,
      workspaceId: value.workspace_id,
    });
    setPilotReady(true);
  }, [apiBaseUrl]);

  useEffect(() => {
    if (!hostedPilot) return;
    const timer = window.setTimeout(() => {
      void loadPilotContext().catch((caught) => setError(errorFor(caught)));
    }, 0);
    return () => window.clearTimeout(timer);
  }, [hostedPilot, loadPilotContext]);

  async function grantPilotAccess(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(
        new URL("/api/v1/pilot-access", apiBaseUrl),
        {
          method: "POST",
          credentials: "same-origin",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ password: pilotPassword }),
        },
      );
      if (!response.ok) {
        let payload: unknown;
        try {
          payload = await response.json();
        } catch {
          payload = undefined;
        }
        throw new ApiClientError(
          response.status,
          parseApiErrorEnvelope(
            payload,
            response.headers.get("x-correlation-id") ?? undefined,
          ),
        );
      }
      setPilotPassword("");
      await loadPilotContext();
      setNotice("已进入私有试点工作台。");
    } catch (caught) {
      setError(errorFor(caught));
      setNotice("试点访问未完成。");
    } finally {
      setBusy(false);
    }
  }

  function handleContextChange(next: LocalWorkspaceContext) {
    if (tenantKey(next) !== tenantKey(context)) {
      resetTransientState();
      activeProjectIdentity.current = undefined;
      selectedProjectId.current = undefined;
      hydrationRequest.current += 1;
      setProjects([]);
      setSelected(null);
      setWorkspace(null);
      setActiveStage("upload");
    }
    setContext(next);
  }

  async function createProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!hasTenantContext(context)) {
      setNotice("请先完整填写本地工作区设置。");
      return;
    }
    if (!projectName.trim()) {
      setNotice("请填写项目名称。");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const project = await client.createProject({
        name: projectName.trim(),
        description: projectDescription.trim() || null,
        idempotencyKey: createOperationKey("project-create"),
      });
      setProjects((current) => [project, ...current]);
      setProjectName("");
      setProjectDescription("");
      await selectProject(project);
      setNotice("项目已创建。请从 Upload 开始登记制作输入。");
    } catch (caught) {
      setError(errorFor(caught));
      setNotice("项目创建未完成。");
    } finally {
      setBusy(false);
    }
  }

  function operationScope(stage: StageId, detail: string): string {
    return `${selected?.id ?? "project"}:${stage}:${detail}`;
  }

  function operationKey(scope: string): string {
    const current = operationKeys.current.get(scope);
    if (current) return current;
    const next = createOperationKey(scope);
    operationKeys.current.set(scope, next);
    return next;
  }

  async function runStage(
    stage: StageId,
    detail: string,
    action: StageAction,
  ): Promise<void> {
    if (!selected || !workspace) return;
    const identity: ProjectIdentity = {
      organizationId: context.organizationId,
      workspaceId: context.workspaceId,
      projectId: selected.id,
    };
    const isCurrent = () =>
      sameProjectIdentity(activeProjectIdentity.current, identity);
    const scope = operationScope(stage, detail);
    const key = operationKey(scope);
    mutationIdentity.current = identity;
    lastAction.current = () => {
      void runStage(stage, detail, action);
    };
    const applyWorkspace: WorkspacePatch = (patch) => {
      if (isCurrent()) patchWorkspace(patch, identity);
    };
    setBusy(true);
    setError(null);
    setNotice(`${stageLabel(stage)} 操作进行中…`);
    applyWorkspace((current) => {
      const errors = { ...current.errors };
      delete errors[stage];
      return { ...current, activeOperation: stage, errors };
    });
    try {
      await action(key, isCurrent, applyWorkspace);
      if (!isCurrent()) return;
      operationKeys.current.delete(scope);
      lastAction.current = null;
      applyWorkspace((current) => ({ ...current, activeOperation: null }));
      setNotice(`${stageLabel(stage)} 已完成当前动作。`);
    } catch (caught) {
      if (!isCurrent()) return;
      const nextError = errorFor(caught);
      applyWorkspace((current) => ({
        ...current,
        activeOperation: null,
        errors: { ...current.errors, [stage]: errorReason(caught) },
      }));
      setError(nextError);
      setNotice(`${stageLabel(stage)} 未完成；请查看错误详情。`);
    } finally {
      if (isCurrent()) {
        setBusy(false);
        if (sameProjectIdentity(mutationIdentity.current, identity)) {
          mutationIdentity.current = undefined;
        }
      }
    }
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    setSourceFile(event.target.files?.[0] ?? null);
    clearDownload();
    setError(null);
    setNotice(
      event.target.files?.[0]
        ? "已选择源文件；下一步由你明确开始 Upload。"
        : "已清除源文件选择。",
    );
  }

  function handleUpload() {
    const project = selected;
    const current = workspace;
    const file = sourceFile;
    if (!project || !current || !file) {
      setNotice("请选择项目和 Structured Brief JSON 文件。");
      return;
    }
    void runStage(
      "upload",
      `${file.name}:${file.size}:${file.lastModified}`,
      async (key, _isCurrent, applyWorkspace) => {
        const checksum = await sha256File(file);
        const created = await client.createSourceAsset({
          projectId: project.id,
          displayName: file.name,
          originalFilename: file.name,
          mediaType: "application/json",
          byteSize: file.size,
          checksum,
          idempotencyKey: `${key}-metadata`,
        });
        const sourceAsset = {
          source_asset: created.source_asset,
          current_version: created.current_version,
        };
        const uploaded = await client.uploadSourceObject({
          projectId: project.id,
          sourceAssetId: created.source_asset.id,
          sourceAssetVersionId: created.current_version.id,
          bytes: await file.arrayBuffer(),
          idempotencyKey: `${key}-bytes`,
        });
        applyWorkspace((snapshot) => {
          const artifacts: ArtifactIds = {
            sourceAssetId: created.source_asset.id,
            sourceAssetVersionId: created.current_version.id,
            sourceObjectId: uploaded.source_object.id,
          };
          return {
            ...snapshot,
            artifacts,
            sourceAssets: [
              created.source_asset,
              ...snapshot.sourceAssets.filter(
                (item) => item.id !== created.source_asset.id,
              ),
            ],
            sourceAsset,
            sourceObject: uploaded.source_object,
            extraction: undefined,
            briefRun: undefined,
            candidate: undefined,
            briefCandidateAvailable: undefined,
            candidateReview: undefined,
            brief: undefined,
            conceptRun: undefined,
            concepts: [],
            script: undefined,
            storyboard: undefined,
            shotPlan: undefined,
            reviews: [],
            review: undefined,
            revisionRequest: undefined,
            deliveryPackage: undefined,
            exports: [],
            errors: {},
          };
        });
        updateResumeState(project.id, {
          conceptSelection: undefined,
          briefCandidateAvailable: undefined,
        });
      },
    );
  }

  function handleParse() {
    const project = selected;
    const current = workspace;
    const sourceAssetId = current?.artifacts.sourceAssetId;
    const sourceAssetVersionId = current?.artifacts.sourceAssetVersionId;
    if (
      !project ||
      !current ||
      !sourceAssetId ||
      !sourceAssetVersionId ||
      !current.sourceObject
    ) {
      setNotice("请先完成 Upload。");
      return;
    }
    void runStage(
      "parse",
      `${sourceAssetId}:${sourceAssetVersionId}`,
      async (key, _isCurrent, applyWorkspace) => {
        const extractionResult = await client.createDocumentExtraction({
          projectId: project.id,
          sourceAssetId,
          sourceAssetVersionId,
          idempotencyKey: `${key}-document`,
        });
        const extraction = extractionResult.extraction;
        applyWorkspace((snapshot) => ({
          ...snapshot,
          artifacts: { ...snapshot.artifacts, extractionId: extraction.id },
          extraction,
          briefCandidateAvailable: undefined,
        }));
        if (extraction.status === "failed") {
          updateResumeState(project.id, {
            conceptSelection: undefined,
            briefCandidateAvailable: false,
          });
          throw new Error("文档解析运行已失败；请检查源文件后重试。");
        }
        const started = await client.extractBriefCandidate({
          projectId: project.id,
          sourceAssetId,
          sourceAssetVersionId,
          extractionId: extraction.id,
          idempotencyKey: `${key}-brief`,
        });
        const briefRun = await client.getBriefExtractionRun(
          project.id,
          started.run_id,
        );
        if (
          started.status === "failed" ||
          briefRun.status === "failed" ||
          !started.candidate_available
        ) {
          updateResumeState(project.id, {
            conceptSelection: undefined,
            briefCandidateAvailable: false,
          });
          applyWorkspace((snapshot) => ({
            ...snapshot,
            artifacts: {
              ...snapshot.artifacts,
              extractionId: extraction.id,
              briefRunId: briefRun.id,
            },
            briefRun,
            candidate: undefined,
            briefCandidateAvailable: false,
            candidateReview: undefined,
            errors: {
              ...snapshot.errors,
              parse:
                "解析运行已失败；candidate_available=false，没有可审查候选。",
            },
          }));
          throw new Error(
            "解析运行已失败；candidate_available=false，没有可审查候选。请检查源文件后重试。",
          );
        }
        const candidate = await client.getBriefCandidate(
          project.id,
          started.run_id,
        );
        updateResumeState(project.id, {
          conceptSelection: undefined,
          briefCandidateAvailable: true,
        });
        applyWorkspace((snapshot) => {
          const artifacts: ArtifactIds = {
            ...snapshot.artifacts,
            extractionId: extraction.id,
            briefRunId: briefRun.id,
          };
          delete artifacts.briefCandidateReviewId;
          delete artifacts.briefCandidateReviewAction;
          delete artifacts.briefId;
          delete artifacts.briefVersionId;
          delete artifacts.conceptRunId;
          delete artifacts.conceptCandidateIds;
          delete artifacts.selectedConceptCandidateId;
          delete artifacts.conceptSelectionId;
          delete artifacts.scriptVersionId;
          delete artifacts.storyboardRunId;
          delete artifacts.storyboardVersionId;
          delete artifacts.shotPlanRunId;
          delete artifacts.shotPlanVersionId;
          delete artifacts.reviewId;
          delete artifacts.revisionRequestId;
          delete artifacts.deliveryPackageVersionId;
          delete artifacts.exportId;
          return {
            ...snapshot,
            artifacts,
            extraction,
            briefRun,
            candidate,
            briefCandidateAvailable: true,
            candidateReview: undefined,
            brief: undefined,
            conceptRun: undefined,
            concepts: [],
            script: undefined,
            storyboard: undefined,
            shotPlan: undefined,
            reviews: [],
            review: undefined,
            revisionRequest: undefined,
            deliveryPackage: undefined,
            exports: [],
            errors: {},
          };
        });
        setActiveStageIfCurrent("brief", _isCurrent);
      },
    );
  }

  function handleAccept() {
    const project = selected;
    const current = workspace;
    if (!project || !current?.candidate || !current.briefRun) return;
    void runStage(
      "brief",
      `${current.briefRun.id}:accept`,
      async (key, _isCurrent, applyWorkspace) => {
        const response = await client.acceptBriefCandidate({
          projectId: project.id,
          runId: current.briefRun?.id ?? "",
          acceptedContent: current.candidate?.candidate ?? {},
          title: current.sourceAsset?.source_asset.display_name ?? project.name,
          idempotencyKey: `${key}-accept`,
        });
        if (!response.brief_id || !response.brief_version_id)
          throw new Error("Accept API 未返回 Brief 版本 ID。");
        const brief = await client.getBrief(project.id, response.brief_id);
        applyWorkspace((snapshot) => ({
          ...snapshot,
          artifacts: acceptedArtifactIds(
            snapshot.artifacts,
            response.review_id,
            response.brief_id,
            response.brief_version_id,
          ),
          candidateReview: response,
          brief,
          revisionRequest: undefined,
          errors: {},
        }));
        setActiveStageIfCurrent("concepts", _isCurrent);
      },
    );
  }

  function handleReject() {
    const project = selected;
    const current = workspace;
    if (!project || !current?.briefRun) return;
    void runStage(
      "brief",
      `${current.briefRun.id}:reject:${rejectReason}:${rejectNote.trim()}`,
      async (key, _isCurrent, applyWorkspace) => {
        const response = await client.rejectBriefCandidate({
          projectId: project.id,
          runId: current.briefRun?.id ?? "",
          reason: rejectReason,
          note: rejectNote.trim() || null,
          idempotencyKey: `${key}-reject`,
        });
        applyWorkspace((snapshot) => {
          const artifacts = {
            ...snapshot.artifacts,
            briefCandidateReviewId: response.review_id,
            briefCandidateReviewAction: "reject" as const,
          };
          delete artifacts.revisionRequestId;
          return {
            ...snapshot,
            artifacts,
            candidateReview: response,
            revisionRequest: undefined,
            errors: {},
          };
        });
      },
    );
  }

  function handleGenerateConcepts() {
    const project = selected;
    const current = workspace;
    if (!project || !current?.brief) return;
    void runStage(
      "concepts",
      `${current.brief.brief.id}:${current.brief.current_version.id}`,
      async (key, _isCurrent, applyWorkspace) => {
        const response = await client.generateConcepts({
          projectId: project.id,
          briefId: current.brief?.brief.id ?? "",
          briefVersionId: current.brief?.current_version.id ?? "",
          idempotencyKey: `${key}-generate`,
        });
        applyWorkspace((snapshot) => ({
          ...snapshot,
          artifacts: {
            ...snapshot.artifacts,
            conceptRunId: response.run.id,
            conceptCandidateIds: response.candidates.map(
              (candidate) => candidate.id,
            ),
          },
          conceptRun: response.run,
          concepts: response.candidates,
          script: undefined,
          storyboard: undefined,
          shotPlan: undefined,
          review: undefined,
          revisionRequest: undefined,
          reviews: [],
          deliveryPackage: undefined,
          exports: [],
          errors: {},
        }));
        setActiveStageIfCurrent("concepts", _isCurrent);
      },
    );
  }

  function handleSelectConcept(candidateId: string) {
    const project = selected;
    const current = workspace;
    if (!project || !current?.conceptRun) return;
    void runStage(
      "concepts",
      `${current.conceptRun.id}:select:${candidateId}`,
      async (key, _isCurrent, applyWorkspace) => {
        const response = await client.selectConcept({
          projectId: project.id,
          conceptRunId: current.conceptRun?.id ?? "",
          candidateId,
          idempotencyKey: `${key}-select`,
        });
        updateResumeState(project.id, { conceptSelection: `${key}-select` });
        applyWorkspace((snapshot) => ({
          ...snapshot,
          artifacts: {
            ...snapshot.artifacts,
            selectedConceptCandidateId: response.candidate_id,
            conceptSelectionId: response.selection_id,
          },
        }));
        setActiveStageIfCurrent("script", _isCurrent);
      },
    );
  }

  function handleGenerateScript() {
    const project = selected;
    const current = workspace;
    if (
      !project ||
      !current?.conceptRun ||
      !current.artifacts.selectedConceptCandidateId
    )
      return;
    void runStage(
      "script",
      current.conceptRun.id,
      async (key, _isCurrent, applyWorkspace) => {
        const response = await client.generateScript({
          projectId: project.id,
          conceptRunId: current.conceptRun?.id ?? "",
          idempotencyKey: `${key}-generate`,
        });
        const script = await client.getScript(
          project.id,
          response.script_version_id,
        );
        applyWorkspace((snapshot) => ({
          ...snapshot,
          artifacts: {
            ...snapshot.artifacts,
            scriptVersionId: response.script_version_id,
          },
          script,
          storyboard: undefined,
          shotPlan: undefined,
          review: undefined,
          revisionRequest: undefined,
          reviews: [],
          deliveryPackage: undefined,
          exports: [],
        }));
        setActiveStageIfCurrent("storyboard", _isCurrent);
      },
    );
  }

  function handleGenerateStoryboard() {
    const project = selected;
    const current = workspace;
    if (!project || !current?.script) return;
    void runStage(
      "storyboard",
      current.script.id,
      async (key, _isCurrent, applyWorkspace) => {
        const response = await client.generateStoryboard({
          projectId: project.id,
          scriptVersionId: current.script?.id ?? "",
          idempotencyKey: `${key}-generate`,
        });
        const storyboard = await client.getStoryboardVersion(
          project.id,
          response.version.id,
        );
        applyWorkspace((snapshot) => ({
          ...snapshot,
          artifacts: {
            ...snapshot.artifacts,
            storyboardRunId: response.run.id,
            storyboardVersionId: storyboard.id,
          },
          storyboard,
          shotPlan: undefined,
          review: undefined,
          revisionRequest: undefined,
          reviews: [],
          deliveryPackage: undefined,
          exports: [],
        }));
        setActiveStageIfCurrent("shot-plan", _isCurrent);
      },
    );
  }

  function handleGenerateShotPlan() {
    const project = selected;
    const current = workspace;
    if (!project || !current?.storyboard) return;
    void runStage(
      "shot-plan",
      current.storyboard.id,
      async (key, _isCurrent, applyWorkspace) => {
        const response = await client.generateShotPlan({
          projectId: project.id,
          storyboardVersionId: current.storyboard?.id ?? "",
          idempotencyKey: `${key}-generate`,
        });
        const shotPlan = await client.getShotPlanVersion(
          project.id,
          response.version.id,
        );
        applyWorkspace((snapshot) => ({
          ...snapshot,
          artifacts: {
            ...snapshot.artifacts,
            shotPlanRunId: response.run.id,
            shotPlanVersionId: shotPlan.id,
          },
          shotPlan,
          review: undefined,
          revisionRequest: undefined,
          reviews: [],
          deliveryPackage: undefined,
          exports: [],
        }));
        setActiveStageIfCurrent("review", _isCurrent);
      },
    );
  }

  function submitReview(outcome: "approved" | "revision_requested") {
    const project = selected;
    const current = workspace;
    if (
      !project ||
      !current?.script ||
      !current.storyboard ||
      !current.shotPlan
    )
      return;
    const summary = reviewSummary.trim();
    const changes = reviewChanges.trim();
    if (!summary || (outcome === "revision_requested" && !changes)) return;
    void runStage(
      "review",
      `${current.script.id}:${outcome}:${outcome === "approved" ? summary : changes}`,
      async (key, _isCurrent, applyWorkspace) => {
        const response = await client.submitPlanningReview({
          projectId: project.id,
          scriptVersionId: current.script?.id ?? "",
          storyboardVersionId: current.storyboard?.id ?? "",
          shotPlanVersionId: current.shotPlan?.id ?? "",
          outcome,
          summary,
          requestedChanges:
            outcome === "revision_requested" ? { reason: changes } : {},
          idempotencyKey: `${key}-submit`,
        });
        const revisionRequest = response.revision_request
          ? enrichRevisionRequest(response.revision_request, response.review)
          : undefined;
        applyWorkspace((snapshot) => {
          const artifacts: ArtifactIds = {
            ...snapshot.artifacts,
            reviewId: response.review.id,
          };
          if (revisionRequest) {
            artifacts.revisionRequestId = revisionRequest.id;
          } else {
            delete artifacts.revisionRequestId;
          }
          return {
            ...snapshot,
            artifacts,
            reviews: [...snapshot.reviews, response.review],
            review: response.review,
            revisionRequest,
            deliveryPackage: undefined,
            exports: [],
          };
        });
        setActiveStageIfCurrent(
          outcome === "approved" ? "delivery" : "review",
          _isCurrent,
        );
      },
    );
  }

  function handleCompleteRevision() {
    const project = selected;
    const current = workspace;
    const revisionRequest = current?.revisionRequest;
    if (
      !project ||
      !current ||
      !revisionRequest ||
      revisionRequest.status !== "open"
    )
      return;
    void runStage(
      "review",
      `${revisionRequest.id}:complete`,
      async (key, _isCurrent, applyWorkspace) => {
        const response = await client.completeRevision({
          projectId: project.id,
          revisionRequestId: revisionRequest.id,
          providerMode: "valid",
          idempotencyKey: `${key}-complete`,
        });
        const successorIds = [
          response.successor_script_version_id,
          response.successor_storyboard_version_id,
          response.successor_shot_plan_version_id,
        ];
        if (successorIds.some((value) => !value)) {
          throw new Error(
            "Complete revision API 未返回完整 successor 版本 ID。",
          );
        }
        const hydrationArtifacts: ArtifactIds = {
          ...current.artifacts,
          scriptVersionId: response.successor_script_version_id as string,
          storyboardVersionId:
            response.successor_storyboard_version_id as string,
          shotPlanVersionId: response.successor_shot_plan_version_id as string,
          revisionRequestId: response.revision_request.id,
        };
        delete hydrationArtifacts.reviewId;
        delete hydrationArtifacts.deliveryPackageVersionId;
        delete hydrationArtifacts.exportId;
        const hydrated = await client.hydrateProject(
          project.id,
          hydrationArtifacts,
        );
        const reviewDetails = current.review ?? latestReview(current);
        if (!reviewDetails) throw new Error("修改请求缺少来源审查记录。");
        const revision = enrichRevisionRequest(
          response.revision_request,
          reviewDetails,
        );
        const artifacts: ArtifactIds = {
          ...hydrated.artifacts,
          scriptVersionId: response.successor_script_version_id as string,
          storyboardVersionId:
            response.successor_storyboard_version_id as string,
          shotPlanVersionId: response.successor_shot_plan_version_id as string,
          revisionRequestId: response.revision_request.id,
        };
        delete artifacts.reviewId;
        delete artifacts.deliveryPackageVersionId;
        delete artifacts.exportId;
        applyWorkspace((snapshot) => ({
          ...fromHydratedProject(
            {
              ...hydrated,
              artifacts,
              reviews: [],
              review: undefined,
              revisionRequest: revision,
            },
            snapshot,
          ),
          errors: {},
        }));
        setActiveStageIfCurrent("review", _isCurrent);
      },
    );
  }

  function handleCancelRevision() {
    const project = selected;
    const current = workspace;
    const revisionRequest = current?.revisionRequest;
    if (
      !project ||
      !current ||
      !revisionRequest ||
      revisionRequest.status !== "open"
    )
      return;
    void runStage(
      "review",
      `${revisionRequest.id}:cancel`,
      async (key, _isCurrent, applyWorkspace) => {
        const response = await client.cancelRevision({
          projectId: project.id,
          revisionRequestId: revisionRequest.id,
          idempotencyKey: `${key}-cancel`,
        });
        const reviewDetails = current.review ?? latestReview(current);
        if (!reviewDetails) throw new Error("修改请求缺少来源审查记录。");
        const revision = enrichRevisionRequest(
          response.revision_request,
          reviewDetails,
        );
        applyWorkspace((snapshot) => ({
          ...snapshot,
          artifacts: {
            ...snapshot.artifacts,
            revisionRequestId: revision.id,
          },
          revisionRequest: revision,
          errors: {},
        }));
      },
    );
  }

  function handleCreateDelivery() {
    const project = selected;
    const current = workspace;
    const review = current ? latestReview(current) : undefined;
    if (
      !project ||
      !current?.script ||
      !current.storyboard ||
      !current.shotPlan ||
      !review ||
      review.outcome !== "approved"
    )
      return;
    void runStage(
      "delivery",
      `${review.id}:package`,
      async (key, _isCurrent, applyWorkspace) => {
        const response = await client.createDeliveryPackage({
          projectId: project.id,
          scriptVersionId: current.script?.id ?? "",
          storyboardVersionId: current.storyboard?.id ?? "",
          shotPlanVersionId: current.shotPlan?.id ?? "",
          approvalReviewId: review.id,
          idempotencyKey: `${key}-package`,
        });
        applyWorkspace((snapshot) => ({
          ...snapshot,
          artifacts: {
            ...snapshot.artifacts,
            deliveryPackageVersionId: response.package.id,
          },
          deliveryPackage: response.package,
          exports: [],
        }));
      },
    );
  }

  function handleExportDelivery() {
    const project = selected;
    const current = workspace;
    const review = current ? latestReview(current) : undefined;
    if (
      !project ||
      !current?.deliveryPackage ||
      !review ||
      review.outcome !== "approved"
    )
      return;
    void runStage(
      "delivery",
      `${current.deliveryPackage.id}:export`,
      async (key, _isCurrent, applyWorkspace) => {
        const response = await client.exportDeliveryPackage({
          projectId: project.id,
          deliveryPackageVersionId: current.deliveryPackage?.id ?? "",
          idempotencyKey: `${key}-zip`,
        });
        applyWorkspace((snapshot) => ({
          ...snapshot,
          artifacts: { ...snapshot.artifacts, exportId: response.export.id },
          exports: [
            ...snapshot.exports.filter(
              (item) => item.id !== response.export.id,
            ),
            response.export,
          ],
        }));
      },
    );
  }

  function handleDownload(exportId: string, filename: string) {
    const project = selected;
    if (!project) return;
    setBusy(true);
    setError(null);
    void client
      .downloadExport(project.id, exportId, filename)
      .then((result) => {
        clearDownload();
        setDownload({
          downloadUrl: URL.createObjectURL(result.blob),
          filename: result.filename,
        });
        setNotice(
          `已准备 ${result.filename} 下载；Checksum 见 Delivery 清单。`,
        );
      })
      .catch((caught) => {
        setError(errorFor(caught));
        setNotice("ZIP 下载未完成。");
      })
      .finally(() => setBusy(false));
  }

  function refreshSelected() {
    if (!selected) {
      void loadProjects();
      return;
    }
    let ids: ArtifactIds = workspace?.artifacts ?? {};
    try {
      ids = readArtifactIds(
        window.localStorage,
        artifactStorageKey(context, selected.id),
      );
    } catch {
      // Use in-memory IDs when storage is unavailable.
    }
    void hydrateProject(selected, ids);
  }

  function retryLastAction() {
    if (lastAction.current) {
      lastAction.current();
      return;
    }
    refreshSelected();
  }

  function retryWithNewKey() {
    operationKeys.current.clear();
    if (selected)
      updateResumeState(selected.id, { conceptSelection: undefined });
    if (lastAction.current) {
      lastAction.current();
      return;
    }
    refreshSelected();
  }

  return (
    <main className="production-shell">
      <a className="skip-link" href="#workspace">
        跳至工作区内容
      </a>
      <header className="masthead">
        <div>
          <p className="eyebrow">AI VIDEO PREPRODUCTION AGENT</p>
          <h1>Production Desk</h1>
          <p className="masthead-subtitle">
            把 Brief 变成可审查、可交接的制作蓝图。
          </p>
        </div>
        <div className="system-state" aria-live="polite">
          <span
            className={
              api.state === "available"
                ? "status-dot ready"
                : "status-dot blocked"
            }
          />
          {api.state === "available"
            ? `本地 API 已连接 · ${environment}`
            : "本地 API 未连接"}
        </div>
      </header>

      <div className="workspace-grid" id="workspace">
        <aside className="left-panel">
          <StageRail
            snapshot={workspace}
            activeStage={activeStage}
            onSelect={setActiveStage}
          />
          {hostedPilot ? null : (
            <ContextForm value={context} onChange={handleContextChange} />
          )}
          <section className="boundary-note">
            <p className="eyebrow">Boundary</p>
            <p>
              所有接受、选择、批准和导出都需要制作人明确操作。这里编排前期制作蓝图，不生成最终视频。
            </p>
          </section>
        </aside>

        <section className="main-panel" aria-labelledby="desk-title">
          {hostedPilot && !pilotReady ? (
            <form
              className="pilot-gate"
              onSubmit={(event) => void grantPilotAccess(event)}
            >
              <div>
                <p className="eyebrow">Private pilot</p>
                <h2>进入私有试点工作台</h2>
                <p>访问门只用于当前单租户试点，不是生产认证。</p>
              </div>
              <label>
                访问凭据
                <input
                  type="password"
                  value={pilotPassword}
                  onChange={(event) => setPilotPassword(event.target.value)}
                  autoComplete="current-password"
                />
              </label>
              <button className="button" type="submit" disabled={busy}>
                进入试点
              </button>
            </form>
          ) : null}

          <div className="section-heading">
            <div>
              <p className="eyebrow">Projects home</p>
              <h2 id="desk-title">制作项目</h2>
            </div>
            <button
              className="button secondary"
              type="button"
              disabled={busy || !pilotReady}
              onClick={() => void loadProjects()}
            >
              {busy ? "处理中…" : "刷新项目"}
            </button>
          </div>
          <p className="notice" role="status" aria-live="polite">
            {notice}
          </p>
          {error ? (
            <ErrorPanel
              error={error}
              onRefresh={refreshSelected}
              onRetry={retryLastAction}
              onNewKey={retryWithNewKey}
            />
          ) : null}

          <details className="project-index" open={!selected}>
            <summary>
              项目索引 <span>{projects.length} 个项目</span>
            </summary>
            <ProjectList
              projects={projects}
              selectedProjectId={selected?.id}
              onSelect={(project) => void selectProject(project)}
            />
          </details>

          <form
            className="project-form"
            onSubmit={(event) => void createProject(event)}
          >
            <label>
              新项目名称
              <input
                value={projectName}
                onChange={(event) => setProjectName(event.target.value)}
                placeholder="例如：春季品牌片"
              />
            </label>
            <label>
              制作说明（可选）
              <input
                value={projectDescription}
                onChange={(event) => setProjectDescription(event.target.value)}
                placeholder="目标、受众或交付背景"
              />
            </label>
            <button
              className="button"
              type="submit"
              disabled={busy || !pilotReady}
            >
              创建项目
            </button>
          </form>

          {hydrating ? (
            <div className="workspace-loading" role="status">
              <span className="loading-orbit" aria-hidden="true" />
              正在从 API 恢复项目状态…
            </div>
          ) : selected && workspace ? (
            <WorkspaceStage
              snapshot={workspace}
              activeStage={activeStage}
              sourceFile={sourceFile}
              busy={busy}
              rejectReason={rejectReason}
              rejectNote={rejectNote}
              reviewSummary={reviewSummary}
              reviewChanges={reviewChanges}
              onFileChange={handleFileChange}
              onUpload={handleUpload}
              onParse={handleParse}
              onAccept={handleAccept}
              onReject={handleReject}
              onRejectReasonChange={setRejectReason}
              onRejectNoteChange={setRejectNote}
              onGenerateConcepts={handleGenerateConcepts}
              onSelectConcept={handleSelectConcept}
              onGenerateScript={handleGenerateScript}
              onGenerateStoryboard={handleGenerateStoryboard}
              onGenerateShotPlan={handleGenerateShotPlan}
              onReviewSummaryChange={setReviewSummary}
              onReviewChangesChange={setReviewChanges}
              onApprove={() => submitReview("approved")}
              onRequestChanges={() => submitReview("revision_requested")}
              onCompleteRevision={handleCompleteRevision}
              onCancelRevision={handleCancelRevision}
              onCreateDelivery={handleCreateDelivery}
              onExportDelivery={handleExportDelivery}
              onDownload={handleDownload}
              download={download}
            />
          ) : (
            <div className="no-project-state">
              <span aria-hidden="true">✦</span>
              <h3>选择一个项目开始</h3>
              <p>
                项目状态、artifact IDs 和当前阶段会在进入后从本地 API 恢复。
              </p>
            </div>
          )}
        </section>

        <aside className="right-panel" aria-label="项目详情">
          <p className="eyebrow">Project context</p>
          {selected && workspace ? (
            <>
              <h2>{selected.name}</h2>
              <p>{selected.description || "尚未添加项目说明。"}</p>
              <dl className="metadata-list">
                <div>
                  <dt>项目状态</dt>
                  <dd>{selected.status}</dd>
                </div>
                <div>
                  <dt>项目版本</dt>
                  <dd>v{selected.version}</dd>
                </div>
                <div>
                  <dt>当前阶段</dt>
                  <dd>{stageLabel(activeStage)}</dd>
                </div>
                <div>
                  <dt>已保存 IDs</dt>
                  <dd>{countArtifactIds(workspace.artifacts)} 个</dd>
                </div>
              </dl>
              <section className="next-step">
                <h3>当前动作</h3>
                <p>{stageDescription(workspace, activeStage)}</p>
                <button
                  className="button secondary"
                  type="button"
                  onClick={refreshSelected}
                  disabled={busy}
                >
                  重新读取真实状态
                </button>
              </section>
              <details className="artifact-detail">
                <summary>Artifact ID ledger</summary>
                <dl className="ledger-list">
                  {Object.entries(workspace.artifacts).map(([key, value]) => (
                    <div key={key}>
                      <dt>{key}</dt>
                      <dd>
                        <code>
                          {Array.isArray(value)
                            ? value.join(", ")
                            : String(value)}
                        </code>
                      </dd>
                    </div>
                  ))}
                </dl>
              </details>
            </>
          ) : (
            <p className="empty-state">
              选择一个项目后，可查看其版本、artifact IDs 和后续动作。
            </p>
          )}
          <section className="safety-note">
            <h3>审计边界</h3>
            <p>
              浏览器只调用本地 API 的 tenant-scoped 路由；不会保存 Provider
              密钥，也不会直接调用模型、渲染器或外部存储。
            </p>
          </section>
        </aside>
      </div>
    </main>
  );
}

async function sha256File(file: File): Promise<string> {
  const digest = await globalThis.crypto.subtle.digest(
    "SHA-256",
    await file.arrayBuffer(),
  );
  return Array.from(new Uint8Array(digest))
    .map((item) => item.toString(16).padStart(2, "0"))
    .join("");
}

function countArtifactIds(artifacts: ArtifactIds): number {
  return Object.values(artifacts).reduce(
    (count, value) =>
      count +
      (Array.isArray(value) ? (value.length > 0 ? 1 : 0) : value ? 1 : 0),
    0,
  );
}

function acceptedArtifactIds(
  current: ArtifactIds,
  reviewId: string,
  briefId: string | null,
  briefVersionId: string | null,
): ArtifactIds {
  const next: ArtifactIds = {
    ...current,
    briefCandidateReviewId: reviewId,
    briefCandidateReviewAction: "accept",
  };
  delete next.revisionRequestId;
  if (briefId) next.briefId = briefId;
  if (briefVersionId) next.briefVersionId = briefVersionId;
  return next;
}

function enrichRevisionRequest(
  revisionRequest: PlanningRevisionRequest,
  review: { summary: string; requested_changes: JsonRecord },
): PlanningRevisionRequest {
  return {
    ...revisionRequest,
    summary: revisionRequest.summary ?? review.summary,
    requested_changes:
      revisionRequest.requested_changes ?? review.requested_changes,
  };
}

function isRecord(value: unknown): value is JsonRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

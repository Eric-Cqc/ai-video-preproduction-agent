import type {
  ApiClientError,
  ArtifactIds,
  BriefBundle,
  BriefCandidateResponse,
  CandidateReviewResponse,
  BriefExtractionRun,
  ConceptCandidate,
  ConceptRun,
  DeliveryExport,
  DeliveryPackage,
  DocumentExtraction,
  HydratedProject,
  PlanningReview,
  PlanningRevisionRequest,
  PlanningRun,
  PlanningVersion,
  Project,
  ScriptArtifact,
  SourceAsset,
  SourceAssetDetail,
  SourceObject,
} from "./api/product-client";

export const stageDefinitions = [
  { id: "upload", label: "Upload", index: "01", eyebrow: "Source" },
  { id: "parse", label: "Parse", index: "02", eyebrow: "Extraction" },
  { id: "brief", label: "Brief", index: "03", eyebrow: "Human gate" },
  { id: "concepts", label: "Concepts", index: "04", eyebrow: "Comparison" },
  { id: "script", label: "Script", index: "05", eyebrow: "Draft" },
  {
    id: "storyboard",
    label: "Storyboard",
    index: "06",
    eyebrow: "Visual plan",
  },
  { id: "shot-plan", label: "Shot Plan", index: "07", eyebrow: "Coverage" },
  { id: "review", label: "Review", index: "08", eyebrow: "Human gate" },
  { id: "delivery", label: "Delivery", index: "09", eyebrow: "Handoff" },
] as const;

export type StageId = (typeof stageDefinitions)[number]["id"];
export type StageState =
  "done" | "available" | "pending" | "failed" | "blocked";

export interface WorkspaceSnapshot {
  project: Project;
  artifacts: ArtifactIds;
  sourceAssets: SourceAsset[];
  sourceAsset: SourceAssetDetail | undefined;
  sourceObject: SourceObject | undefined;
  extraction: DocumentExtraction | undefined;
  briefRun: BriefExtractionRun | undefined;
  candidate: BriefCandidateResponse | undefined;
  briefCandidateAvailable: boolean | undefined;
  candidateReview: CandidateReviewResponse | undefined;
  brief: BriefBundle | undefined;
  conceptRun: ConceptRun | undefined;
  concepts: ConceptCandidate[];
  script: ScriptArtifact | undefined;
  storyboardRun: PlanningRun | undefined;
  storyboard: PlanningVersion | undefined;
  shotPlanRun: PlanningRun | undefined;
  shotPlan: PlanningVersion | undefined;
  reviews: PlanningReview[];
  review: PlanningReview | undefined;
  revisionRequest: PlanningRevisionRequest | undefined;
  deliveryPackage: DeliveryPackage | undefined;
  exports: DeliveryExport[];
  hydrationIssues: ApiClientError[];
  errors: Partial<Record<StageId, string>>;
  activeOperation: StageId | null;
  hasSourceFile: boolean;
}

export function fromHydratedProject(
  hydrated: HydratedProject,
  previous?: WorkspaceSnapshot,
): WorkspaceSnapshot {
  return {
    project: hydrated.project,
    artifacts: hydrated.artifacts,
    sourceAssets: hydrated.sourceAssets,
    sourceAsset: hydrated.sourceAsset,
    sourceObject: hydrated.sourceObject,
    extraction: hydrated.extraction,
    briefRun: hydrated.briefRun,
    candidate: hydrated.candidate,
    briefCandidateAvailable: hydrated.briefCandidateAvailable,
    candidateReview: hydrated.candidateReview,
    brief: hydrated.brief,
    conceptRun: hydrated.conceptRun,
    concepts: hydrated.concepts,
    script: hydrated.script,
    storyboardRun: hydrated.storyboardRun,
    storyboard: hydrated.storyboard,
    shotPlanRun: hydrated.shotPlanRun,
    shotPlan: hydrated.shotPlan,
    reviews: hydrated.reviews,
    review: hydrated.review,
    revisionRequest: hydrated.revisionRequest,
    deliveryPackage: hydrated.deliveryPackage,
    exports: hydrated.exports,
    hydrationIssues: hydrated.issues,
    errors: previous?.errors ?? {},
    activeOperation: null,
    hasSourceFile: previous?.hasSourceFile ?? false,
  };
}

export function withWorkspacePatch(
  snapshot: WorkspaceSnapshot,
  patch: Partial<WorkspaceSnapshot>,
): WorkspaceSnapshot {
  return { ...snapshot, ...patch };
}

export function stageStatuses(
  snapshot: WorkspaceSnapshot,
): Record<StageId, StageState> {
  return Object.fromEntries(
    stageDefinitions.map((stage) => [
      stage.id,
      stageStatus(snapshot, stage.id),
    ]),
  ) as Record<StageId, StageState>;
}

export function stageStatus(
  snapshot: WorkspaceSnapshot,
  stage: StageId,
): StageState {
  if (snapshot.activeOperation === stage) return "pending";
  if (snapshot.errors[stage]) return "failed";

  const uploadFailed = isFailed(snapshot.sourceObject?.state);
  const uploadDone = Boolean(snapshot.sourceObject) && !uploadFailed;
  const extractionPending = isPending(snapshot.extraction?.status);
  const briefRunPending = isPending(snapshot.briefRun?.status);
  const parseFailed =
    isFailed(snapshot.extraction?.status) ||
    isFailed(snapshot.briefRun?.status) ||
    snapshot.briefCandidateAvailable === false ||
    uploadFailed;
  const parsePending = extractionPending || briefRunPending;
  const parseDone = Boolean(snapshot.candidate);
  const briefDone = Boolean(snapshot.brief);
  const conceptsDone = Boolean(
    snapshot.artifacts.selectedConceptCandidateId &&
    snapshot.conceptRun &&
    snapshot.concepts.some(
      (candidate) =>
        candidate.id === snapshot.artifacts.selectedConceptCandidateId,
    ),
  );
  const conceptsReady = snapshot.concepts.length > 0;
  const conceptsFailed = isFailed(snapshot.conceptRun?.status);
  const conceptsPending = isPending(snapshot.conceptRun?.status);
  const storyboardFailed = isFailed(snapshot.storyboardRun?.status);
  const storyboardPending = isPending(snapshot.storyboardRun?.status);
  const shotPlanFailed = isFailed(snapshot.shotPlanRun?.status);
  const shotPlanPending = isPending(snapshot.shotPlanRun?.status);
  const review = latestReview(snapshot);
  const reviewApproved = review?.outcome === "approved";
  const deliveryExported = snapshot.exports.some(
    (item) => item.checksum.trim().length > 0,
  );
  const planningReady = Boolean(
    snapshot.script && snapshot.storyboard && snapshot.shotPlan,
  );

  switch (stage) {
    case "upload":
      if (uploadFailed) return "failed";
      return uploadDone ? "done" : "available";
    case "parse":
      if (parseFailed) return "failed";
      if (parsePending) return "pending";
      return parseDone ? "done" : uploadDone ? "available" : "blocked";
    case "brief":
      if (briefDone) return "done";
      if (snapshot.candidateReview?.action === "reject") return "failed";
      return snapshot.candidate
        ? "available"
        : parseFailed
          ? "blocked"
          : "blocked";
    case "concepts":
      if (conceptsDone) return "done";
      if (conceptsFailed) return "failed";
      if (conceptsPending) return "pending";
      if (conceptsReady) return "available";
      return briefDone ? "available" : "blocked";
    case "script":
      if (snapshot.script) return "done";
      return conceptsDone ? "available" : "blocked";
    case "storyboard":
      if (snapshot.storyboard) return "done";
      if (storyboardFailed) return "failed";
      if (storyboardPending) return "pending";
      return snapshot.script ? "available" : "blocked";
    case "shot-plan":
      if (snapshot.shotPlan) return "done";
      if (shotPlanFailed) return "failed";
      if (shotPlanPending) return "pending";
      return snapshot.storyboard ? "available" : "blocked";
    case "review":
      if (reviewApproved) return "done";
      return planningReady ? "available" : "blocked";
    case "delivery":
      if (deliveryExported) return "done";
      if (snapshot.deliveryPackage) return "available";
      return reviewApproved ? "available" : "blocked";
  }
}

export function latestReview(
  snapshot: WorkspaceSnapshot,
): PlanningReview | undefined {
  return (
    snapshot.review ??
    [...snapshot.reviews].sort((left, right) =>
      right.created_at.localeCompare(left.created_at),
    )[0]
  );
}

export function stageDescription(
  snapshot: WorkspaceSnapshot,
  stage: StageId,
): string {
  switch (stage) {
    case "upload":
      return snapshot.sourceObject
        ? "源文件已登记并保存。"
        : "登记一个受控的结构化制作输入。";
    case "parse":
      return snapshot.extraction?.status === "failed" ||
        snapshot.briefRun?.status === "failed" ||
        snapshot.briefCandidateAvailable === false
        ? "解析运行失败，当前没有可审查候选。"
        : snapshot.candidate
          ? "候选已生成，等待制作人审查。"
          : "把源文件解析为可审查的 Brief 候选。";
    case "brief":
      return snapshot.brief
        ? "Brief 已由制作人接受并成为版本化事实。"
        : snapshot.candidateReview?.action === "reject"
          ? "候选已被制作人拒绝；请重新执行 Parse 以产生新的候选。"
          : "阅读候选字段和要求问题，然后明确接受或拒绝。";
    case "concepts":
      return snapshot.artifacts.selectedConceptCandidateId
        ? "已记录明确的 Concept 选择。"
        : "比较全部候选，不会替你选第一张卡。";
    case "script":
      return snapshot.script
        ? "脚本版本已保存。"
        : "确认 Concept 后，显式生成脚本版本。";
    case "storyboard":
      return snapshot.storyboard
        ? "Storyboard 版本已保存。"
        : "以当前脚本为依据显式生成视觉分镜。";
    case "shot-plan":
      return snapshot.shotPlan
        ? "Shot Plan 版本已保存。"
        : "以当前 Storyboard 为依据显式生成镜头表。";
    case "review":
      if (latestReview(snapshot)?.outcome === "revision_requested") {
        if (snapshot.revisionRequest?.status === "open") {
          return "已请求修改；处理修改请求后再审查新的制作蓝图。";
        }
        if (snapshot.revisionRequest?.status === "completed") {
          return "修改已完成；请审查新的制作蓝图。";
        }
        if (snapshot.revisionRequest?.status === "cancelled") {
          return "修改请求已取消；可重新审查当前制作蓝图。";
        }
        return "已请求修改；Delivery 仍被锁定。";
      }
      return "检查完整制作蓝图，然后批准或请求修改。";
    case "delivery":
      return snapshot.deliveryPackage
        ? "交付包已创建；ZIP 仍需制作人明确生成和下载。"
        : "仅在精确的已批准规划包之后创建交付包。";
  }
}

export function stateLabel(state: StageState): string {
  return {
    done: "完成",
    available: "可操作",
    pending: "处理中",
    failed: "失败",
    blocked: "等待前置",
  }[state];
}

export function stageLabel(stage: StageId): string {
  return stageDefinitions.find((item) => item.id === stage)?.label ?? stage;
}

export function nextActionableStage(snapshot: WorkspaceSnapshot): StageId {
  const statuses = stageStatuses(snapshot);
  return (
    stageDefinitions.find((stage) => statuses[stage.id] === "available")?.id ??
    stageDefinitions.find((stage) => statuses[stage.id] === "failed")?.id ??
    stageDefinitions.find((stage) => statuses[stage.id] === "pending")?.id ??
    stageDefinitions[0].id
  );
}

function isFailed(value: string | undefined): boolean {
  return value === "failed" || value === "error";
}

function isPending(value: string | undefined): boolean {
  return (
    value === "pending" ||
    value === "queued" ||
    value === "running" ||
    value === "processing"
  );
}

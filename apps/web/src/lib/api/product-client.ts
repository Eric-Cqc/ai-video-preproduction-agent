export interface LocalWorkspaceContext {
  actorSubject: string;
  organizationId: string;
  workspaceId: string;
}

export type JsonRecord = Record<string, unknown>;

export interface Project {
  id: string;
  name: string;
  description: string | null;
  status: string;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectListResponse {
  items: Project[];
}

export interface SourceAsset {
  id: string;
  organization_id: string;
  workspace_id: string;
  project_id: string;
  display_name: string;
  status: string;
  current_version_id: string;
  latest_version_number: number;
  created_by_actor_subject: string;
  created_at: string;
  updated_at: string;
  version: number;
}

export interface SourceAssetVersion {
  id: string;
  organization_id: string;
  workspace_id: string;
  project_id: string;
  source_asset_id: string;
  version_number: number;
  original_filename: string;
  media_type: string;
  byte_size: number;
  checksum_algorithm: string;
  checksum_value: string;
  source_type: string;
  source_reference: string | null;
  external_record_id: string | null;
  declared_created_at: string | null;
  created_by_actor_subject: string;
  created_at: string;
  supersedes_version_id: string | null;
  metadata_schema_version: string;
}

export interface SourceAssetDetail {
  source_asset: SourceAsset;
  current_version: SourceAssetVersion;
}

export interface SourceAssetListResponse {
  items: SourceAsset[];
  limit: number;
  offset: number;
}

export interface SourceObject {
  id: string;
  source_asset_id: string;
  source_asset_version_id: string;
  state: string;
  observed_byte_size: number;
  created_at: string;
}

export interface DocumentExtraction {
  id: string;
  source_asset_id: string;
  source_asset_version_id: string;
  parser_id: string;
  parser_version: string;
  status: string;
  extracted_document: JsonRecord;
  character_count: number;
  warning_count: number;
  truncated: boolean;
  created_at: string;
  schema_version: string;
}

export interface DocumentExtractionMutationResponse {
  extraction: DocumentExtraction;
  replayed: boolean;
  completed_at: string;
  correlation_id: string;
}

export interface BriefExtractionRun {
  id: string;
  status: string;
  created_at: string;
}

export interface BriefCandidateResponse {
  run_id: string;
  candidate: JsonRecord;
  candidate_issues: JsonRecord[];
}

export interface BriefExtractionRunStartResponse {
  run_id: string;
  status: string;
  candidate_available: boolean;
}

export interface CandidateReviewResponse {
  review_id: string;
  action: string;
  status: string;
  brief_id: string | null;
  brief_version_id: string | null;
  replayed: boolean;
  completed_at: string | null;
}

export interface BriefSummary {
  id: string;
  organization_id: string;
  workspace_id: string;
  project_id: string;
  title: string;
  status: string;
  current_version_id: string;
  latest_version_number: number;
  created_by_actor_subject: string;
  created_at: string;
  updated_at: string;
  version: number;
}

export interface BriefVersion {
  id: string;
  organization_id: string;
  workspace_id: string;
  project_id: string;
  brief_id: string;
  version_number: number;
  lifecycle_state: string;
  structured_content: JsonRecord;
  source_type: string;
  source_reference: string | null;
  change_summary: string;
  created_by_actor_subject: string;
  created_at: string;
  submitted_for_review_at: string | null;
  approved_at: string | null;
  approved_by_actor_subject: string | null;
  supersedes_version_id: string | null;
  content_schema_version: string;
}

export interface RequirementIssue {
  id: string;
  organization_id: string;
  workspace_id: string;
  project_id: string;
  brief_id: string;
  brief_version_id: string;
  issue_type: string;
  field_path: string;
  severity: string;
  message: string;
  status: string;
  resolution_note: string | null;
  created_by_actor_subject: string;
  resolved_by_actor_subject: string | null;
  created_at: string;
  resolved_at: string | null;
  version: number;
}

export interface BriefBundle {
  brief: BriefSummary;
  current_version: BriefVersion;
  issues: RequirementIssue[];
}

export interface BriefListResponse {
  items: BriefSummary[];
}

export interface ConceptRun {
  id: string;
  status: string;
  brief_id: string;
  brief_version_id: string;
  created_at: string;
  completed_at: string | null;
}

export interface ConceptCandidate {
  id: string;
  candidate_index: number;
  content: JsonRecord;
  created_at: string;
}

export interface ConceptGenerationResponse {
  run: ConceptRun;
  candidates: ConceptCandidate[];
  replayed: boolean;
}

export interface ConceptCandidatesResponse {
  items: ConceptCandidate[];
}

export interface ConceptSelectionResponse {
  selection_id: string;
  candidate_id: string;
  replayed: boolean;
}

export interface ScriptArtifact {
  id: string;
  content: JsonRecord;
  brief_version_id: string;
  concept_candidate_id: string;
  concept_selection_id: string;
}

export interface ScriptGenerationResponse {
  script_version_id: string;
  content: JsonRecord;
  replayed: boolean;
}

export interface PlanningRun {
  id: string;
  status: string;
  created_at: string;
  completed_at: string | null;
  brief_id: string;
  script_version_id: string;
  brief_version_id: string;
  concept_run_id: string;
  concept_candidate_id: string;
  concept_selection_id: string;
  script_run_id: string;
  storyboard_run_id?: string | null;
  storyboard_version_id?: string | null;
}

export interface PlanningVersion {
  id: string;
  storyboard_run_id: string;
  storyboard_version_id?: string | null;
  shot_plan_run_id?: string | null;
  brief_id: string;
  brief_version_id: string;
  concept_run_id: string;
  concept_candidate_id: string;
  concept_selection_id: string;
  script_run_id: string;
  script_version_id: string;
  version_number: number;
  schema_version: string;
  content: JsonRecord;
  total_duration_seconds: number;
  scene_count: number;
  shot_count?: number;
  created_at: string;
}

export interface PlanningGenerationResponse {
  run: PlanningRun;
  version: PlanningVersion;
  replayed: boolean;
}

export interface PlanningReview {
  id: string;
  artifact_type: string;
  script_version_id: string | null;
  storyboard_version_id: string | null;
  shot_plan_version_id: string | null;
  review_round: number;
  outcome: string;
  summary: string;
  requested_changes: JsonRecord;
  reviewed_by_actor_subject: string;
  reviewed_at: string;
  created_at: string;
}

export interface PlanningRevisionRequest {
  id: string;
  review_id: string;
  artifact_type: string;
  source_script_version_id: string | null;
  source_storyboard_version_id: string | null;
  source_shot_plan_version_id: string | null;
  status: string;
  created_at: string;
  completed_at: string | null;
  successor_script_version_id: string | null;
  successor_storyboard_version_id: string | null;
  successor_shot_plan_version_id: string | null;
  /** Present when the response is enriched from its originating review. */
  summary?: string;
  /** The current backend serializer omits this; the review carries it. */
  requested_changes?: JsonRecord;
}

export interface PlanningReviewResponse {
  review: PlanningReview;
  revision_request: PlanningRevisionRequest | null;
  replayed: boolean;
}

export interface RevisionCompleteResponse {
  revision_request: PlanningRevisionRequest;
  successor_script_version_id: string | null;
  successor_storyboard_version_id: string | null;
  successor_shot_plan_version_id: string | null;
  replayed: boolean;
}

export interface DeliveryPackage {
  id: string;
  delivery_package_id: string;
  version_number: number;
  script_version_id: string;
  storyboard_version_id: string;
  shot_plan_version_id: string;
  approval_review_id: string;
  manifest_schema_version: string;
  manifest: JsonRecord;
  manifest_digest: string;
  created_at: string;
}

export interface DeliveryPackageResponse {
  package: DeliveryPackage;
  replayed: boolean;
}

export interface DeliveryExport {
  id: string;
  format: string;
  filename: string;
  checksum: string;
  byte_size: number;
  created_at: string;
}

export interface DeliveryExportsResponse {
  items: DeliveryExport[];
}

export interface DownloadedExport {
  blob: Blob;
  filename: string;
}

export interface ArtifactIds {
  sourceAssetId?: string;
  sourceAssetVersionId?: string;
  sourceObjectId?: string;
  extractionId?: string;
  briefRunId?: string;
  briefCandidateReviewId?: string;
  briefCandidateReviewAction?: "accept" | "reject";
  briefId?: string;
  briefVersionId?: string;
  conceptRunId?: string;
  conceptCandidateIds?: string[];
  selectedConceptCandidateId?: string;
  conceptSelectionId?: string;
  scriptVersionId?: string;
  storyboardRunId?: string;
  storyboardVersionId?: string;
  shotPlanRunId?: string;
  shotPlanVersionId?: string;
  reviewId?: string;
  revisionRequestId?: string;
  deliveryPackageVersionId?: string;
  exportId?: string;
}

/**
 * These are resumable browser operation handles, not artifact content. They
 * are kept separate from the artifact ledger so the ledger remains ID-led.
 */
export interface ResumeOperationKeys {
  conceptSelection?: string | undefined;
  briefCandidateAvailable?: boolean | undefined;
}

export function operationStorageKey(
  context: LocalWorkspaceContext,
  projectId: string,
): string {
  return [
    "production-desk-operation-keys",
    context.organizationId,
    context.workspaceId,
    projectId,
  ]
    .map((value) => encodeURIComponent(value))
    .join(":");
}

export function readResumeOperationKeys(
  storage: Pick<Storage, "getItem">,
  key: string,
): ResumeOperationKeys {
  const saved = storage.getItem(key);
  if (!saved) return {};
  try {
    const value: unknown = JSON.parse(saved);
    if (!isRecord(value)) return {};
    const result: ResumeOperationKeys = {};
    if (
      typeof value.conceptSelection === "string" &&
      value.conceptSelection.length > 0
    ) {
      result.conceptSelection = value.conceptSelection;
    }
    if (typeof value.briefCandidateAvailable === "boolean") {
      result.briefCandidateAvailable = value.briefCandidateAvailable;
    }
    return result;
  } catch {
    return {};
  }
}

export function writeResumeOperationKeys(
  storage: Pick<Storage, "setItem">,
  key: string,
  operationKeys: ResumeOperationKeys,
): void {
  storage.setItem(key, JSON.stringify(operationKeys));
}

export interface ApiErrorEnvelope {
  code: string;
  message: string;
  correlation_id: string;
}

export class ApiClientError extends Error {
  readonly status: number;
  readonly code: string;
  readonly correlationId: string | undefined;
  readonly recovery: string | undefined;

  constructor(
    status: number,
    details: Partial<ApiErrorEnvelope> & { correlationId?: string } = {},
  ) {
    super(details.message ?? `Local API request failed (${status})`);
    this.name = "ApiClientError";
    this.status = status;
    this.code = details.code ?? "http_error";
    this.correlationId = details.correlationId ?? details.correlation_id;
    this.recovery =
      status === 409
        ? "刷新项目状态后重试；如果仍需执行，请重新开始当前操作以生成新的操作键。"
        : undefined;
  }

  get isConflict(): boolean {
    return this.status === 409;
  }
}

export function parseApiErrorEnvelope(
  payload: unknown,
  fallbackCorrelationId?: string,
): ApiErrorEnvelope {
  const root =
    isRecord(payload) && isRecord(payload.error) ? payload.error : payload;
  return {
    code:
      isRecord(root) && typeof root.code === "string"
        ? root.code
        : "http_error",
    message:
      isRecord(root) && typeof root.message === "string"
        ? root.message
        : "操作未完成。请稍后重试。",
    correlation_id:
      isRecord(root) && typeof root.correlation_id === "string"
        ? root.correlation_id
        : (fallbackCorrelationId ?? "未提供"),
  };
}

export function createOperationKey(scope: string): string {
  const normalizedScope =
    scope.replace(/[^A-Za-z0-9._-]/g, "-").slice(0, 48) || "operation";
  const runId =
    globalThis.crypto?.randomUUID?.() ??
    `${Date.now().toString(36)}-${operationSequence++}`;
  return `${normalizedScope}-${runId}`.slice(0, 128);
}

export function artifactStorageKey(
  context: LocalWorkspaceContext,
  projectId: string,
): string {
  return [
    "production-desk-artifacts",
    context.organizationId,
    context.workspaceId,
    projectId,
  ]
    .map((value) => encodeURIComponent(value))
    .join(":");
}

export function readArtifactIds(
  storage: Pick<Storage, "getItem">,
  key: string,
): ArtifactIds {
  const saved = storage.getItem(key);
  if (!saved) return {};
  try {
    const value: unknown = JSON.parse(saved);
    if (!isRecord(value)) return {};
    return normalizeArtifactIds(value);
  } catch {
    return {};
  }
}

export function writeArtifactIds(
  storage: Pick<Storage, "setItem">,
  key: string,
  ids: ArtifactIds,
): void {
  storage.setItem(key, JSON.stringify(ids));
}

type ProductFetcher = (input: URL, init?: RequestInit) => Promise<Response>;

export interface HydratedProject {
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
  briefs: BriefSummary[];
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
  issues: ApiClientError[];
}

export interface ProductClient {
  listProjects(): Promise<ProjectListResponse>;
  getProject(projectId: string): Promise<Project>;
  hydrateProject(
    projectId: string,
    artifactIds: ArtifactIds,
  ): Promise<HydratedProject>;
  listSourceAssets(projectId: string): Promise<SourceAssetListResponse>;
  getSourceAsset(
    projectId: string,
    sourceAssetId: string,
  ): Promise<SourceAssetDetail>;
  getSourceObject(
    projectId: string,
    sourceAssetId: string,
    sourceAssetVersionId: string,
  ): Promise<SourceObject>;
  createProject(input: {
    name: string;
    description: string | null;
    idempotencyKey: string;
  }): Promise<Project>;
  createSourceAsset(input: {
    projectId: string;
    displayName: string;
    originalFilename: string;
    mediaType: string;
    byteSize: number;
    checksum: string;
    idempotencyKey?: string;
  }): Promise<SourceAssetDetail & { operation: JsonRecord }>;
  uploadSourceObject(input: {
    projectId: string;
    sourceAssetId: string;
    sourceAssetVersionId: string;
    bytes: ArrayBuffer;
    idempotencyKey?: string;
  }): Promise<{ source_object: SourceObject; replayed: boolean }>;
  createDocumentExtraction(input: {
    projectId: string;
    sourceAssetId: string;
    sourceAssetVersionId: string;
    idempotencyKey?: string;
  }): Promise<DocumentExtractionMutationResponse>;
  extractBriefCandidate(input: {
    projectId: string;
    sourceAssetId: string;
    sourceAssetVersionId: string;
    extractionId: string;
    idempotencyKey?: string;
  }): Promise<BriefExtractionRunStartResponse>;
  getBriefExtractionRun(
    projectId: string,
    runId: string,
  ): Promise<BriefExtractionRun>;
  getBriefCandidate(
    projectId: string,
    runId: string,
  ): Promise<BriefCandidateResponse>;
  acceptBriefCandidate(input: {
    projectId: string;
    runId: string;
    acceptedContent: JsonRecord;
    title: string;
    idempotencyKey?: string;
  }): Promise<CandidateReviewResponse>;
  rejectBriefCandidate(input: {
    projectId: string;
    runId: string;
    reason: string;
    note: string | null;
    idempotencyKey?: string;
  }): Promise<CandidateReviewResponse>;
  listBriefs(projectId: string): Promise<BriefListResponse>;
  getBrief(projectId: string, briefId: string): Promise<BriefBundle>;
  generateConcepts(input: {
    projectId: string;
    briefId: string;
    briefVersionId: string;
    idempotencyKey?: string;
  }): Promise<ConceptGenerationResponse>;
  getConceptRun(projectId: string, conceptRunId: string): Promise<ConceptRun>;
  listConceptCandidates(
    projectId: string,
    conceptRunId: string,
  ): Promise<ConceptCandidatesResponse>;
  selectConcept(input: {
    projectId: string;
    conceptRunId: string;
    candidateId: string;
    idempotencyKey?: string;
  }): Promise<ConceptSelectionResponse>;
  generateScript(input: {
    projectId: string;
    conceptRunId: string;
    idempotencyKey?: string;
  }): Promise<ScriptGenerationResponse>;
  getScript(
    projectId: string,
    scriptVersionId: string,
  ): Promise<ScriptArtifact>;
  generateStoryboard(input: {
    projectId: string;
    scriptVersionId: string;
    idempotencyKey?: string;
  }): Promise<PlanningGenerationResponse>;
  getStoryboardRun(
    projectId: string,
    storyboardRunId: string,
  ): Promise<PlanningRun>;
  getStoryboardVersion(
    projectId: string,
    storyboardVersionId: string,
  ): Promise<PlanningVersion>;
  generateShotPlan(input: {
    projectId: string;
    storyboardVersionId: string;
    idempotencyKey?: string;
  }): Promise<PlanningGenerationResponse>;
  getShotPlanRun(
    projectId: string,
    shotPlanRunId: string,
  ): Promise<PlanningRun>;
  getShotPlanVersion(
    projectId: string,
    shotPlanVersionId: string,
  ): Promise<PlanningVersion>;
  listReviews(projectId: string): Promise<{ items: PlanningReview[] }>;
  getReview(projectId: string, reviewId: string): Promise<PlanningReview>;
  getRevisionRequest(
    projectId: string,
    revisionRequestId: string,
  ): Promise<PlanningRevisionRequest>;
  submitPlanningReview(input: {
    projectId: string;
    scriptVersionId: string;
    storyboardVersionId: string;
    shotPlanVersionId: string;
    outcome: "approved" | "revision_requested" | "rejected";
    summary: string;
    requestedChanges: JsonRecord;
    idempotencyKey?: string;
  }): Promise<PlanningReviewResponse>;
  completeRevision(input: {
    projectId: string;
    revisionRequestId: string;
    providerMode?: "valid";
    idempotencyKey?: string;
  }): Promise<RevisionCompleteResponse>;
  cancelRevision(input: {
    projectId: string;
    revisionRequestId: string;
    idempotencyKey?: string;
  }): Promise<{ revision_request: PlanningRevisionRequest }>;
  createDeliveryPackage(input: {
    projectId: string;
    scriptVersionId: string;
    storyboardVersionId: string;
    shotPlanVersionId: string;
    approvalReviewId: string;
    idempotencyKey?: string;
  }): Promise<DeliveryPackageResponse>;
  getDeliveryPackage(
    projectId: string,
    deliveryPackageVersionId: string,
  ): Promise<DeliveryPackage>;
  listExports(
    projectId: string,
    deliveryPackageVersionId: string,
  ): Promise<DeliveryExportsResponse>;
  exportDeliveryPackage(input: {
    projectId: string;
    deliveryPackageVersionId: string;
    idempotencyKey?: string;
  }): Promise<{ export: DeliveryExport; replayed: boolean }>;
  downloadExport(
    projectId: string,
    exportId: string,
    filename: string,
  ): Promise<DownloadedExport>;
}

const retryableStatuses = new Set([502, 503, 504]);
let operationSequence = 0;

export function createProductClient(
  baseUrl: string,
  context: LocalWorkspaceContext,
  fetcher: ProductFetcher = (input, init) => fetch(input, init),
  useTemporaryHeaders = true,
): ProductClient {
  const workspacePath = `/api/v1/organizations/${encodeURIComponent(context.organizationId)}/workspaces/${encodeURIComponent(context.workspaceId)}`;
  const projectPath = (projectId: string) =>
    `${workspacePath}/projects/${encodeURIComponent(projectId)}`;

  const headersFor = (init: RequestInit, idempotencyKey?: string): Headers => {
    const headers = new Headers(init.headers);
    headers.set("accept", "application/json");
    if (useTemporaryHeaders) {
      headers.set("X-Actor-Subject", context.actorSubject);
      headers.set("X-Organization-Id", context.organizationId);
      headers.set("X-Workspace-Id", context.workspaceId);
    }
    if (idempotencyKey) headers.set("Idempotency-Key", idempotencyKey);
    return headers;
  };

  const errorFromResponse = async (
    response: Response,
  ): Promise<ApiClientError> => {
    let payload: unknown;
    try {
      payload = await response.clone().json();
    } catch {
      payload = undefined;
    }
    const envelope = parseApiErrorEnvelope(
      payload,
      response.headers.get("x-correlation-id") ?? undefined,
    );
    return new ApiClientError(response.status, envelope);
  };

  const request = async <T>(
    path: string,
    init: RequestInit = {},
    retry = init.method === undefined || init.method === "GET",
  ): Promise<T> => {
    const controller = new AbortController();
    const timeout = globalThis.setTimeout(() => controller.abort(), 8_000);
    const requestInit: RequestInit = {
      ...init,
      headers: headersFor(init),
      cache: "no-store",
      signal: controller.signal,
    };
    try {
      let response = await fetcher(new URL(path, baseUrl), requestInit);
      if (retry && retryableStatuses.has(response.status)) {
        response = await fetcher(new URL(path, baseUrl), {
          ...init,
          headers: headersFor(init),
          cache: "no-store",
        });
      }
      if (!response.ok) throw await errorFromResponse(response);
      if (response.status === 204) return undefined as T;
      return (await response.json()) as T;
    } finally {
      globalThis.clearTimeout(timeout);
    }
  };

  const mutation = <T>(
    path: string,
    body: JsonRecord,
    idempotencyKey?: string,
  ): Promise<T> => {
    const key = idempotencyKey ?? createOperationKey(path);
    return request<T>(
      path,
      {
        method: "POST",
        headers: { "content-type": "application/json", "Idempotency-Key": key },
        body: JSON.stringify(body),
      },
      false,
    );
  };

  const optional = async <T>(
    operation: () => Promise<T>,
    issues: ApiClientError[],
    onNotFound?: () => void,
  ): Promise<T | undefined> => {
    try {
      return await operation();
    } catch (error) {
      if (error instanceof ApiClientError && error.status === 404) {
        onNotFound?.();
        return undefined;
      }
      if (error instanceof ApiClientError) issues.push(error);
      else throw error;
      return undefined;
    }
  };

  const hydrateProject = async (
    projectId: string,
    artifactIds: ArtifactIds,
  ): Promise<HydratedProject> => {
    const issues: ApiClientError[] = [];
    const [project, sourceAssetList, briefList, reviewList] = await Promise.all(
      [
        request<Project>(projectPath(projectId)),
        request<SourceAssetListResponse>(
          `${projectPath(projectId)}/source-assets`,
        ),
        request<BriefListResponse>(`${projectPath(projectId)}/briefs`),
        request<{ items: PlanningReview[] }>(
          `${projectPath(projectId)}/planning-reviews`,
        ),
      ],
    );
    let artifacts: ArtifactIds = { ...artifactIds };
    const dropArtifacts = (...fields: (keyof ArtifactIds)[]) => {
      const next = { ...artifacts };
      for (const field of fields) delete next[field];
      artifacts = next;
    };
    const storedSourceAssetId = artifacts.sourceAssetId;
    const latestSource = [...sourceAssetList.items].sort((left, right) =>
      right.updated_at.localeCompare(left.updated_at),
    )[0];
    if (!artifacts.sourceAssetId && latestSource) {
      artifacts = {
        ...artifacts,
        sourceAssetId: latestSource.id,
        sourceAssetVersionId: latestSource.current_version_id,
      };
    }
    const storedReviewId = artifacts.reviewId;
    const latestReview = [...reviewList.items].sort((left, right) =>
      right.created_at.localeCompare(left.created_at),
    )[0];
    const applyReviewArtifacts = (reviewToApply: PlanningReview) => {
      const nextArtifacts: ArtifactIds = {
        ...artifacts,
        reviewId: reviewToApply.id,
      };
      if (!nextArtifacts.scriptVersionId && reviewToApply.script_version_id) {
        nextArtifacts.scriptVersionId = reviewToApply.script_version_id;
      }
      if (
        !nextArtifacts.storyboardVersionId &&
        reviewToApply.storyboard_version_id
      ) {
        nextArtifacts.storyboardVersionId = reviewToApply.storyboard_version_id;
      }
      if (
        !nextArtifacts.shotPlanVersionId &&
        reviewToApply.shot_plan_version_id
      ) {
        nextArtifacts.shotPlanVersionId = reviewToApply.shot_plan_version_id;
      }
      artifacts = nextArtifacts;
    };
    if (!artifacts.reviewId && latestReview) {
      applyReviewArtifacts(latestReview);
    }

    let sourceAsset =
      artifacts.sourceAssetId === undefined
        ? undefined
        : await optional(
            () => getSourceAsset(projectId, artifacts.sourceAssetId as string),
            issues,
            () =>
              dropArtifacts(
                "sourceAssetId",
                "sourceAssetVersionId",
                "sourceObjectId",
                "extractionId",
              ),
          );
    if (
      !sourceAsset &&
      storedSourceAssetId &&
      artifacts.sourceAssetId === undefined &&
      latestSource
    ) {
      artifacts = {
        ...artifacts,
        sourceAssetId: latestSource.id,
        sourceAssetVersionId: latestSource.current_version_id,
      };
      sourceAsset = await optional(
        () => getSourceAsset(projectId, latestSource.id),
        issues,
        () =>
          dropArtifacts(
            "sourceAssetId",
            "sourceAssetVersionId",
            "sourceObjectId",
            "extractionId",
          ),
      );
    }
    const storedSourceVersionId = artifacts.sourceAssetVersionId;
    let sourceVersionId =
      artifacts.sourceAssetVersionId ?? sourceAsset?.current_version.id;
    if (sourceVersionId && !artifacts.sourceAssetVersionId) {
      artifacts = { ...artifacts, sourceAssetVersionId: sourceVersionId };
    }
    let sourceObject =
      artifacts.sourceAssetId && sourceVersionId
        ? await optional(
            () =>
              getSourceObject(
                projectId,
                artifacts.sourceAssetId as string,
                sourceVersionId as string,
              ),
            issues,
            () => dropArtifacts("sourceObjectId"),
          )
        : undefined;
    if (
      !sourceObject &&
      sourceAsset &&
      storedSourceVersionId &&
      storedSourceVersionId !== sourceAsset.current_version.id
    ) {
      sourceVersionId = sourceAsset.current_version.id;
      artifacts = { ...artifacts, sourceAssetVersionId: sourceVersionId };
      sourceObject =
        artifacts.sourceAssetId && sourceVersionId
          ? await optional(
              () =>
                getSourceObject(
                  projectId,
                  artifacts.sourceAssetId as string,
                  sourceVersionId as string,
                ),
              issues,
              () => dropArtifacts("sourceObjectId"),
            )
          : undefined;
    }
    if (sourceObject && !artifacts.sourceObjectId) {
      artifacts = { ...artifacts, sourceObjectId: sourceObject.id };
    }
    if (
      artifacts.extractionId !== undefined &&
      (artifacts.sourceAssetId === undefined || sourceVersionId === undefined)
    ) {
      dropArtifacts("extractionId");
    }
    const extraction =
      artifacts.extractionId === undefined
        ? undefined
        : await optional(
            () =>
              getDocumentExtraction(
                projectId,
                artifacts.sourceAssetId as string,
                sourceVersionId as string,
                artifacts.extractionId as string,
              ),
            issues,
            () => dropArtifacts("extractionId"),
          );
    const briefRun =
      artifacts.briefRunId === undefined
        ? undefined
        : await optional(
            () =>
              getBriefExtractionRun(projectId, artifacts.briefRunId as string),
            issues,
            () =>
              dropArtifacts(
                "briefRunId",
                "briefCandidateReviewId",
                "briefCandidateReviewAction",
              ),
          );
    const candidate =
      artifacts.briefRunId === undefined || briefRun?.status === "failed"
        ? undefined
        : await optional(
            () => getBriefCandidate(projectId, artifacts.briefRunId as string),
            issues,
          );

    const storedBriefId = artifacts.briefId;
    let brief =
      artifacts.briefId === undefined
        ? undefined
        : await optional(
            () => getBrief(projectId, artifacts.briefId as string),
            issues,
            () =>
              dropArtifacts(
                "briefId",
                "briefVersionId",
                "conceptRunId",
                "conceptCandidateIds",
                "selectedConceptCandidateId",
                "conceptSelectionId",
                "scriptVersionId",
                "storyboardRunId",
                "storyboardVersionId",
                "shotPlanRunId",
                "shotPlanVersionId",
                "reviewId",
                "revisionRequestId",
                "deliveryPackageVersionId",
                "exportId",
              ),
          );
    if (
      !brief &&
      storedBriefId &&
      artifacts.briefId === undefined &&
      briefList.items.length > 0
    ) {
      const latestBrief = [...briefList.items].sort((left, right) =>
        right.updated_at.localeCompare(left.updated_at),
      )[0];
      if (latestBrief) {
        artifacts = {
          ...artifacts,
          briefId: latestBrief.id,
          briefVersionId: latestBrief.current_version_id,
        };
        brief = await optional(
          () => getBrief(projectId, latestBrief.id),
          issues,
          () => dropArtifacts("briefId", "briefVersionId"),
        );
      }
    }
    if (brief) {
      artifacts = {
        ...artifacts,
        briefVersionId: brief.current_version.id,
      };
    }

    const conceptRun =
      artifacts.conceptRunId === undefined
        ? undefined
        : await optional(
            () => getConceptRun(projectId, artifacts.conceptRunId as string),
            issues,
            () =>
              dropArtifacts(
                "conceptRunId",
                "conceptCandidateIds",
                "selectedConceptCandidateId",
                "conceptSelectionId",
                "scriptVersionId",
                "storyboardRunId",
                "storyboardVersionId",
                "shotPlanRunId",
                "shotPlanVersionId",
                "reviewId",
                "revisionRequestId",
                "deliveryPackageVersionId",
                "exportId",
              ),
          );
    const conceptResponse =
      artifacts.conceptRunId === undefined
        ? undefined
        : await optional(
            () =>
              listConceptCandidates(
                projectId,
                artifacts.conceptRunId as string,
              ),
            issues,
            () =>
              dropArtifacts(
                "conceptCandidateIds",
                "selectedConceptCandidateId",
                "conceptSelectionId",
              ),
          );
    const concepts = conceptResponse?.items ?? [];
    if (concepts.length > 0) {
      artifacts = {
        ...artifacts,
        conceptCandidateIds: concepts.map((candidateItem) => candidateItem.id),
      };
    } else if (artifacts.conceptCandidateIds) {
      dropArtifacts(
        "conceptCandidateIds",
        "selectedConceptCandidateId",
        "conceptSelectionId",
      );
    }

    const script =
      artifacts.scriptVersionId === undefined
        ? undefined
        : await optional(
            () => getScript(projectId, artifacts.scriptVersionId as string),
            issues,
            () =>
              dropArtifacts(
                "scriptVersionId",
                "storyboardRunId",
                "storyboardVersionId",
                "shotPlanRunId",
                "shotPlanVersionId",
                "reviewId",
                "revisionRequestId",
                "deliveryPackageVersionId",
                "exportId",
              ),
          );
    const storyboardRun =
      artifacts.storyboardRunId === undefined
        ? undefined
        : await optional(
            () =>
              getStoryboardRun(projectId, artifacts.storyboardRunId as string),
            issues,
            () =>
              dropArtifacts(
                "storyboardRunId",
                "storyboardVersionId",
                "shotPlanRunId",
                "shotPlanVersionId",
                "reviewId",
                "revisionRequestId",
                "deliveryPackageVersionId",
                "exportId",
              ),
          );
    const storyboardVersionId =
      artifacts.storyboardVersionId ??
      storyboardRun?.storyboard_version_id ??
      undefined;
    if (storyboardVersionId && !artifacts.storyboardVersionId) {
      artifacts = { ...artifacts, storyboardVersionId };
    }
    const storyboard =
      storyboardVersionId === undefined
        ? undefined
        : await optional(
            () => getStoryboardVersion(projectId, storyboardVersionId),
            issues,
            () =>
              dropArtifacts(
                "storyboardVersionId",
                "shotPlanRunId",
                "shotPlanVersionId",
                "reviewId",
                "revisionRequestId",
                "deliveryPackageVersionId",
                "exportId",
              ),
          );
    const shotPlanRun =
      artifacts.shotPlanRunId === undefined
        ? undefined
        : await optional(
            () => getShotPlanRun(projectId, artifacts.shotPlanRunId as string),
            issues,
            () =>
              dropArtifacts(
                "shotPlanRunId",
                "shotPlanVersionId",
                "reviewId",
                "revisionRequestId",
                "deliveryPackageVersionId",
                "exportId",
              ),
          );
    const shotPlan =
      artifacts.shotPlanVersionId === undefined
        ? undefined
        : await optional(
            () =>
              getShotPlanVersion(
                projectId,
                artifacts.shotPlanVersionId as string,
              ),
            issues,
            () =>
              dropArtifacts(
                "shotPlanVersionId",
                "reviewId",
                "revisionRequestId",
                "deliveryPackageVersionId",
                "exportId",
              ),
          );

    let review =
      artifacts.reviewId === undefined
        ? undefined
        : await optional(
            () => getReview(projectId, artifacts.reviewId as string),
            issues,
            () => dropArtifacts("reviewId", "revisionRequestId"),
          );
    if (
      !review &&
      storedReviewId &&
      artifacts.reviewId === undefined &&
      latestReview
    ) {
      applyReviewArtifacts(latestReview);
      review = latestReview;
    }
    const revisionRequest =
      artifacts.revisionRequestId === undefined
        ? undefined
        : await optional(
            () =>
              getRevisionRequest(
                projectId,
                artifacts.revisionRequestId as string,
              ),
            issues,
            () => dropArtifacts("revisionRequestId"),
          );
    const deliveryPackage =
      artifacts.deliveryPackageVersionId === undefined
        ? undefined
        : await optional(
            () =>
              getDeliveryPackage(
                projectId,
                artifacts.deliveryPackageVersionId as string,
              ),
            issues,
            () => dropArtifacts("deliveryPackageVersionId", "exportId"),
          );
    const exportsResponse = deliveryPackage
      ? await optional(
          () => listExports(projectId, deliveryPackage.id),
          issues,
          () => dropArtifacts("exportId"),
        )
      : undefined;
    const exports = exportsResponse?.items ?? [];
    if (
      !deliveryPackage ||
      (artifacts.exportId &&
        !exports.some((item) => item.id === artifacts.exportId))
    ) {
      dropArtifacts("exportId");
    }
    return {
      project,
      artifacts,
      sourceAssets: sourceAssetList.items,
      sourceAsset,
      sourceObject,
      extraction,
      briefRun,
      candidate,
      briefCandidateAvailable: candidate
        ? true
        : briefRun?.status === "failed"
          ? false
          : undefined,
      candidateReview: undefined,
      briefs: briefList.items,
      brief,
      conceptRun,
      concepts,
      script,
      storyboardRun,
      storyboard,
      shotPlanRun,
      shotPlan,
      reviews: reviewList.items,
      review,
      revisionRequest,
      deliveryPackage,
      exports,
      issues,
    };
  };

  const listProjects = () =>
    request<ProjectListResponse>(`${workspacePath}/projects`);
  const getProject = (projectId: string) =>
    request<Project>(projectPath(projectId));
  const listSourceAssets = (projectId: string) =>
    request<SourceAssetListResponse>(`${projectPath(projectId)}/source-assets`);
  const getSourceAsset = (projectId: string, sourceAssetId: string) =>
    request<SourceAssetDetail>(
      `${projectPath(projectId)}/source-assets/${encodeURIComponent(sourceAssetId)}`,
    );
  const getSourceObject = (
    projectId: string,
    sourceAssetId: string,
    sourceAssetVersionId: string,
  ) =>
    request<SourceObject>(
      `${projectPath(projectId)}/source-assets/${encodeURIComponent(sourceAssetId)}/versions/${encodeURIComponent(sourceAssetVersionId)}/object`,
    );
  const getDocumentExtraction = (
    projectId: string,
    sourceAssetId: string,
    sourceAssetVersionId: string,
    extractionId: string,
  ) =>
    request<DocumentExtraction>(
      `${projectPath(projectId)}/source-assets/${encodeURIComponent(sourceAssetId)}/versions/${encodeURIComponent(sourceAssetVersionId)}/extractions/${encodeURIComponent(extractionId)}`,
    );
  const getBriefExtractionRun = (projectId: string, runId: string) =>
    request<BriefExtractionRun>(
      `${projectPath(projectId)}/brief-extraction-runs/${encodeURIComponent(runId)}`,
    );
  const getBriefCandidate = (projectId: string, runId: string) =>
    request<BriefCandidateResponse>(
      `${projectPath(projectId)}/brief-extraction-runs/${encodeURIComponent(runId)}/candidate`,
    );
  const getBrief = (projectId: string, briefId: string) =>
    request<BriefBundle>(
      `${projectPath(projectId)}/briefs/${encodeURIComponent(briefId)}`,
    );
  const listBriefs = (projectId: string) =>
    request<BriefListResponse>(`${projectPath(projectId)}/briefs`);
  const getConceptRun = (projectId: string, conceptRunId: string) =>
    request<ConceptRun>(
      `${projectPath(projectId)}/concept-runs/${encodeURIComponent(conceptRunId)}`,
    );
  const listConceptCandidates = (projectId: string, conceptRunId: string) =>
    request<ConceptCandidatesResponse>(
      `${projectPath(projectId)}/concept-runs/${encodeURIComponent(conceptRunId)}/candidates`,
    );
  const getScript = (projectId: string, scriptVersionId: string) =>
    request<ScriptArtifact>(
      `${projectPath(projectId)}/scripts/${encodeURIComponent(scriptVersionId)}`,
    );
  const getStoryboardRun = (projectId: string, storyboardRunId: string) =>
    request<{ run: PlanningRun }>(
      `${projectPath(projectId)}/storyboard-runs/${encodeURIComponent(storyboardRunId)}`,
    ).then((response) => response.run);
  const getStoryboardVersion = (
    projectId: string,
    storyboardVersionId: string,
  ) =>
    request<{ version: PlanningVersion }>(
      `${projectPath(projectId)}/storyboards/${encodeURIComponent(storyboardVersionId)}`,
    ).then((response) => response.version);
  const getShotPlanRun = (projectId: string, shotPlanRunId: string) =>
    request<{ run: PlanningRun }>(
      `${projectPath(projectId)}/shot-plan-runs/${encodeURIComponent(shotPlanRunId)}`,
    ).then((response) => response.run);
  const getShotPlanVersion = (projectId: string, shotPlanVersionId: string) =>
    request<{ version: PlanningVersion }>(
      `${projectPath(projectId)}/shot-plans/${encodeURIComponent(shotPlanVersionId)}`,
    ).then((response) => response.version);
  const listReviews = (projectId: string) =>
    request<{ items: PlanningReview[] }>(
      `${projectPath(projectId)}/planning-reviews`,
    );
  const getReview = (projectId: string, reviewId: string) =>
    request<{ review: PlanningReview }>(
      `${projectPath(projectId)}/planning-reviews/${encodeURIComponent(reviewId)}`,
    ).then((response) => response.review);
  const getRevisionRequest = (projectId: string, revisionRequestId: string) =>
    request<{ revision_request: PlanningRevisionRequest }>(
      `${projectPath(projectId)}/revision-requests/${encodeURIComponent(revisionRequestId)}`,
    ).then((response) => response.revision_request);
  const completeRevision = ({
    projectId,
    revisionRequestId,
    providerMode = "valid",
    idempotencyKey,
  }: {
    projectId: string;
    revisionRequestId: string;
    providerMode?: "valid";
    idempotencyKey?: string;
  }) =>
    mutation<RevisionCompleteResponse>(
      `${projectPath(projectId)}/revision-requests/${encodeURIComponent(revisionRequestId)}/complete`,
      { provider_mode: providerMode },
      idempotencyKey,
    );
  const cancelRevision = ({
    projectId,
    revisionRequestId,
    idempotencyKey,
  }: {
    projectId: string;
    revisionRequestId: string;
    idempotencyKey?: string;
  }) =>
    mutation<{ revision_request: PlanningRevisionRequest }>(
      `${projectPath(projectId)}/revision-requests/${encodeURIComponent(revisionRequestId)}/cancel`,
      {},
      idempotencyKey,
    );
  const getDeliveryPackage = (
    projectId: string,
    deliveryPackageVersionId: string,
  ) =>
    request<{ package: DeliveryPackage }>(
      `${projectPath(projectId)}/delivery-packages/${encodeURIComponent(deliveryPackageVersionId)}`,
    ).then((response) => response.package);
  const listExports = (projectId: string, deliveryPackageVersionId: string) =>
    request<DeliveryExportsResponse>(
      `${projectPath(projectId)}/delivery-packages/${encodeURIComponent(deliveryPackageVersionId)}/exports`,
    );

  return {
    listProjects,
    getProject,
    hydrateProject,
    listSourceAssets,
    getSourceAsset,
    getSourceObject,
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
    createSourceAsset: async ({
      projectId,
      displayName,
      originalFilename,
      mediaType,
      byteSize,
      checksum,
      idempotencyKey,
    }) => {
      const response = await mutation<{
        source_asset: SourceAsset;
        current_version: SourceAssetVersion;
        operation: JsonRecord;
      }>(
        `${projectPath(projectId)}/source-assets`,
        {
          display_name: displayName,
          original_filename: originalFilename,
          media_type: mediaType,
          byte_size: byteSize,
          checksum_algorithm: "sha256",
          checksum_value: checksum,
          source_type: "api_declared",
          source_reference: null,
          external_record_id: null,
          declared_created_at: null,
        },
        idempotencyKey,
      );
      return {
        source_asset: response.source_asset,
        current_version: response.current_version,
        operation: response.operation,
      };
    },
    uploadSourceObject: ({
      projectId,
      sourceAssetId,
      sourceAssetVersionId,
      bytes,
      idempotencyKey,
    }) =>
      request<{ source_object: SourceObject; replayed: boolean }>(
        `${projectPath(projectId)}/source-assets/${encodeURIComponent(sourceAssetId)}/versions/${encodeURIComponent(sourceAssetVersionId)}/uploads`,
        {
          method: "POST",
          headers: {
            "content-type": "application/octet-stream",
            "Idempotency-Key": idempotencyKey ?? createOperationKey("upload"),
          },
          body: bytes,
        },
        false,
      ),
    createDocumentExtraction: ({
      projectId,
      sourceAssetId,
      sourceAssetVersionId,
      idempotencyKey,
    }) =>
      mutation<DocumentExtractionMutationResponse>(
        `${projectPath(projectId)}/source-assets/${encodeURIComponent(sourceAssetId)}/versions/${encodeURIComponent(sourceAssetVersionId)}/extractions`,
        {},
        idempotencyKey,
      ),
    extractBriefCandidate: ({
      projectId,
      sourceAssetId,
      sourceAssetVersionId,
      extractionId,
      idempotencyKey,
    }) =>
      mutation<BriefExtractionRunStartResponse>(
        `${projectPath(projectId)}/source-assets/${encodeURIComponent(sourceAssetId)}/versions/${encodeURIComponent(sourceAssetVersionId)}/extractions/${encodeURIComponent(extractionId)}/brief-extraction-runs`,
        {},
        idempotencyKey,
      ),
    getBriefExtractionRun,
    getBriefCandidate,
    acceptBriefCandidate: ({
      projectId,
      runId,
      acceptedContent,
      title,
      idempotencyKey,
    }) =>
      mutation<CandidateReviewResponse>(
        `${projectPath(projectId)}/brief-extraction-runs/${encodeURIComponent(runId)}/accept`,
        {
          brief_id: null,
          expected_brief_version: null,
          expected_current_version_id: null,
          accepted_content: acceptedContent,
          title,
        },
        idempotencyKey,
      ),
    rejectBriefCandidate: ({
      projectId,
      runId,
      reason,
      note,
      idempotencyKey,
    }) =>
      mutation<CandidateReviewResponse>(
        `${projectPath(projectId)}/brief-extraction-runs/${encodeURIComponent(runId)}/reject`,
        { reason, note },
        idempotencyKey,
      ),
    listBriefs,
    getBrief,
    generateConcepts: ({
      projectId,
      briefId,
      briefVersionId,
      idempotencyKey,
    }) =>
      mutation<ConceptGenerationResponse>(
        `${projectPath(projectId)}/briefs/${encodeURIComponent(briefId)}/versions/${encodeURIComponent(briefVersionId)}/concept-runs`,
        {},
        idempotencyKey,
      ),
    getConceptRun,
    listConceptCandidates,
    selectConcept: ({ projectId, conceptRunId, candidateId, idempotencyKey }) =>
      mutation<ConceptSelectionResponse>(
        `${projectPath(projectId)}/concept-runs/${encodeURIComponent(conceptRunId)}/candidates/${encodeURIComponent(candidateId)}/select`,
        {},
        idempotencyKey,
      ),
    generateScript: ({ projectId, conceptRunId, idempotencyKey }) =>
      mutation<ScriptGenerationResponse>(
        `${projectPath(projectId)}/concept-runs/${encodeURIComponent(conceptRunId)}/scripts`,
        {},
        idempotencyKey,
      ),
    getScript,
    generateStoryboard: ({ projectId, scriptVersionId, idempotencyKey }) =>
      mutation<PlanningGenerationResponse>(
        `${projectPath(projectId)}/scripts/${encodeURIComponent(scriptVersionId)}/storyboards`,
        { provider_mode: "valid" },
        idempotencyKey,
      ),
    getStoryboardRun,
    getStoryboardVersion,
    generateShotPlan: ({ projectId, storyboardVersionId, idempotencyKey }) =>
      mutation<PlanningGenerationResponse>(
        `${projectPath(projectId)}/storyboards/${encodeURIComponent(storyboardVersionId)}/shot-plans`,
        { provider_mode: "valid" },
        idempotencyKey,
      ),
    getShotPlanRun,
    getShotPlanVersion,
    listReviews,
    getReview,
    getRevisionRequest,
    submitPlanningReview: ({
      projectId,
      scriptVersionId,
      storyboardVersionId,
      shotPlanVersionId,
      outcome,
      summary,
      requestedChanges,
      idempotencyKey,
    }) =>
      mutation<PlanningReviewResponse>(
        `${projectPath(projectId)}/planning-reviews`,
        {
          artifact_type: "planning_bundle",
          script_version_id: scriptVersionId,
          storyboard_version_id: storyboardVersionId,
          shot_plan_version_id: shotPlanVersionId,
          outcome,
          summary,
          requested_changes: requestedChanges,
        },
        idempotencyKey,
      ),
    completeRevision,
    cancelRevision,
    createDeliveryPackage: ({
      projectId,
      scriptVersionId,
      storyboardVersionId,
      shotPlanVersionId,
      approvalReviewId,
      idempotencyKey,
    }) =>
      mutation<DeliveryPackageResponse>(
        `${projectPath(projectId)}/delivery-packages`,
        {
          script_version_id: scriptVersionId,
          storyboard_version_id: storyboardVersionId,
          shot_plan_version_id: shotPlanVersionId,
          approval_review_id: approvalReviewId,
        },
        idempotencyKey,
      ),
    getDeliveryPackage,
    listExports,
    exportDeliveryPackage: ({
      projectId,
      deliveryPackageVersionId,
      idempotencyKey,
    }) =>
      mutation<{ export: DeliveryExport; replayed: boolean }>(
        `${projectPath(projectId)}/delivery-packages/${encodeURIComponent(deliveryPackageVersionId)}/exports`,
        { format: "delivery-package.zip" },
        idempotencyKey,
      ),
    downloadExport: async (projectId, exportId, filename) => {
      const path = `${projectPath(projectId)}/delivery-exports/${encodeURIComponent(exportId)}`;
      const response = await fetcher(new URL(path, baseUrl), {
        headers: headersFor({}, undefined),
        cache: "no-store",
      });
      if (!response.ok) throw await errorFromResponse(response);
      return { blob: await response.blob(), filename };
    },
  };
}

function isRecord(value: unknown): value is JsonRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function normalizeArtifactIds(value: JsonRecord): ArtifactIds {
  const result: ArtifactIds = {};
  const stringFields: (keyof ArtifactIds)[] = [
    "sourceAssetId",
    "sourceAssetVersionId",
    "sourceObjectId",
    "extractionId",
    "briefRunId",
    "briefCandidateReviewId",
    "briefId",
    "briefVersionId",
    "conceptRunId",
    "selectedConceptCandidateId",
    "conceptSelectionId",
    "scriptVersionId",
    "storyboardRunId",
    "storyboardVersionId",
    "shotPlanRunId",
    "shotPlanVersionId",
    "reviewId",
    "revisionRequestId",
    "deliveryPackageVersionId",
    "exportId",
  ];
  for (const field of stringFields) {
    if (typeof value[field] === "string") result[field] = value[field] as never;
  }
  if (Array.isArray(value.conceptCandidateIds)) {
    const ids = value.conceptCandidateIds.filter(
      (item): item is string => typeof item === "string",
    );
    if (ids.length > 0) result.conceptCandidateIds = ids;
  }
  if (
    value.briefCandidateReviewAction === "accept" ||
    value.briefCandidateReviewAction === "reject"
  ) {
    result.briefCandidateReviewAction = value.briefCandidateReviewAction;
  }
  return result;
}

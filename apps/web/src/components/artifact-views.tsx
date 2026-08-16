import type {
  ConceptCandidate,
  DeliveryExport,
  DeliveryPackage,
  JsonRecord,
  PlanningReview,
  PlanningVersion,
  ScriptArtifact,
} from "../lib/api/product-client";
import { Badge } from "./ui/badge";

function truncateChecksum(checksum: string): string {
  if (checksum.length <= 18) return checksum;
  return `${checksum.slice(0, 10)}…${checksum.slice(-6)}`;
}

interface BriefSurfaceProps {
  content: JsonRecord;
  issues: readonly IssueLike[];
  candidate?: boolean;
}

interface IssueLike {
  field_path?: unknown;
  severity?: unknown;
  message?: unknown;
}

export function BriefSurface({
  content,
  issues,
  candidate = false,
}: BriefSurfaceProps) {
  const groups: ReadonlyArray<{
    title: string;
    fields: ReadonlyArray<[string, string]>;
  }> = [
    {
      title: "目标与受众",
      fields: [
        ["核心目标", "objective.primary_goal"],
        ["期望行动", "objective.desired_action"],
        ["主要受众", "audience.primary_audience"],
        ["次要受众", "audience.secondary_audiences"],
        ["地区", "audience.geography"],
        ["语言", "audience.language"],
        ["受众洞察", "audience.audience_insights"],
      ],
    },
    {
      title: "产品与品牌",
      fields: [
        ["产品", "product.product_name"],
        ["品类", "product.product_category"],
        ["关键特征", "product.key_features"],
        ["关键利益", "product.key_benefits"],
        ["证明点", "product.proof_points"],
        ["品牌", "brand.brand_name"],
        ["语气", "brand.tone"],
        ["视觉指引", "brand.visual_guidelines"],
      ],
    },
    {
      title: "交付与创意约束",
      fields: [
        ["渠道", "channels"],
        ["画幅", "deliverables.aspect_ratios"],
        ["时长（秒）", "deliverables.duration_seconds"],
        ["交付数量", "deliverables.deliverable_count"],
        ["字幕", "deliverables.caption_requirements"],
        ["音频", "deliverables.audio_requirements"],
        ["必传信息", "creative_constraints.required_message"],
        ["行动号召", "creative_constraints.call_to_action"],
        ["开场要求", "creative_constraints.opening_hook_requirements"],
        ["禁用主题", "creative_constraints.prohibited_themes"],
      ],
    },
    {
      title: "制作、合规与未决问题",
      fields: [
        ["可用素材", "production_constraints.available_assets"],
        ["必需素材", "production_constraints.required_assets"],
        ["人才限制", "production_constraints.talent_constraints"],
        ["场地限制", "production_constraints.location_constraints"],
        ["截止日期", "production_constraints.deadline"],
        ["预算", "production_constraints.budget_range"],
        ["免责声明", "legal_and_compliance.disclaimer_requirements"],
        ["受监管类别", "legal_and_compliance.regulated_category"],
        ["权利说明", "legal_and_compliance.usage_rights_notes"],
        ["未决问题", "open_questions"],
      ],
    },
  ];

  return (
    <div className="artifact-surface brief-surface">
      <div className="artifact-badge-row">
        <Badge>{candidate ? "候选" : "已接受版本"}</Badge>
        <span className="artifact-muted">Structured Brief v1</span>
      </div>
      {groups.map((group) => (
        <section className="artifact-section" key={group.title}>
          <h4>{group.title}</h4>
          <FieldGrid
            fields={group.fields.map(([label, path]) => [
              label,
              readPath(content, path),
            ])}
          />
        </section>
      ))}
      <IssueList issues={issues} />
      <JsonInspector label="检查原始 Brief 结构" value={content} />
    </div>
  );
}

export function ConceptComparison({
  candidates,
  selectedId,
  onSelect,
}: {
  candidates: readonly ConceptCandidate[];
  selectedId: string | undefined;
  onSelect: (candidateId: string) => void;
}) {
  return (
    <div className="concept-comparison" aria-label="Concept 候选比较">
      {candidates.map((candidate) => {
        const selected = candidate.id === selectedId;
        const content = candidate.content;
        return (
          <article
            className={`concept-card${selected ? " selected" : ""}`}
            key={candidate.id}
          >
            <div className="card-kicker">
              <span>
                候选 {String(candidate.candidate_index).padStart(2, "0")}
              </span>
              {selected ? <span className="selection-mark">已选择</span> : null}
            </div>
            <h3>{textValue(content.title, "未命名 Concept")}</h3>
            <p className="concept-idea">{textValue(content.one_line_idea)}</p>
            <FieldGrid
              fields={[
                ["策略理由", content.strategic_rationale],
                ["受众洞察", content.target_audience_insight],
                ["情绪语气", content.emotional_tone],
                ["视觉世界", content.visual_world],
                ["叙事弧线", content.narrative_arc],
                ["关键信息", content.key_message],
                ["渠道适配", content.channel_fit],
                ["风险", content.risks],
              ]}
            />
            <button
              className={
                selected ? "button selected-button" : "button secondary"
              }
              type="button"
              aria-pressed={selected}
              onClick={() => onSelect(candidate.id)}
            >
              {selected ? "已选择此 Concept" : "选择此 Concept"}
            </button>
            <JsonInspector label="检查原始 Concept 结构" value={content} />
          </article>
        );
      })}
    </div>
  );
}

export function ScriptSurface({ script }: { script: ScriptArtifact }) {
  const content = script.content;
  const scenes = recordsFrom(content.scenes);
  return (
    <div className="artifact-surface reading-surface">
      <div className="reading-header">
        <div>
          <Badge>Script v{String(content.schema_version ?? "1")}</Badge>
          <h3>{textValue(content.title, "未命名脚本")}</h3>
          <p>{textValue(content.logline)}</p>
        </div>
        <dl className="mini-metadata">
          <div>
            <dt>目标时长</dt>
            <dd>{textValue(content.target_duration_seconds, "未设定")} 秒</dd>
          </div>
          <div>
            <dt>语言 / 格式</dt>
            <dd>
              {textValue(content.language, "—")} ·{" "}
              {textValue(content.format, "—")}
            </dd>
          </div>
        </dl>
      </div>
      <div className="script-summary">
        <FieldGrid
          fields={[
            ["旁白", content.voiceover],
            ["对白", content.dialogue],
            ["屏幕文字", content.on_screen_text],
            ["音乐方向", content.music_direction],
            ["声音方向", content.sound_direction],
            ["行动号召", content.call_to_action],
          ]}
        />
      </div>
      <section className="scene-stack">
        <div className="artifact-section-heading">
          <h4>场景阅读</h4>
          <span>{scenes.length} 个场景</span>
        </div>
        {scenes.map((scene, index) => (
          <article
            className="scene-card"
            key={`${textValue(scene.scene_number, index + 1)}-${index}`}
          >
            <div className="scene-number">
              {String(textValue(scene.scene_number, index + 1)).padStart(
                2,
                "0",
              )}
            </div>
            <div className="scene-copy">
              <h4>{textValue(scene.purpose, "未命名场景")}</h4>
              <p className="scene-context">
                {textValue(scene.setting, "未设定地点")} ·{" "}
                {textValue(scene.estimated_duration_seconds, "—")} 秒 ·{" "}
                {textValue(scene.transition, "cut")}
              </p>
              <p>{textValue(scene.action, "未提供动作描述")}</p>
              <FieldGrid
                fields={[
                  ["旁白", scene.voiceover],
                  ["对白", scene.dialogue],
                  ["屏幕文字", scene.on_screen_text],
                ]}
              />
            </div>
          </article>
        ))}
      </section>
      <JsonInspector label="检查原始 Script 结构" value={content} />
    </div>
  );
}

export function StoryboardSurface({
  storyboard,
}: {
  storyboard: PlanningVersion;
}) {
  const scenes = recordsFrom(storyboard.content.scenes);
  return (
    <div className="artifact-surface storyboard-surface">
      <div className="artifact-badge-row">
        <Badge>Storyboard v{storyboard.version_number}</Badge>
        <span className="artifact-muted">
          {storyboard.scene_count} 个场景 · {storyboard.total_duration_seconds}{" "}
          秒
        </span>
      </div>
      <div className="storyboard-grid">
        {scenes.map((scene, index) => (
          <article
            className="storyboard-card"
            key={`${textValue(scene.storyboard_scene_number, index + 1)}-${index}`}
          >
            <div className="storyboard-frame" aria-hidden="true">
              <span>
                {String(
                  textValue(scene.storyboard_scene_number, index + 1),
                ).padStart(2, "0")}
              </span>
              <i />
            </div>
            <div className="storyboard-copy">
              <h4>{textValue(scene.visual_summary, "未提供视觉摘要")}</h4>
              <p>{textValue(scene.narrative_purpose, "未提供叙事目的")}</p>
              <FieldGrid
                fields={[
                  ["主体", scene.subject],
                  ["地点", scene.setting],
                  ["动作", scene.action],
                  ["构图", scene.composition],
                  ["镜头语言", scene.camera_language],
                  ["光线", scene.lighting],
                  ["色彩", scene.color_palette],
                  ["连续性", scene.continuity_notes],
                ]}
              />
            </div>
          </article>
        ))}
      </div>
      <JsonInspector
        label="检查原始 Storyboard 结构"
        value={storyboard.content}
      />
    </div>
  );
}

export function ShotPlanSurface({ shotPlan }: { shotPlan: PlanningVersion }) {
  const shots = recordsFrom(shotPlan.content.shots);
  return (
    <div className="artifact-surface shot-plan-surface">
      <div className="artifact-badge-row">
        <Badge>Shot Plan v{shotPlan.version_number}</Badge>
        <span className="artifact-muted">
          {shotPlan.shot_count ?? shots.length} 个镜头 ·{" "}
          {shotPlan.total_duration_seconds} 秒
        </span>
      </div>
      <div className="table-scroll">
        <table className="shot-table">
          <caption>镜头覆盖与制作字段</caption>
          <thead>
            <tr>
              <th scope="col">镜头</th>
              <th scope="col">场景</th>
              <th scope="col">类型 / 运动</th>
              <th scope="col">主体与动作</th>
              <th scope="col">环境 / 光线</th>
              <th scope="col">时长</th>
              <th scope="col">声音 / 屏幕文字</th>
            </tr>
          </thead>
          <tbody>
            {shots.map((shot, index) => (
              <tr key={`${textValue(shot.shot_id, index + 1)}-${index}`}>
                <th scope="row">
                  <span className="table-shot-id">
                    {textValue(shot.shot_id, `shot-${index + 1}`)}
                  </span>
                  <small>#{textValue(shot.shot_number, index + 1)}</small>
                </th>
                <td>SB {textValue(shot.storyboard_scene_number, "—")}</td>
                <td>
                  {textValue(shot.shot_type, "—")} ·{" "}
                  {textValue(shot.camera_movement, "—")}
                </td>
                <td>
                  <strong>{textValue(shot.subject, "—")}</strong>
                  <br />
                  {textValue(shot.action, "—")}
                </td>
                <td>
                  {textValue(shot.environment, "—")}
                  <br />
                  <span className="artifact-muted">
                    {textValue(shot.lighting, "—")}
                  </span>
                </td>
                <td>{textValue(shot.estimated_duration_seconds, "—")} 秒</td>
                <td>
                  <span>{textValue(shot.voiceover_segment, "—")}</span>
                  <br />
                  <span className="artifact-muted">
                    {textValue(shot.on_screen_text, "—")}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <JsonInspector label="检查原始 Shot Plan 结构" value={shotPlan.content} />
    </div>
  );
}

export function ReviewSurface({
  review,
  script,
  storyboard,
  shotPlan,
}: {
  review: PlanningReview | undefined;
  script: ScriptArtifact | undefined;
  storyboard: PlanningVersion | undefined;
  shotPlan: PlanningVersion | undefined;
}) {
  return (
    <div className="review-surface">
      <div className="bundle-strip">
        <div>
          <Badge>Planning bundle</Badge>
          <h3>{review ? review.outcome : "等待制作人决定"}</h3>
          <p>
            {review?.summary ??
              "脚本、Storyboard 和 Shot Plan 将作为一个不可变规划包审查。"}
          </p>
        </div>
        <dl className="bundle-counts">
          <div>
            <dt>Script</dt>
            <dd>{script ? "已就绪" : "缺失"}</dd>
          </div>
          <div>
            <dt>Storyboard</dt>
            <dd>{storyboard ? "已就绪" : "缺失"}</dd>
          </div>
          <div>
            <dt>Shot Plan</dt>
            <dd>{shotPlan ? "已就绪" : "缺失"}</dd>
          </div>
        </dl>
      </div>
      {review?.requested_changes &&
      Object.keys(review.requested_changes).length > 0 ? (
        <div className="requested-changes">
          <strong>请求修改</strong>
          <p>
            {textValue(review.requested_changes.reason, "请查看制作人备注")}
          </p>
        </div>
      ) : null}
      {review ? <JsonInspector label="检查审查记录" value={review} /> : null}
    </div>
  );
}

export function DeliverySurface({
  deliveryPackage,
  exports,
}: {
  deliveryPackage: DeliveryPackage | undefined;
  exports: readonly DeliveryExport[];
}) {
  if (!deliveryPackage) {
    return (
      <p className="empty-state">审批通过后，这里会显示不可变交付包清单。</p>
    );
  }
  const manifest = deliveryPackage.manifest;
  const lineage = asRecord(manifest.lineage);
  const artifactDigests = Object.entries(lineage).filter(([key]) =>
    key.endsWith("_content_digest"),
  );
  const packageArtifacts = asRecord(manifest.artifacts);
  return (
    <div className="artifact-surface delivery-surface">
      <div className="delivery-heading">
        <div>
          <Badge>{deliveryPackage.manifest_schema_version}</Badge>
          <h3>交付包 v{deliveryPackage.version_number}</h3>
          <p>已绑定精确的 Script、Storyboard、Shot Plan 与批准记录。</p>
        </div>
        <div className="digest-block">
          <span>Manifest digest</span>
          <code>{deliveryPackage.manifest_digest}</code>
        </div>
      </div>
      <section className="artifact-section">
        <h4>Lineage</h4>
        <FieldGrid
          fields={Object.entries(lineage).map(([key, value]) => [
            labelize(key),
            value,
          ])}
        />
      </section>
      {artifactDigests.length > 0 ? (
        <section className="artifact-section">
          <h4>公共 Artifact digests</h4>
          <FieldGrid
            fields={artifactDigests.map(([key, value]) => [
              labelize(key),
              value,
            ])}
          />
        </section>
      ) : null}
      <section className="artifact-section">
        <h4>包内产物</h4>
        <div className="manifest-cards">
          {Object.entries(packageArtifacts).map(([key, value]) => (
            <div className="manifest-card" key={key}>
              <strong>{labelize(key)}</strong>
              <DetailValue value={value} />
            </div>
          ))}
        </div>
      </section>
      <section className="artifact-section">
        <div className="artifact-section-heading">
          <h4>导出记录</h4>
          <span>{exports.length} 个导出</span>
        </div>
        {exports.length === 0 ? (
          <p className="empty-state">
            尚未生成 ZIP；这是一个需要明确操作的步骤。
          </p>
        ) : (
          <div className="export-list">
            {exports.map((item) => (
              <div className="export-row" key={item.id}>
                <div>
                  <strong>{item.filename}</strong>
                  <span>
                    {item.byte_size.toLocaleString()} bytes · {item.created_at}
                  </span>
                </div>
                <div className="export-checksum">
                  <span>ZIP checksum</span>
                  <code
                    title={item.checksum}
                    aria-label={`完整 ZIP checksum：${item.checksum}`}
                  >
                    {truncateChecksum(item.checksum)}
                  </code>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
      <JsonInspector label="检查原始 delivery manifest" value={manifest} />
    </div>
  );
}

export function JsonInspector({
  label,
  value,
}: {
  label: string;
  value: unknown;
}) {
  return (
    <details className="artifact-inspector">
      <summary>{label}</summary>
      <pre>{JSON.stringify(value, null, 2)}</pre>
    </details>
  );
}

function IssueList({ issues }: { issues: readonly IssueLike[] }) {
  return (
    <section className="issue-section" aria-labelledby="brief-issues-title">
      <div className="artifact-section-heading">
        <h4 id="brief-issues-title">要求问题</h4>
        <span>{issues.length} 条记录</span>
      </div>
      {issues.length === 0 ? (
        <p className="issue-clear">
          没有机器检测到的要求问题；仍需制作人确认候选内容。
        </p>
      ) : (
        <ul className="issue-list">
          {issues.map((issue, index) => (
            <li key={`${textValue(issue.field_path, index)}-${index}`}>
              <span
                className={`severity severity-${textValue(issue.severity, "info")}`}
              >
                {textValue(issue.severity, "info")}
              </span>
              <div>
                <strong>{textValue(issue.field_path, "未标注字段")}</strong>
                <p>{textValue(issue.message, "未提供说明")}</p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function FieldGrid({ fields }: { fields: ReadonlyArray<[string, unknown]> }) {
  return (
    <dl className="field-grid">
      {fields.map(([label, value]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>
            <DetailValue value={value} />
          </dd>
        </div>
      ))}
    </dl>
  );
}

function DetailValue({ value }: { value: unknown }) {
  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="empty-value">未提供</span>;
    return (
      <ul className="inline-list">
        {value.map((item, index) => (
          <li key={`${textValue(item, index)}-${index}`}>{textValue(item)}</li>
        ))}
      </ul>
    );
  }
  if (isRecord(value)) {
    return (
      <span className="nested-value">
        {Object.entries(value).map(([key, item]) => (
          <span key={key}>
            <b>{labelize(key)}：</b>
            {textValue(item, "未提供")}
          </span>
        ))}
      </span>
    );
  }
  return (
    <span
      className={
        value === null || value === undefined || value === ""
          ? "empty-value"
          : undefined
      }
    >
      {textValue(value, "未提供")}
    </span>
  );
}

function recordsFrom(value: unknown): JsonRecord[] {
  return Array.isArray(value) ? value.filter(isRecord) : [];
}

function readPath(value: JsonRecord, path: string): unknown {
  return path.split(".").reduce<unknown>((current, key) => {
    return isRecord(current) ? current[key] : undefined;
  }, value);
}

function asRecord(value: unknown): JsonRecord {
  return isRecord(value) ? value : {};
}

function isRecord(value: unknown): value is JsonRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function textValue(value: unknown, fallback: unknown = "未提供"): string {
  if (value === null || value === undefined || value === "")
    return String(fallback);
  if (Array.isArray(value))
    return (
      value
        .map((item) => textValue(item, ""))
        .filter(Boolean)
        .join("、") || String(fallback)
    );
  if (isRecord(value)) {
    return Object.entries(value)
      .map(([key, item]) => `${labelize(key)}：${textValue(item, "未提供")}`)
      .join("；");
  }
  return String(value);
}

function labelize(value: string): string {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

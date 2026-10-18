import type { WorkspaceSnapshot, StageId } from "../../lib/workspace-model";
import { TruncatedValue } from "../ui/truncated-value";

export function ArtifactLibrary({
  snapshot,
  activeStage,
  onSelect,
}: {
  snapshot: WorkspaceSnapshot;
  activeStage: StageId;
  onSelect: (stage: StageId) => void;
}) {
  const entries: {
    stage: StageId;
    label: string;
    detail: string;
    available: boolean;
    version: string;
  }[] = [
    {
      stage: "brief",
      label: "Creative Brief",
      detail: snapshot.brief?.brief.title ?? "创作目标与制作约束",
      available: Boolean(snapshot.brief || snapshot.ideaIntake),
      version: snapshot.brief
        ? `v${snapshot.brief.current_version.version_number}`
        : "草稿",
    },
    {
      stage: "concepts",
      label: "Concept directions",
      detail: snapshot.artifacts.selectedConceptCandidateId
        ? "已选择创意方向"
        : `${snapshot.concepts.length} 个方向待比较`,
      available: snapshot.concepts.length > 0,
      version: `${snapshot.concepts.length} directions`,
    },
    {
      stage: "script",
      label: "Script",
      detail: "场景、旁白与叙事节奏",
      available: Boolean(snapshot.script),
      version: "已保存",
    },
    {
      stage: "storyboard",
      label: "Storyboard",
      detail: "分镜描述与视觉连续性",
      available: Boolean(snapshot.storyboard),
      version: snapshot.storyboard
        ? `v${snapshot.storyboard.version_number}`
        : "",
    },
    {
      stage: "shot-plan",
      label: "Shot plan",
      detail: "镜头覆盖与拍摄安排",
      available: Boolean(snapshot.shotPlan),
      version: snapshot.shotPlan ? `v${snapshot.shotPlan.version_number}` : "",
    },
    {
      stage: "review",
      label: "Review record",
      detail:
        snapshot.review?.outcome === "approved"
          ? "当前版本已批准"
          : "人工审查与修改记录",
      available: snapshot.reviews.length > 0,
      version: `${snapshot.reviews.length} records`,
    },
    {
      stage: "delivery",
      label: "Delivery package",
      detail: snapshot.exports.length
        ? "制作蓝图 ZIP 已就绪"
        : "批准版本的交付包",
      available: Boolean(snapshot.deliveryPackage),
      version: snapshot.exports.length ? "ZIP" : "v1",
    },
  ];
  return (
    <section className="artifact-library" aria-label="作品目录">
      <div className="library-heading">
        <div>
          <p className="eyebrow">Living artifacts</p>
          <h3>作品目录</h3>
        </div>
        <span>{entries.filter((x) => x.available).length} / 7</span>
      </div>
      <p className="library-caption">每一步都留下可回看的制作产物。</p>
      <ol>
        {entries.map((entry, i) => (
          <li key={entry.stage}>
            <button
              type="button"
              className={`library-item${entry.stage === activeStage ? " active" : ""}`}
              onClick={() => onSelect(entry.stage)}
              disabled={!entry.available}
              aria-label={`查看制作产物 ${entry.stage}`}
              aria-current={entry.stage === activeStage ? "page" : undefined}
            >
              <span className="library-icon" aria-hidden="true">
                {String(i + 1).padStart(2, "0")}
              </span>
              <span>
                <strong>{entry.label}</strong>
                <small>{entry.available ? entry.detail : "等待创作"}</small>
              </span>
              <span className="library-version">
                {entry.available ? entry.version : "—"}
              </span>
            </button>
          </li>
        ))}
      </ol>
      <details className="artifact-detail">
        <summary>版本追溯</summary>
        <dl className="ledger-list">
          {Object.entries(snapshot.artifacts).map(([key, value]) => (
            <div key={key}>
              <dt>{key}</dt>
              <dd>
                <TruncatedValue
                  value={
                    Array.isArray(value) ? value.join(", ") : String(value)
                  }
                  fieldLabel={key}
                />
              </dd>
            </div>
          ))}
        </dl>
      </details>
    </section>
  );
}

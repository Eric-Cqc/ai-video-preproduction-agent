import { Button } from "../../ui/button";
import type { StageProps } from "./stage-props";

type ParseStageProps = Pick<StageProps, "snapshot" | "busy" | "onParse">;

export function ParseStage({ snapshot, busy, onParse }: ParseStageProps) {
  const sourceVersion = snapshot.sourceAsset?.current_version;

  return (
    <section className="stage-card">
      <div className="stage-card-topline">
        <div>
          <h3>解析源文件</h3>
          <p>
            {sourceVersion
              ? `${sourceVersion.original_filename} · ${sourceVersion.media_type}`
              : "需要先完成 Upload。"}
          </p>
        </div>
        {snapshot.extraction ? (
          <span className="artifact-badge">{snapshot.extraction.status}</span>
        ) : null}
      </div>
      {snapshot.briefRun?.status === "failed" ||
      snapshot.briefCandidateAvailable === false ? (
        <div className="failed-run" role="status">
          <strong>解析运行失败</strong>
          <p>
            candidate_available=false；没有可供制作人接受的 Brief
            候选。请修正源文件后重新执行 Parse。
          </p>
        </div>
      ) : null}
      <div className="action-row">
        <Button
          label={
            busy
              ? "解析中…"
              : snapshot.candidate
                ? "重新执行 Parse"
                : "开始 Parse"
          }
          onClick={onParse}
          disabled={busy || !snapshot.sourceObject}
        />
      </div>
      {snapshot.candidate ? (
        <p className="inline-confirmation">
          候选已载入 Brief 阶段；Parse 不会自动接受它。
        </p>
      ) : null}
    </section>
  );
}

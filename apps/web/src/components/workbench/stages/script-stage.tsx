import { ScriptSurface } from "../../artifact-views";
import { Button } from "../../ui/button";
import { EmptyStage } from "../../ui/empty-stage";
import type { StageProps } from "./stage-props";

type ScriptStageProps = Pick<
  StageProps,
  "snapshot" | "busy" | "onGenerateScript"
>;

export function ScriptStage({
  snapshot,
  busy,
  onGenerateScript,
}: ScriptStageProps) {
  return (
    <section className="stage-card">
      {snapshot.script ? (
        <ScriptSurface script={snapshot.script} />
      ) : (
        <>
          <EmptyStage message="选择一个 Concept 后，脚本生成按钮才会可用。" />
          <div className="action-row">
            <Button
              label={busy ? "生成中…" : "生成 Script"}
              onClick={onGenerateScript}
              disabled={busy || !snapshot.artifacts.selectedConceptCandidateId}
            />
          </div>
        </>
      )}
    </section>
  );
}

import { ConceptComparison } from "../../artifact-views";
import { Button } from "../../ui/button";
import { EmptyStage } from "../../ui/empty-stage";
import type { StageProps } from "./stage-props";

type ConceptsStageProps = Pick<
  StageProps,
  "snapshot" | "busy" | "onGenerateConcepts" | "onSelectConcept"
>;

export function ConceptsStage({
  snapshot,
  busy,
  onGenerateConcepts,
  onSelectConcept,
}: ConceptsStageProps) {
  return (
    <section className="stage-card">
      {snapshot.concepts.length > 0 ? (
        <>
          <div className="stage-card-topline">
            <div>
              <h3>比较 Concept 候选</h3>
              <p>全部候选同时展示；选择动作会写入不可变 selection 记录。</p>
            </div>
            <span className="artifact-badge">
              {snapshot.concepts.length} candidates
            </span>
          </div>
          <ConceptComparison
            candidates={snapshot.concepts}
            selectedId={snapshot.artifacts.selectedConceptCandidateId}
            onSelect={onSelectConcept}
          />
        </>
      ) : (
        <>
          <EmptyStage message="Brief 接受后，显式生成三个 Concept 候选。" />
          <div className="action-row">
            <Button
              label={busy ? "生成中…" : "生成 Concept 候选"}
              onClick={onGenerateConcepts}
              disabled={busy || !snapshot.brief}
            />
          </div>
        </>
      )}
    </section>
  );
}

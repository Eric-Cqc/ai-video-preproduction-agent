import { ShotPlanSurface } from "../../artifact-views";
import { Button } from "../../ui/button";
import { EmptyStage } from "../../ui/empty-stage";
import type { StageProps } from "./stage-props";

type ShotPlanStageProps = Pick<
  StageProps,
  "snapshot" | "busy" | "onGenerateShotPlan"
>;

export function ShotPlanStage({
  snapshot,
  busy,
  onGenerateShotPlan,
}: ShotPlanStageProps) {
  return (
    <section className="stage-card">
      {snapshot.shotPlan ? (
        <ShotPlanSurface shotPlan={snapshot.shotPlan} />
      ) : (
        <>
          <EmptyStage message="Storyboard 版本就绪后，显式生成 Shot Plan。" />
          <div className="action-row">
            <Button
              label={busy ? "生成中…" : "生成 Shot Plan"}
              onClick={onGenerateShotPlan}
              disabled={busy || !snapshot.storyboard}
            />
          </div>
        </>
      )}
    </section>
  );
}

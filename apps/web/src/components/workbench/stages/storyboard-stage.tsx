import { StoryboardSurface } from "../../artifact-views";
import { Button } from "../../ui/button";
import { EmptyStage } from "../../ui/empty-stage";
import type { StageProps } from "./stage-props";

type StoryboardStageProps = Pick<
  StageProps,
  "snapshot" | "busy" | "onGenerateStoryboard"
>;

export function StoryboardStage({
  snapshot,
  busy,
  onGenerateStoryboard,
}: StoryboardStageProps) {
  return (
    <section className="stage-card">
      {snapshot.storyboard ? (
        <StoryboardSurface storyboard={snapshot.storyboard} />
      ) : (
        <>
          <EmptyStage message="Script 版本就绪后，显式生成 Storyboard。" />
          <div className="action-row">
            <Button
              label={busy ? "生成中…" : "生成 Storyboard"}
              onClick={onGenerateStoryboard}
              disabled={busy || !snapshot.script}
            />
          </div>
        </>
      )}
    </section>
  );
}

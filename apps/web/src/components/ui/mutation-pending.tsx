import { stageLabel, type StageId } from "../../lib/workspace-model";

export function MutationPending({ stage }: { stage: StageId }) {
  return (
    <div className="mutation-pending" role="status" aria-live="polite">
      <span className="button-spinner" aria-hidden="true" />
      <span>{stageLabel(stage)} 操作进行中</span>
      <span className="mutation-pending-bar" aria-hidden="true" />
    </div>
  );
}

"use client";

import type { ReactNode } from "react";

import {
  stageDefinitions,
  stageDescription,
  stageStatuses,
  stateLabel,
  type StageId,
  type StageState,
} from "../../lib/workspace-model";
import { ErrorPanel } from "../ui/error-panel";
import { BriefStage } from "./stages/brief-stage";
import { MutationPending } from "../ui/mutation-pending";
import { ConceptsStage } from "./stages/concepts-stage";
import { DeliveryStage } from "./stages/delivery-stage";
import { ParseStage } from "./stages/parse-stage";
import { ReviewStage } from "./stages/review-stage";
import { ScriptStage } from "./stages/script-stage";
import { ShotPlanStage } from "./stages/shot-plan-stage";
import type { StageProps } from "./stages/stage-props";
import { StoryboardStage } from "./stages/storyboard-stage";
import { UploadStage } from "./stages/upload-stage";

function statusClass(state: StageState): string {
  return `stage-state stage-state-${state}`;
}

export function WorkspaceStage({
  activeStage,
  onRefresh,
  onRetry,
  onNewKey,
  canRetry,
  ...stageProps
}: StageProps & {
  activeStage: StageId;
  onRefresh: () => void;
  onRetry: () => void;
  onNewKey: () => void;
  canRetry: boolean;
}) {
  const state = stageStatuses(stageProps.snapshot)[activeStage];
  const stage =
    stageDefinitions.find((item) => item.id === activeStage) ??
    stageDefinitions[0];

  const stageContent = {
    upload: <UploadStage {...stageProps} />,
    parse: <ParseStage {...stageProps} />,
    brief: <BriefStage {...stageProps} />,
    concepts: <ConceptsStage {...stageProps} />,
    script: <ScriptStage {...stageProps} />,
    storyboard: <StoryboardStage {...stageProps} />,
    "shot-plan": <ShotPlanStage {...stageProps} />,
    review: <ReviewStage {...stageProps} />,
    delivery: <DeliveryStage {...stageProps} />,
  } satisfies Record<StageId, ReactNode>;

  return (
    <section className="stage-workspace" aria-labelledby="stage-title">
      <div className="stage-heading">
        <div className="stage-heading-copy">
          <p className="eyebrow">
            {stage.eyebrow} · {stage.index}
          </p>
          <h2 id="stage-title">{stage.label}</h2>
          <p>{stageDescription(stageProps.snapshot, activeStage)}</p>
        </div>
        <div className="stage-heading-status">
          <span className="stage-progress">
            Stage {stage.index} /{" "}
            {String(stageDefinitions.length).padStart(2, "0")}
          </span>
          <span className={statusClass(state)}>{stateLabel(state)}</span>
        </div>
      </div>
      {stageProps.snapshot.errors[activeStage] ? (
        <ErrorPanel
          error={stageProps.snapshot.errors[activeStage]}
          onRefresh={onRefresh}
          onRetry={onRetry}
          onNewKey={onNewKey}
          canRetry={canRetry}
        />
      ) : null}
      {stageProps.snapshot.activeOperation === activeStage ? (
        <MutationPending stage={activeStage} />
      ) : null}
      {stageContent[activeStage]}
    </section>
  );
}

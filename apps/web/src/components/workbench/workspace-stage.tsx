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
import { BriefStage } from "./stages/brief-stage";
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
  ...stageProps
}: StageProps & {
  activeStage: StageId;
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
        <div>
          <p className="eyebrow">
            {stage.eyebrow} · {stage.index}
          </p>
          <h2 id="stage-title">{stage.label}</h2>
          <p>{stageDescription(stageProps.snapshot, activeStage)}</p>
        </div>
        <span className={statusClass(state)}>{stateLabel(state)}</span>
      </div>
      {stageProps.snapshot.errors[activeStage] ? (
        <div className="stage-failure" role="status">
          <strong>阶段失败</strong>
          <p>{stageProps.snapshot.errors[activeStage]}</p>
        </div>
      ) : null}
      {stageContent[activeStage]}
    </section>
  );
}

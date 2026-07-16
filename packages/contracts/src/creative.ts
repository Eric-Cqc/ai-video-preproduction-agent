import Ajv, { type ErrorObject } from "ajv";
import conceptSchema from "../schemas/creative-concept-v1.schema.json";
import scriptSchema from "../schemas/script-v1.schema.json";
import shotPlanSchema from "../schemas/shot-plan-v1.schema.json";
import storyboardSchema from "../schemas/storyboard-v1.schema.json";

export const CREATIVE_SCHEMA_VERSION = "1.0.0" as const;
const ajv = new Ajv({ allErrors: true, strict: true });
const validators = {
  concept: ajv.compile<Record<string, unknown>>(conceptSchema),
  script: ajv.compile<Record<string, unknown>>(scriptSchema),
  storyboard: ajv.compile<Record<string, unknown>>(storyboardSchema),
  shotPlan: ajv.compile<Record<string, unknown>>(shotPlanSchema),
};

export class CreativeContractError extends Error {
  constructor(readonly validationErrors: ErrorObject[] | null | undefined) {
    super("Creative content does not match canonical contract v1");
  }
}

export function parseCreativeContent(
  kind: keyof typeof validators,
  value: unknown,
): Record<string, unknown> {
  const validate = validators[kind];
  if (!validate(value)) throw new CreativeContractError(validate.errors);
  if (kind === "storyboard") validateStoryboardSemantics(value);
  if (kind === "shotPlan") validateShotPlanSemantics(value);
  return value;
}

function validateStoryboardSemantics(value: Record<string, unknown>): void {
  const scenes = value.scenes;
  if (!Array.isArray(scenes)) return;
  const sourceNumbers = scenes.map((scene) =>
    typeof scene === "object" && scene !== null
      ? (scene as Record<string, unknown>).source_script_scene_number
      : undefined,
  );
  if (!sourceNumbers.every((number, index) => number === index + 1)) {
    throw new CreativeContractError(null);
  }
  const total = scenes.reduce((sum, scene) => {
    const duration = (scene as Record<string, unknown>)
      .estimated_duration_seconds;
    return sum + (typeof duration === "number" ? duration : 0);
  }, 0);
  if (!Number.isFinite(total) || total <= 0)
    throw new CreativeContractError(null);
  for (const scene of scenes) {
    const record = scene as Record<string, unknown>;
    for (const field of [
      "visual_summary",
      "composition",
      "camera_language",
      "action",
    ]) {
      if (containsExternalAction(String(record[field] ?? ""))) {
        throw new CreativeContractError(null);
      }
    }
  }
}

function validateShotPlanSemantics(value: Record<string, unknown>): void {
  const shots = value.shots;
  if (!Array.isArray(shots)) return;
  const ids = shots.map((shot) => (shot as Record<string, unknown>).shot_id);
  if (new Set(ids).size !== ids.length) throw new CreativeContractError(null);
  const orders = shots.map(
    (shot) => (shot as Record<string, unknown>).shot_number,
  );
  if (!orders.every((number, index) => number === index + 1)) {
    throw new CreativeContractError(null);
  }
  for (const shot of shots) {
    const prompt = String(
      (shot as Record<string, unknown>).generation_prompt ?? "",
    ).toLowerCase();
    if (containsExternalAction(prompt)) {
      throw new CreativeContractError(null);
    }
  }
}

function containsExternalAction(value: string): boolean {
  return [
    "http://",
    "https://",
    "fetch ",
    "tool call",
    "run shell",
    "execute ",
    "ignore previous",
    "system prompt",
  ].some((token) => value.includes(token));
}

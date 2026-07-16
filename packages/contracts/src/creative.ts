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
  return value;
}

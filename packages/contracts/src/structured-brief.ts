import Ajv, { type ErrorObject } from "ajv";
import structuredBriefSchema from "../schemas/structured-brief-v1.schema.json";

export const STRUCTURED_BRIEF_SCHEMA_VERSION = "1.0.0" as const;

export interface StructuredBriefContent {
  schema_version: typeof STRUCTURED_BRIEF_SCHEMA_VERSION;
  objective: Record<string, unknown>;
  audience: Record<string, unknown>;
  offer: Record<string, unknown>;
  product: Record<string, unknown>;
  brand: Record<string, unknown>;
  channels: string[];
  deliverables: Record<string, unknown>;
  creative_constraints: Record<string, unknown>;
  production_constraints: Record<string, unknown>;
  legal_and_compliance: Record<string, unknown>;
  references: Array<Record<string, unknown>>;
  success_criteria: Record<string, unknown>;
  open_questions: string[];
}

const ajv = new Ajv({ allErrors: true, strict: true });
const validate = ajv.compile<StructuredBriefContent>(structuredBriefSchema);

export class StructuredBriefContractError extends Error {
  readonly validationErrors: ErrorObject[];

  constructor(errors: ErrorObject[] | null | undefined) {
    super("Structured Brief content does not match contract v1");
    this.name = "StructuredBriefContractError";
    this.validationErrors = errors ? [...errors] : [];
  }
}

export function parseStructuredBrief(value: unknown): StructuredBriefContent {
  if (!validate(value)) {
    throw new StructuredBriefContractError(validate.errors);
  }
  return value;
}

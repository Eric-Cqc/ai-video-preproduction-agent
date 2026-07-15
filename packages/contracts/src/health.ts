import Ajv, { type ErrorObject } from "ajv";
import healthSchema from "../schemas/health-v1.schema.json";

export const HEALTH_CONTRACT_VERSION = "1.0.0" as const;

export interface HealthResponse {
  status: "ok";
  service: string;
  version: string;
  environment: string;
  contract_version: typeof HEALTH_CONTRACT_VERSION;
  timestamp: string;
}

const ajv = new Ajv({ allErrors: true, strict: true });
const validate = ajv.compile<HealthResponse>(healthSchema);

export class HealthContractError extends Error {
  readonly validationErrors: ErrorObject[];

  constructor(errors: ErrorObject[] | null | undefined) {
    super("API health response does not match contract v1");
    this.name = "HealthContractError";
    this.validationErrors = errors ? [...errors] : [];
  }
}

export function parseHealthResponse(value: unknown): HealthResponse {
  if (!validate(value)) {
    throw new HealthContractError(validate.errors);
  }
  return value;
}

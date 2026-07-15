import {
  HealthContractError,
  parseHealthResponse,
  type HealthResponse,
} from "@foundation/contracts/health";

export type HealthResult =
  | { state: "available"; health: HealthResponse }
  | { state: "unavailable"; message: string };

export async function fetchApiHealth(
  apiBaseUrl: URL,
  fetcher: typeof fetch = fetch,
): Promise<HealthResult> {
  const endpoint = new URL("/api/v1/health", apiBaseUrl);
  try {
    const response = await fetcher(endpoint, {
      cache: "no-store",
      headers: { accept: "application/json" },
    });
    if (!response.ok) {
      return {
        state: "unavailable",
        message: `API health request failed with status ${response.status}`,
      };
    }
    const health = parseHealthResponse(await response.json());
    return { state: "available", health };
  } catch (error) {
    const message =
      error instanceof HealthContractError
        ? "API returned an invalid health response"
        : "API is unavailable";
    return { state: "unavailable", message };
  }
}

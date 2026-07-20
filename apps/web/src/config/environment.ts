export interface WebEnvironment {
  applicationEnvironment: string;
  apiBaseUrl: URL;
  browserApiBaseUrl: URL;
}

function parseApiBaseUrl(rawValue: string): URL {
  let url: URL;
  try {
    url = new URL(rawValue);
  } catch {
    throw new Error("API_BASE_URL must be an absolute URL");
  }

  if (!["http:", "https:"].includes(url.protocol)) {
    throw new Error("API_BASE_URL must use http or https");
  }
  if (url.username || url.password) {
    throw new Error("API_BASE_URL must not contain credentials");
  }
  return url;
}

export function loadWebEnvironment(
  environment: Readonly<Record<string, string | undefined>> = process.env,
): WebEnvironment {
  const applicationEnvironment = environment.APP_ENVIRONMENT?.trim() || "local";
  const apiBaseUrl = parseApiBaseUrl(
    environment.API_BASE_URL?.trim() || "http://127.0.0.1:8000",
  );
  const browserApiBaseUrl = parseApiBaseUrl(
    environment.PUBLIC_API_BASE_URL?.trim() || apiBaseUrl.toString(),
  );
  return { applicationEnvironment, apiBaseUrl, browserApiBaseUrl };
}

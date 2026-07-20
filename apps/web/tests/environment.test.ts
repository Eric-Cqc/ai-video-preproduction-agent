import { describe, expect, it } from "vitest";

import { loadWebEnvironment } from "../src/config/environment";

describe("Web environment", () => {
  it("uses safe local defaults", () => {
    const environment = loadWebEnvironment({});
    expect(environment.applicationEnvironment).toBe("local");
    expect(environment.apiBaseUrl.href).toBe("http://127.0.0.1:8000/");
    expect(environment.browserApiBaseUrl.href).toBe("http://127.0.0.1:8000/");
  });

  it.each(["not-a-url", "file:///tmp/api", "https://user:secret@example.test"])(
    "rejects unsafe API_BASE_URL value %s",
    (apiBaseUrl) => {
      expect(() => loadWebEnvironment({ API_BASE_URL: apiBaseUrl })).toThrow();
    },
  );

  it("separates the server health origin from the browser proxy origin", () => {
    const environment = loadWebEnvironment({
      API_BASE_URL: "http://api:8000",
      PUBLIC_API_BASE_URL: "https://pilot.example.test/api",
    });
    expect(environment.apiBaseUrl.href).toBe("http://api:8000/");
    expect(environment.browserApiBaseUrl.href).toBe(
      "https://pilot.example.test/api",
    );
  });
});

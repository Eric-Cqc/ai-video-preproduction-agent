import { describe, expect, it } from "vitest";

import { loadWebEnvironment } from "../src/config/environment";

describe("Web environment", () => {
  it("uses safe local defaults", () => {
    const environment = loadWebEnvironment({});
    expect(environment.applicationEnvironment).toBe("local");
    expect(environment.apiBaseUrl.href).toBe("http://127.0.0.1:8000/");
  });

  it.each(["not-a-url", "file:///tmp/api", "https://user:secret@example.test"])(
    "rejects unsafe API_BASE_URL value %s",
    (apiBaseUrl) => {
      expect(() => loadWebEnvironment({ API_BASE_URL: apiBaseUrl })).toThrow();
    },
  );
});

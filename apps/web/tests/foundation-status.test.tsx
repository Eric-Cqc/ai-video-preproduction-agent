import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import validHealth from "../../../packages/test-fixtures/health/valid-health.json";
import { parseHealthResponse } from "@foundation/contracts/health";
import { FoundationStatus } from "../src/components/foundation-status";

describe("FoundationStatus", () => {
  it("shows Web and connected API status", () => {
    render(
      <FoundationStatus
        environment="test"
        api={{ state: "available", health: parseHealthResponse(validHealth) }}
      />,
    );
    expect(
      screen.getByRole("heading", { name: "AI Video Preproduction Agent" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Connected")).toBeInTheDocument();
    expect(screen.getByText("foundation-api")).toBeInTheDocument();
    expect(screen.getByText("1.0.0")).toBeInTheDocument();
  });

  it("shows a clear API error state", () => {
    render(
      <FoundationStatus
        environment="test"
        api={{ state: "unavailable", message: "API is unavailable" }}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Unavailable");
    expect(screen.getByRole("alert")).toHaveTextContent("API is unavailable");
  });
});

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import validHealth from "../../../packages/test-fixtures/health/valid-health.json";
import { parseHealthResponse } from "@foundation/contracts/health";
import { FoundationStatus } from "../src/components/foundation-status";

afterEach(cleanup);

describe("FoundationStatus", () => {
  it("shows Web and connected API status", () => {
    render(
      <FoundationStatus
        environment="test"
        api={{ state: "available", health: parseHealthResponse(validHealth) }}
        apiBaseUrl="http://api.test"
      />,
    );
    expect(
      screen.getByRole("heading", { name: "Production Desk" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/本地 API 已连接/)).toBeInTheDocument();
    expect(screen.getByText("制作项目")).toBeInTheDocument();
  });

  it("shows a clear API error state", () => {
    render(
      <FoundationStatus
        environment="test"
        api={{ state: "unavailable", message: "API is unavailable" }}
        apiBaseUrl="http://api.test"
      />,
    );
    expect(screen.getByText("本地 API 未连接")).toBeInTheDocument();
  });

  it("exposes a collapsed mobile stage-rail control", () => {
    render(
      <FoundationStatus
        environment="test"
        api={{ state: "unavailable", message: "API is unavailable" }}
        apiBaseUrl="http://api.test"
      />,
    );

    const toggle = screen.getByRole("button", {
      name: "制作阶段导航，展开",
    });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(toggle).toHaveAttribute("aria-controls", "production-stage-list");

    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");

    fireEvent.click(screen.getByRole("button", { name: /^Upload/ }));
    expect(toggle).toHaveAttribute("aria-expanded", "false");
  });
});

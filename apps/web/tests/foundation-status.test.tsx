import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import validHealth from "../../../packages/test-fixtures/health/valid-health.json";
import { parseHealthResponse } from "@foundation/contracts/health";
import { FoundationStatus } from "../src/components/foundation-status";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function renderHosted(fetchMock: ReturnType<typeof vi.fn>) {
  vi.stubGlobal("fetch", fetchMock);
  return render(
    <FoundationStatus
      environment="hosted"
      api={{ state: "available", health: parseHealthResponse(validHealth) }}
      apiBaseUrl="https://pilot.example.test/api"
    />,
  );
}

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  vi.unstubAllGlobals();
});

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

  it("enters the hosted pilot with a valid credential", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(401, { error: { code: "pilot_access_required" } }),
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(
        jsonResponse(200, {
          actor_subject: "pilot:owner",
          organization_id: "11111111-1111-1111-1111-111111111111",
          workspace_id: "22222222-2222-2222-2222-222222222222",
        }),
      );
    renderHosted(fetchMock);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    fireEvent.change(screen.getByLabelText("私有试点访问凭据"), {
      target: { value: "private-pilot-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: "进入试点" }));

    expect(
      await screen.findByText("已进入私有试点工作台。"),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "退出" })).toBeEnabled();
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("distinguishes invalid credentials from rate limiting", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(401, { error: { code: "pilot_access_required" } }),
      )
      .mockResolvedValueOnce(
        jsonResponse(401, {
          error: { code: "pilot_access_invalid_credential" },
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse(429, {
          error: { code: "pilot_access_rate_limited" },
        }),
      );
    renderHosted(fetchMock);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    fireEvent.change(screen.getByLabelText("私有试点访问凭据"), {
      target: { value: "incorrect" },
    });
    fireEvent.click(screen.getByRole("button", { name: "进入试点" }));

    expect(
      await screen.findByText("访问凭据无效，请核对后重试。"),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "进入试点" }));
    expect(
      await screen.findByText("尝试次数过多，请等待几分钟后使用正确凭据重试。"),
    ).toBeInTheDocument();
  });

  it("shows a distinct network error and restores the submit button", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(401, { error: { code: "pilot_access_required" } }),
      )
      .mockRejectedValueOnce(new TypeError("network unavailable"));
    renderHosted(fetchMock);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    fireEvent.change(screen.getByLabelText("私有试点访问凭据"), {
      target: { value: "private-pilot-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: "进入试点" }));

    expect(
      await screen.findByText("无法连接访问服务，请检查网络后重试。"),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "进入试点" })).toBeEnabled();
  });

  it("prevents duplicate access submissions while verification is pending", async () => {
    let resolveAccess: (response: Response) => void = () => undefined;
    const pendingAccess = new Promise<Response>((resolve) => {
      resolveAccess = resolve;
    });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(401, { error: { code: "pilot_access_required" } }),
      )
      .mockReturnValueOnce(pendingAccess)
      .mockResolvedValueOnce(
        jsonResponse(200, {
          actor_subject: "pilot:owner",
          organization_id: "11111111-1111-1111-1111-111111111111",
          workspace_id: "22222222-2222-2222-2222-222222222222",
        }),
      );
    renderHosted(fetchMock);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    fireEvent.change(screen.getByLabelText("私有试点访问凭据"), {
      target: { value: "private-pilot-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: "进入试点" }));
    const pendingButton = screen.getByRole("button", { name: "正在验证…" });
    fireEvent.click(pendingButton);

    expect(pendingButton).toBeDisabled();
    expect(fetchMock).toHaveBeenCalledTimes(2);

    resolveAccess(new Response(null, { status: 204 }));
    expect(
      await screen.findByText("已进入私有试点工作台。"),
    ).toBeInTheDocument();
  });

  it("logs out and returns to the access gate", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(200, {
          actor_subject: "pilot:owner",
          organization_id: "11111111-1111-1111-1111-111111111111",
          workspace_id: "22222222-2222-2222-2222-222222222222",
        }),
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    renderHosted(fetchMock);
    expect(await screen.findByRole("button", { name: "退出" })).toBeEnabled();

    fireEvent.click(screen.getByRole("button", { name: "退出" }));

    expect(await screen.findByText("已安全退出私有试点。")).toBeInTheDocument();
    expect(screen.getByLabelText("私有试点访问凭据")).toBeInTheDocument();
  });
});

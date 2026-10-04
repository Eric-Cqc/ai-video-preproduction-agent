import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { IdeaBriefEditor } from "../src/components/workbench/idea-intake";
import {
  createIdeaIntakeClient,
  type IdeaIntake,
} from "../src/lib/api/idea-intake-client";
import { nextActionableStage } from "../src/lib/workspace-model";
import type { WorkspaceSnapshot } from "../src/lib/workspace-model";

const intake: IdeaIntake = {
  id: "synthetic-intake",
  raw_idea: "Synthetic coffee shop film",
  objective: "Introduce the shop",
  platform: "Xiaohongshu",
  audience: "Commuters",
  duration_seconds: 30,
  content_type: "short-form video",
  tone: [],
  key_messages: ["Take a moment"],
  call_to_action: "Visit tomorrow",
  constraints: [],
  must_include: [],
  must_avoid: [],
  assumptions: ["Offline template; review required"],
  missing_fields: [],
  status: "structured",
  brief_id: null,
  brief_version_id: null,
  version: 1,
};

describe("idea-first human gates", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("lets the server derive a bounded title from a long objective", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(Response.json({}));
    vi.stubGlobal("fetch", fetcher);
    const client = createIdeaIntakeClient("http://api.test", {
      actorSubject: "actor:owner",
      organizationId: "org-1",
      workspaceId: "workspace-1",
    });
    await client.confirm("project-1", {
      ...intake,
      objective: "目".repeat(500),
    });
    expect(fetcher).toHaveBeenCalledOnce();
    expect(JSON.parse(String(fetcher.mock.calls[0]?.[1]?.body))).toEqual({
      expected_version: 1,
    });
  });

  it("blocks key messages that cannot fit the canonical Brief", () => {
    render(
      <IdeaBriefEditor
        intake={intake}
        busy={false}
        onSave={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByLabelText("关键信息（每行一项）"), {
      target: { value: `${"甲".repeat(500)}\n${"乙".repeat(499)}` },
    });
    expect(
      screen.getByRole("button", { name: "保存 Brief 修改" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "确认 Brief，进入创意方向" }),
    ).toBeDisabled();
    expect(
      screen.getByText(/关键信息合并后不能超过 1,000 字/),
    ).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("关键信息（每行一项）"), {
      target: { value: `${"甲".repeat(500)}\n${"乙".repeat(498)}` },
    });
    expect(
      screen.getByRole("button", { name: "保存 Brief 修改" }),
    ).toBeEnabled();
  });

  it("requires saving a supported duration before confirming the Brief", () => {
    const save = vi.fn();
    const confirm = vi.fn();
    const props = { busy: false, onSave: save, onConfirm: confirm };
    const { rerender } = render(<IdeaBriefEditor intake={intake} {...props} />);
    const duration = screen.getByLabelText("时长（秒，15–60）");
    const saveButton = screen.getByRole("button", { name: "保存 Brief 修改" });
    const confirmButton = screen.getByRole("button", {
      name: "确认 Brief，进入创意方向",
    });
    fireEvent.change(duration, { target: { value: "14" } });
    expect(saveButton).toBeDisabled();
    expect(confirmButton).toBeDisabled();
    fireEvent.change(duration, { target: { value: "37" } });
    expect(saveButton).toBeEnabled();
    expect(confirmButton).toBeDisabled();
    fireEvent.click(saveButton);
    expect(save).toHaveBeenCalledWith(
      expect.objectContaining({ duration_seconds: 37 }),
    );
    expect(confirm).not.toHaveBeenCalled();
    rerender(
      <IdeaBriefEditor
        key="saved-v2"
        intake={{ ...intake, duration_seconds: 37, version: 2 }}
        {...props}
      />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: "确认 Brief，进入创意方向" }),
    );
    expect(confirm).toHaveBeenCalledOnce();
  });

  it("counts normalized Unicode key messages like the API", () => {
    render(
      <IdeaBriefEditor
        intake={intake}
        busy={false}
        onSave={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByLabelText("关键信息（每行一项）"), {
      target: {
        value: `${"☕".repeat(500)}\n ${"☕".repeat(500)} \n${"🎬".repeat(498)}`,
      },
    });
    expect(
      screen.getByRole("button", { name: "保存 Brief 修改" }),
    ).toBeEnabled();
  });

  it("resumes a completed idea project at Delivery without inferring a new action", () => {
    const snapshot = {
      ideaIntake: { ...intake, status: "confirmed" },
      artifacts: {},
      concepts: [],
      sourceAssets: [],
      reviews: [],
      exports: [{ checksum: "verified-offline-fixture" }],
      errors: {},
    } as unknown as WorkspaceSnapshot;
    expect(nextActionableStage(snapshot)).toBe("delivery");
  });
});

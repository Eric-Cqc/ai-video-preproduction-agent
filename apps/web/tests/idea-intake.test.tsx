import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { IdeaBriefEditor } from "../src/components/workbench/idea-intake";
import type { IdeaIntake } from "../src/lib/api/idea-intake-client";
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

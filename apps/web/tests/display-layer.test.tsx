import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Button } from "../src/components/ui/button";
import { CopyButton } from "../src/components/ui/copy-button";
import { ErrorPanel } from "../src/components/ui/error-panel";
import { TruncatedValue } from "../src/components/ui/truncated-value";
import {
  BriefSurface,
  ConceptComparison,
} from "../src/components/artifact-views";
import { ApiClientError } from "../src/lib/api/product-client";

describe("display layer controls", () => {
  afterEach(() => {
    cleanup();
  });

  it("reveals a long value without discarding its full content", () => {
    const value = "A".repeat(200);

    render(<TruncatedValue value={value} limit={20} />);

    expect(screen.getByText(/A{20}…/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "展开" }));
    expect(screen.getByText(value)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "收起" })).toBeInTheDocument();
  });

  it("keeps long Brief and Concept fields collapsed until a field-specific disclosure is requested", () => {
    const briefValue = "Brief field ".repeat(30);
    const conceptValue = "Concept field ".repeat(30);

    const { rerender } = render(
      <BriefSurface
        content={{ objective: { primary_goal: briefValue } }}
        issues={[]}
      />,
    );

    const briefDisclosure = screen.getByRole("button", {
      name: "展开核心目标",
    });
    expect(briefDisclosure).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(briefDisclosure);
    expect(briefDisclosure.parentElement).toHaveTextContent(briefValue);

    rerender(
      <ConceptComparison
        candidates={[
          {
            id: "concept-1",
            candidate_index: 1,
            content: { strategic_rationale: conceptValue },
            created_at: "2026-01-01T00:00:00Z",
          },
        ]}
        selectedId={undefined}
        onSelect={() => undefined}
      />,
    );

    const conceptDisclosure = screen.getByRole("button", {
      name: "展开策略理由",
    });
    expect(conceptDisclosure).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(conceptDisclosure);
    expect(conceptDisclosure.parentElement).toHaveTextContent(conceptValue);
  });

  it("hides empty Brief fields by default and reveals them on request", () => {
    render(
      <BriefSurface
        content={{
          objective: { primary_goal: "Launch the spring campaign" },
        }}
        issues={[]}
      />,
    );

    expect(
      screen.queryByText("\u671f\u671b\u884c\u52a8"),
    ).not.toBeInTheDocument();
    expect(screen.getByText("\u6838\u5fc3\u76ee\u6807")).toBeInTheDocument();

    const toggles = screen.getAllByRole("button", {
      name: /\u663e\u793a \d+ \u4e2a\u672a\u586b\u5199\u5b57\u6bb5/,
    });
    expect(toggles.length).toBeGreaterThan(0);
    const toggle = toggles[0]!;
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(toggle);

    expect(screen.getByText("\u671f\u671b\u884c\u52a8")).toBeInTheDocument();
    expect(
      screen.getByRole("button", {
        name: /\u9690\u85cf \d+ \u4e2a\u672a\u586b\u5199\u5b57\u6bb5/,
      }),
    ).toHaveAttribute("aria-expanded", "true");
  });

  it("copies visible values through the native Clipboard API", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    render(<CopyButton value="sha256:example" label="复制 checksum" />);
    fireEvent.click(
      screen.getByRole("button", { name: "复制 checksum完整值" }),
    );

    await waitFor(() =>
      expect(writeText).toHaveBeenCalledWith("sha256:example"),
    );
    expect(
      screen.getByRole("button", { name: "复制 checksum完整值" }),
    ).toHaveTextContent("已复制");
  });

  it("shows pending feedback inside a disabled mutation button", () => {
    render(
      <Button label="创建交付包" pending pendingLabel="创建中…" disabled />,
    );

    const button = screen.getByRole("button", { name: "创建中…" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
  });

  it("offers only the recovery actions that match a conflict", () => {
    const onRefresh = vi.fn();
    const onRetry = vi.fn();
    const onNewKey = vi.fn();

    render(
      <ErrorPanel
        error={
          new ApiClientError(409, {
            code: "version_conflict",
            message: "The version changed.",
          })
        }
        onRefresh={onRefresh}
        onRetry={onRetry}
        onNewKey={onNewKey}
        canRetry
      />,
    );

    const alert = screen.getByRole("alert");
    expect(alert).toHaveAttribute("aria-live", "assertive");
    expect(alert).toHaveClass("error-panel-warning");
    expect(
      screen.getByText(/重新开始当前操作以生成新的操作键/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "重新读取状态" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "使用新操作键重新提交" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "重试同一安全操作" }),
    ).not.toBeInTheDocument();
  });
});

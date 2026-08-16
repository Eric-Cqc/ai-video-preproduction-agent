"use client";

import { useState } from "react";

export function CopyButton({
  value,
  label = "复制",
}: {
  value: string;
  label?: string;
}) {
  const [status, setStatus] = useState<"idle" | "copied" | "failed">("idle");

  async function copy() {
    try {
      if (!navigator.clipboard?.writeText) {
        throw new Error("Clipboard API unavailable");
      }
      await navigator.clipboard.writeText(value);
      setStatus("copied");
    } catch {
      setStatus("failed");
    }
  }

  const text =
    status === "copied" ? "已复制" : status === "failed" ? "复制失败" : label;

  return (
    <button
      className="copy-button"
      type="button"
      onClick={() => void copy()}
      aria-label={`${label}完整值`}
    >
      {text}
    </button>
  );
}

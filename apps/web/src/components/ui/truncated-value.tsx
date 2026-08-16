"use client";

import { useState } from "react";

const defaultLimit = 180;

export function TruncatedValue({
  value,
  limit = defaultLimit,
  fieldLabel,
}: {
  value: string;
  limit?: number;
  fieldLabel?: string | undefined;
}) {
  const [expanded, setExpanded] = useState(false);
  const truncatable = value.length > limit;
  const displayValue =
    truncatable && !expanded ? `${value.slice(0, limit).trimEnd()}…` : value;

  return (
    <span className="truncated-value">
      <span>{displayValue}</span>
      {truncatable ? (
        <button
          className="text-action"
          type="button"
          aria-expanded={expanded}
          aria-label={
            fieldLabel
              ? `${expanded ? "收起" : "展开"}${fieldLabel}`
              : undefined
          }
          onClick={() => setExpanded((current) => !current)}
        >
          {expanded ? "收起" : "展开"}
        </button>
      ) : null}
    </span>
  );
}

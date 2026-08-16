import type { ComponentPropsWithoutRef, ReactNode } from "react";

interface PanelProps extends ComponentPropsWithoutRef<"section"> {
  children: ReactNode;
}

export function Panel({ children, ...props }: PanelProps) {
  return <section {...props}>{children}</section>;
}

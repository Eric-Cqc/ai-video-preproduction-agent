interface ButtonProps {
  label: string;
  onClick?: (() => void) | undefined;
  disabled?: boolean | undefined;
  pending?: boolean | undefined;
  pendingLabel?: string | undefined;
  tone?: "primary" | "secondary" | "warning";
  type?: "button" | "submit";
}

export function Button({
  label,
  onClick,
  disabled,
  pending = false,
  pendingLabel,
  tone = "primary",
  type = "button",
}: ButtonProps) {
  return (
    <button
      className={`button ${tone === "primary" ? "" : tone}${pending ? " button-pending" : ""}`}
      type={type}
      disabled={disabled}
      onClick={onClick}
      aria-busy={pending || undefined}
    >
      {pending ? <span className="button-spinner" aria-hidden="true" /> : null}
      {pending ? (pendingLabel ?? label) : label}
    </button>
  );
}

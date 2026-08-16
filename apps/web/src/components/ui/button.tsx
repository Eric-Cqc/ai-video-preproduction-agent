interface ButtonProps {
  label: string;
  onClick: () => void;
  disabled?: boolean | undefined;
  tone?: "primary" | "secondary" | "warning";
}

export function Button({
  label,
  onClick,
  disabled,
  tone = "primary",
}: ButtonProps) {
  return (
    <button
      className={`button ${tone === "primary" ? "" : tone}`}
      type="button"
      disabled={disabled}
      onClick={onClick}
    >
      {label}
    </button>
  );
}

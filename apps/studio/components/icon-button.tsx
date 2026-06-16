import type { ComponentType } from "react";
import type { LucideProps } from "lucide-react";

interface IconButtonProps {
  label: string;
  icon: ComponentType<LucideProps>;
  onClick?: () => void;
  type?: "button" | "submit";
  active?: boolean;
  disabled?: boolean;
  className?: string;
}

export function IconButton({
  label,
  icon: Icon,
  onClick,
  type = "button",
  active = false,
  disabled = false,
  className = "",
}: IconButtonProps) {
  return (
    <button
      aria-label={label}
      className={`icon-button ${active ? "is-active" : ""} ${className}`}
      disabled={disabled}
      onClick={onClick}
      title={label}
      type={type}
    >
      <Icon aria-hidden="true" size={17} strokeWidth={1.9} />
    </button>
  );
}

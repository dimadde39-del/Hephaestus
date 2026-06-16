import type { ComponentType, ReactNode } from "react";
import type { LucideProps } from "lucide-react";

interface StatusBadgeProps {
  children: ReactNode;
  icon?: ComponentType<LucideProps>;
  tone?: "neutral" | "accent" | "success" | "warning" | "error" | "cyan";
  label?: string;
}

export function StatusBadge({
  children,
  icon: Icon,
  tone = "neutral",
  label,
}: StatusBadgeProps) {
  return (
    <span aria-label={label} className={`status-badge status-${tone}`}>
      {Icon ? <Icon aria-hidden="true" size={14} strokeWidth={1.9} /> : null}
      {children}
    </span>
  );
}

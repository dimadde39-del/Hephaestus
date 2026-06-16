import type { ComponentType, ReactNode } from "react";
import type { LucideProps } from "lucide-react";

interface ArtifactCardProps {
  label: string;
  value: ReactNode;
  detail?: ReactNode;
  icon?: ComponentType<LucideProps>;
  tone?: "neutral" | "accent" | "success" | "warning" | "error" | "cyan";
}

export function ArtifactCard({
  label,
  value,
  detail,
  icon: Icon,
  tone = "neutral",
}: ArtifactCardProps) {
  return (
    <section className={`artifact-card artifact-${tone}`}>
      <div className="artifact-card-icon" aria-hidden="true">
        {Icon ? <Icon size={16} strokeWidth={1.9} /> : null}
      </div>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
        {detail ? <small>{detail}</small> : null}
      </div>
    </section>
  );
}

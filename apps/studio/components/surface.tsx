import type { ComponentPropsWithoutRef } from "react";

interface SurfaceProps extends ComponentPropsWithoutRef<"section"> {
  tone?: "default" | "quiet" | "raised";
}

export function Surface({ className = "", tone = "default", ...props }: SurfaceProps) {
  return <section className={`surface surface-${tone} ${className}`} {...props} />;
}

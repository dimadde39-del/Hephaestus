import Image from "next/image";

interface WorkspaceSwitcherProps {
  repoName: string | null;
  providerLabel: string;
  collapsed?: boolean;
}

export function WorkspaceSwitcher({
  repoName,
  providerLabel,
  collapsed = false,
}: WorkspaceSwitcherProps) {
  return (
    <div className={`workspace-switcher ${collapsed ? "is-collapsed" : ""}`} aria-label="Workspace">
      <Image alt="" height={30} priority src="/talos-mark.svg" width={30} />
      {collapsed ? null : (
        <div>
          <span>Studio</span>
          <strong>{repoName ?? "Local workspace"}</strong>
          <small>{providerLabel}</small>
        </div>
      )}
    </div>
  );
}

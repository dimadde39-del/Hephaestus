import { StudioApp } from "@/features/studio/studio-app";

export function generateStaticParams() {
  return [{ slug: [] }];
}

export default function StudioPage() {
  return <StudioApp />;
}

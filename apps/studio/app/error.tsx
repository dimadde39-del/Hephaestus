"use client";

export default function Error({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="studio-error" role="alert">
      <div>
        <p className="eyebrow">Studio paused</p>
        <h1>Something failed while opening the workspace.</h1>
        <button type="button" onClick={reset}>
          Try again
        </button>
      </div>
    </main>
  );
}

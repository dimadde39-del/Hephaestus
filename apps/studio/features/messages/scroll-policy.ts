export const NEAR_BOTTOM_THRESHOLD = 120;

export interface ScrollMetrics {
  scrollTop: number;
  scrollHeight: number;
  clientHeight: number;
}

export function distanceFromBottom(metrics: ScrollMetrics) {
  return Math.max(0, metrics.scrollHeight - metrics.clientHeight - metrics.scrollTop);
}

export function isNearBottom(
  metrics: ScrollMetrics,
  threshold = NEAR_BOTTOM_THRESHOLD,
) {
  return distanceFromBottom(metrics) <= threshold;
}

export function keyboardScrollTop(
  key: string,
  metrics: ScrollMetrics,
) {
  const page = Math.max(1, Math.round(metrics.clientHeight * 0.9));
  if (key === "Home") return 0;
  if (key === "End") return metrics.scrollHeight;
  if (key === "PageUp") return Math.max(0, metrics.scrollTop - page);
  if (key === "PageDown") {
    return Math.min(metrics.scrollHeight, metrics.scrollTop + page);
  }
  return null;
}

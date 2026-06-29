import "@testing-library/jest-dom/vitest";

Element.prototype.scrollIntoView = function scrollIntoView() {};
Element.prototype.scrollTo = function scrollTo(options?: ScrollToOptions | number, y?: number) {
  if (typeof options === "number") {
    this.scrollTop = y ?? 0;
  } else {
    this.scrollTop = Number(options?.top ?? 0);
  }
};

if (!globalThis.ResizeObserver) {
  globalThis.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}

if (!globalThis.CSS) {
  Object.defineProperty(globalThis, "CSS", {
    value: {},
    writable: true,
  });
}

if (!globalThis.CSS.escape) {
  globalThis.CSS.escape = (value: string) => value.replace(/"/g, '\\"');
}

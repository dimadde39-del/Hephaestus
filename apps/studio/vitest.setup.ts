import "@testing-library/jest-dom/vitest";

Element.prototype.scrollIntoView = function scrollIntoView() {};

if (!globalThis.CSS) {
  Object.defineProperty(globalThis, "CSS", {
    value: {},
    writable: true,
  });
}

if (!globalThis.CSS.escape) {
  globalThis.CSS.escape = (value: string) => value.replace(/"/g, '\\"');
}

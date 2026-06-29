import { describe, expect, it } from "vitest";

import { isNearBottom, keyboardScrollTop } from "./scroll-policy";

describe("scroll policy", () => {
  it("uses a forgiving near-bottom threshold", () => {
    expect(isNearBottom({ scrollTop: 780, scrollHeight: 1000, clientHeight: 120 })).toBe(true);
    expect(isNearBottom({ scrollTop: 700, scrollHeight: 1000, clientHeight: 120 })).toBe(false);
  });

  it("maps transcript navigation keys to bounded positions", () => {
    const metrics = { scrollTop: 500, scrollHeight: 1200, clientHeight: 300 };
    expect(keyboardScrollTop("Home", metrics)).toBe(0);
    expect(keyboardScrollTop("End", metrics)).toBe(1200);
    expect(keyboardScrollTop("PageUp", metrics)).toBe(230);
    expect(keyboardScrollTop("PageDown", metrics)).toBe(770);
    expect(keyboardScrollTop("ArrowDown", metrics)).toBeNull();
  });
});

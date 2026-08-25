import { describe, expect, it } from "vitest";

import { paginate, parsePage } from "./pagination";

describe("pagination", () => {
  it("parses positive pages and falls back safely", () => {
    expect(parsePage("3")).toBe(3);
    expect(parsePage(undefined)).toBe(1);
    expect(parsePage("0")).toBe(1);
    expect(parsePage("2.5")).toBe(1);
    expect(parsePage("not-a-number")).toBe(1);
  });

  it("caps requested pages and returns stable metadata", () => {
    const result = paginate(["a", "b", "c", "d", "e"], 99, 2);

    expect(result.items).toEqual(["e"]);
    expect(result.page).toBe(3);
    expect(result.pageSize).toBe(2);
    expect(result.totalItems).toBe(5);
    expect(result.totalPages).toBe(3);
    expect(result.hasPrevious).toBe(true);
    expect(result.hasNext).toBe(false);
  });

  it("handles empty collections without a page zero", () => {
    expect(paginate([], 4, 20)).toMatchObject({
      items: [],
      page: 1,
      totalItems: 0,
      totalPages: 1,
      hasPrevious: false,
      hasNext: false,
    });
  });
});

import { beforeEach, describe, expect, it, vi } from "vitest";

const redirect = vi.hoisted(() => vi.fn(() => { throw new Error("NEXT_REDIRECT"); }));
vi.mock("next/navigation", () => ({ redirect }));

import SourcesPage, { metadata as sourcesMetadata } from "./sources/page";
import MethodologyPage, { metadata as methodologyMetadata } from "./methodology/page";
import StatusPage, { metadata as statusMetadata } from "./status/page";

describe("retired public sections", () => {
  beforeEach(() => { redirect.mockClear(); });

  it.each([
    ["sources", SourcesPage, sourcesMetadata],
    ["methodology", MethodologyPage, methodologyMetadata],
    ["status", StatusPage, statusMetadata],
  ] as const)("redirects %s to Overview without rendering or indexing the section", (_name, Page, metadata) => {
    expect(() => Page()).toThrow("NEXT_REDIRECT");
    expect(redirect).toHaveBeenCalledExactlyOnceWith("/");
    expect(metadata.robots).toEqual({ index: false, follow: false });
  });
});

import { describe, expect, it } from "vitest";
import { apiProxyTarget } from "../vite.proxy";

describe("Vite API proxy target", () => {
  it("keeps the local backend as the default", () => {
    expect(apiProxyTarget({})).toBe("http://localhost:8000");
  });

  it("uses VITE_API_PROXY_TARGET when it is configured", () => {
    expect(apiProxyTarget({ VITE_API_PROXY_TARGET: "http://localhost:18000" })).toBe("http://localhost:18000");
  });
});

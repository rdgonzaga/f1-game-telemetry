import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, api } from "@/api/client";

function respondWith(body: unknown, init: ResponseInit = {}) {
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(body), init));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("requests", () => {
  it("raises the backend's detail, with the status a caller can branch on", async () => {
    respondWith({ detail: "no such lap" }, { status: 404 });

    await expect(api.lap("20260918-231502_monza_race", 3)).rejects.toThrow(
      expect.objectContaining({ status: 404, message: "no such lap" }) as Error,
    );
  });

  it("falls back to the status when the body is not the API's", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("<html>502</html>", { status: 502 })));

    const error: unknown = await api.sessions().catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(502);
  });
});

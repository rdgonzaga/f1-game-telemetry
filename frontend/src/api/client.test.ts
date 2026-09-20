import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, api, apiBase, liveSocketUrl } from "@/api/client";

function respondWith(body: unknown, init: ResponseInit = {}) {
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(body), init));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("where the API is", () => {
  it("calls the dev server's API port, which app.py allows by origin", () => {
    // Tests run with DEV set, same as `npm run dev`. A build makes both same-origin instead.
    expect(apiBase).toBe("http://localhost:20778");
    expect(liveSocketUrl()).toBe("ws://localhost:20778/ws/live");
  });
});

describe("requests", () => {
  it("builds the compare query in the order the backend expects", async () => {
    const fetchMock = respondWith({ track: { id: 7, name: "Monza", length: 5793 } });
    await api.compare({ session: "a", lap: 1 }, { session: "b", lap: 2 });

    const url = String(fetchMock.mock.calls[0]?.[0]);
    expect(url).toBe("http://localhost:20778/api/compare?session_a=a&lap_a=1&session_b=b&lap_b=2");
  });

  it("escapes a session id rather than pasting it into the path", async () => {
    const fetchMock = respondWith({});
    await api.session("../secret");

    expect(String(fetchMock.mock.calls[0]?.[0])).toContain("/api/sessions/..%2Fsecret");
  });

  it("raises the backend's detail, with the status a caller can branch on", async () => {
    respondWith({ detail: "no such lap" }, { status: 404 });

    await expect(api.lap("20260918-231502_monza_race", 3)).rejects.toThrow(
      expect.objectContaining({ status: 404, message: "no such lap" }) as Error,
    );
  });

  it("falls back to the status when the body is not the API's", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("<html>502</html>", { status: 502 })));

    await expect(api.sessions()).rejects.toBeInstanceOf(ApiError);
  });
});

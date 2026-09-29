import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiGet, apiPost } from "./api";

function mockFetch(status: number, body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(status === 204 ? null : JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("api client", () => {
  it("returns parsed JSON and calls the same-origin /api prefix", async () => {
    mockFetch(200, { ok: true });
    await expect(apiGet("/health")).resolves.toEqual({ ok: true });
    expect(fetch).toHaveBeenCalledWith(
      "/api/health",
      expect.objectContaining({ credentials: "same-origin" }),
    );
  });

  it("surfaces string error details", async () => {
    mockFetch(400, { detail: "Credentials were rejected" });
    await expect(apiPost("/accounts", {})).rejects.toMatchObject({
      message: "Credentials were rejected",
      status: 400,
    });
  });

  it("formats validation errors without echoing input", async () => {
    mockFetch(422, { detail: [{ loc: ["body", "password"], msg: "Too short", type: "x" }] });
    await expect(apiPost("/auth/register", {})).rejects.toThrow("password: Too short");
  });

  it("handles 204 responses", async () => {
    mockFetch(204, null);
    await expect(apiPost("/auth/logout")).resolves.toBeUndefined();
  });

  it("wraps network failures", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
    await expect(apiGet("/x")).rejects.toBeInstanceOf(ApiError);
  });
});

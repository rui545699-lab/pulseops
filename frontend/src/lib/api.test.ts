import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";
import type { RunRequest } from "@/lib/types";

const payload: RunRequest = {
  baseline_start: "2020-12-07",
  baseline_end: "2020-12-13",
  target_start: "2020-12-21",
  target_end: "2020-12-27",
  planner_mode: "deepseek",
};

describe("Product API client", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("posts a JSON run request to the configured backend", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({ id: "run-01" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await api.createRun(payload);

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/runs",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ "Content-Type": "application/json" }),
        body: JSON.stringify(payload),
      }),
    );
  });

  it("surfaces a non-2xx response instead of treating it as a network failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        json: async () => ({ detail: "Invalid planner mode" }),
      }),
    );

    await expect(api.createRun(payload)).rejects.toMatchObject({
      name: "ApiError",
      message: "Invalid planner mode",
      status: 422,
    });
  });
});

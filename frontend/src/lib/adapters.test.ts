import { describe, expect, it, vi } from "vitest";
import { demoAdapter, liveAdapter } from "@/lib/adapters";
import { establishedQuestion } from "@/lib/fixtures";

describe("query adapters", () => {
  it("keeps live mode fail-closed", async () => { await expect(liveAdapter.query(establishedQuestion)).rejects.toThrow("Live backend is not configured"); });
  it("runs the demo through explicit stages without network access", async () => { vi.useFakeTimers(); const stages: string[] = []; const pending = demoAdapter.query(establishedQuestion, (stage) => stages.push(stage)); await vi.runAllTimersAsync(); const response = await pending; expect(stages).toEqual(["securing", "routing", "retrieving", "generating", "validating"]); expect(response.route).toBe("retrieve_docs"); vi.useRealTimers(); });
});

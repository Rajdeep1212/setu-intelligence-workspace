import { describe, expect, it } from "vitest";
import { demoAdapter, liveAdapter } from "@/lib/adapters";
import { establishedQuestion } from "@/lib/fixtures";

describe("query adapters", () => {
  it("keeps live mode fail-closed", async () => { await expect(liveAdapter.query(establishedQuestion)).rejects.toThrow("Live backend is not configured"); });
  it("returns the demo fixture without network access", async () => { const response = await demoAdapter.query(establishedQuestion); expect(response.route).toBe("retrieve_docs"); });
});

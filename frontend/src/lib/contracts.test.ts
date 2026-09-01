import { describe, expect, it } from "vitest";
import { queryRequestSchema, queryResponseSchema, sourceDetailSchema, sourceFiltersSchema } from "@/lib/contracts";
import { demoResponse } from "@/lib/fixtures";

describe("SETU query contracts", () => {
  it("accepts the sanitized demo response", () => { expect(queryResponseSchema.parse(demoResponse).citations).toHaveLength(3); });
  it("rejects empty and oversized questions", () => { expect(queryRequestSchema.safeParse({ query: " " }).success).toBe(false); expect(queryRequestSchema.safeParse({ query: "x".repeat(2001) }).success).toBe(false); });
  it("rejects unsupported language values", () => { expect(queryRequestSchema.safeParse({ query: "Valid", language: "fr" }).success).toBe(false); });
  it("bounds source filters and strips no contract fields", () => { expect(sourceFiltersSchema.safeParse({ page_size: "25", language: "en" }).success).toBe(true); expect(sourceFiltersSchema.safeParse({ page_size: "26" }).success).toBe(false); });
  it("rejects source bodies and malformed eligibility data", () => { const parsed = sourceDetailSchema.safeParse({ id: "safe", title: "Title", source: "PIB", language: "en", metadata: {}, chunk_count: 1, eligibility_count: 0, has_eligibility: false, eligibility: [{ scheme_name: "x", criteria: { nested: { secret: true } } }] }); expect(parsed.success).toBe(false); });
  it("accepts claim-specific retrieved citations and claims without citation badges", () => { const parsed = queryResponseSchema.parse({ answer: "Two sections.", citations: [{ chunk_id: "one", document_id: "document-one" }], sections: [{ text: "Linked.", citation_ids: ["one"] }, { text: "Unlinked.", citation_ids: [] }] }); expect(parsed.sections).toHaveLength(2); expect(parsed.sections[1].citation_ids).toEqual([]); });
  it("rejects unknown and duplicate claim citation IDs", () => { const citation = { chunk_id: "one", document_id: "document-one" }; expect(queryResponseSchema.safeParse({ answer: "Unknown.", citations: [citation], sections: [{ text: "Unknown.", citation_ids: ["fabricated"] }] }).success).toBe(false); expect(queryResponseSchema.safeParse({ answer: "Duplicate.", citations: [citation], sections: [{ text: "Duplicate.", citation_ids: ["one", "one"] }] }).success).toBe(false); });
  it("rejects duplicate top-level citation IDs", () => { const citation = { chunk_id: "one", document_id: "document-one" }; expect(queryResponseSchema.safeParse({ answer: "Duplicate.", citations: [citation, { ...citation, document_id: "document-two" }], sections: [] }).success).toBe(false); });
  it("rejects malformed claim structures", () => { expect(queryResponseSchema.safeParse({ answer: "Malformed.", citations: [], sections: [{ text: "", citation_ids: "not-an-array" }] }).success).toBe(false); });
});

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

describe("traffic-rule answers (Phase 3)", () => {
  const base = { answer: "The official on-the-spot amount in West Bengal for riding without a helmet is ₹1,000.", citations: [], sections: [{ text: "The official on-the-spot amount in West Bengal for riding without a helmet is ₹1,000.", citation_ids: [] }] };

  it("accepts a rule lookup with its verified premise check", () => {
    const parsed = queryResponseSchema.parse({
      ...base,
      route: "traffic_rules",
      response_status: "rule_lookup",
      premise_check: {
        verdict: "contradicted", offence_id: "helmet", jurisdiction: "IN-WB", occurrence: null, claimed_inr: 5000,
        verified_amounts: [{ occurrence: "first", vehicle_class: "any", inr: 1000 }],
        source: { title: "Compounding of offences", reference: "No. 208-WT/3M-128/97 (Pt.III)(D) dated 24 Jan 2022", url: "https://transport.wb.gov.in/wp-content/uploads/2022/02/208-WT-DATE-24-01-2022.pdf" },
        schedule_row: "Schedule II Sl. No. 22", missing: [],
      },
    });
    expect(parsed.premise_check?.verdict).toBe("contradicted");
  });

  it("accepts a clarifying question with no source", () => {
    const parsed = queryResponseSchema.parse({ ...base, answer: "Which state or city are you in?", route: "traffic_rules", response_status: "needs_clarification", premise_check: { verdict: "missing_jurisdiction", missing: ["jurisdiction"] } });
    expect(parsed.premise_check?.missing).toEqual(["jurisdiction"]);
  });

  it("rejects a premise source that is not a URL", () => {
    expect(() => queryResponseSchema.parse({ ...base, response_status: "rule_lookup", premise_check: { verdict: "supported", source: { title: "x", reference: "y", url: "not a url" } } })).toThrow();
  });
});

describe("message checks (Phase 4a)", () => {
  const base = { answer: "This message shows strong signs of a scam.", citations: [], sections: [{ text: "This message shows strong signs of a scam.", citation_ids: [] }], route: "scam_check", response_status: "scam_check" };

  it("accepts a message check with links and a cited warning", () => {
    const parsed = queryResponseSchema.parse({
      ...base,
      scam_check: {
        verdict: "likely_scam", signals: ["apk"],
        links: [{ url: "bit.ly/x", host: "bit.ly", official: false, kinds: ["shortened_link"] }],
        debunks: [{ id: "d", kind: "channel_warning", topic: "t", summary: "s", date: "2026-07-10", issuer: "PIB Fact Check", source: "https://example.org/warning" }],
      },
    });
    expect(parsed.scam_check?.verdict).toBe("likely_scam");
  });

  it("has no verdict that calls a message safe", () => {
    expect(() => queryResponseSchema.parse({ ...base, scam_check: { verdict: "safe" } })).toThrow();
  });
});

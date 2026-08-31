import { describe, expect, it } from "vitest";
import { queryRequestSchema, queryResponseSchema } from "@/lib/contracts";
import { demoResponse } from "@/lib/fixtures";

describe("SETU query contracts", () => {
  it("accepts the sanitized demo response", () => { expect(queryResponseSchema.parse(demoResponse).citations).toHaveLength(3); });
  it("rejects empty and oversized questions", () => { expect(queryRequestSchema.safeParse({ query: " " }).success).toBe(false); expect(queryRequestSchema.safeParse({ query: "x".repeat(2001) }).success).toBe(false); });
  it("rejects unsupported language values", () => { expect(queryRequestSchema.safeParse({ query: "Valid", language: "fr" }).success).toBe(false); });
});

import { afterEach, describe, expect, it, vi } from "vitest";
import { POST } from "./route";

describe("query request byte bounds", () => {
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllEnvs(); });

  it("accepts bounded multilingual clarification context", async () => {
    // Demo mode validates the same request before dispatch and needs no transport.
    vi.stubEnv("SETU_DATA_MODE", "demo");
    const payload = { query: "क".repeat(2000), language: "hi", clarification_context: { original_query: "ব".repeat(2000) } };
    const body = JSON.stringify(payload);
    expect(Buffer.byteLength(body)).toBeGreaterThan(8192);
    const response = await POST(new Request("http://localhost/api/query", { method: "POST", body, headers: { "content-length": String(Buffer.byteLength(body)) } }));
    expect(response.status).toBe(200);
  });

  it("rejects oversized actual bytes even without content-length", async () => {
    const response = await POST(new Request("http://localhost/api/query", { method: "POST", body: JSON.stringify({ query: "क".repeat(6000) }) }));
    expect(response.status).toBe(413);
  });
});

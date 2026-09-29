import { createServer } from "node:http";

import { describe, expect, it, vi } from "vitest";

import { demoResponse, establishedQuestion } from "@/lib/fixtures";
import { BffError, localBackendOrigin, queryThroughBff, sourcesThroughBff, validateSameSite } from "@/lib/server/bff";

const localEnvironment = { NODE_ENV: "test", SETU_DATA_MODE: "local", SETU_BACKEND_URL: "http://127.0.0.1:8000", SETU_BACKEND_API_KEY: "server-only-test-key" } as NodeJS.ProcessEnv;

describe("server-only BFF boundary", () => {
  it("keeps demo mode network-free", async () => { const transport = vi.fn(); const response = await queryThroughBff(establishedQuestion, { transport, environment: { NODE_ENV: "test", SETU_DATA_MODE: "demo" } }); expect(response).toEqual(demoResponse); expect(transport).not.toHaveBeenCalled(); });
  it("keeps the future cloud adapter fail-closed", async () => { await expect(queryThroughBff(establishedQuestion, { environment: { NODE_ENV: "test", SETU_DATA_MODE: "cloud" } })).rejects.toMatchObject({ code: "CLOUD_ADAPTER_DISABLED" }); });
  it("quarantines eligibility before every adapter and transport", async () => { const transport = vi.fn(); const input = { query: "Eligibility assessment: Evaluate a profile", language: "en" as const }; for (const mode of ["demo", "local", "cloud"] as const) await expect(queryThroughBff(input, { transport, environment: { ...localEnvironment, SETU_DATA_MODE: mode } })).rejects.toMatchObject({ code: "ELIGIBILITY_UNVERIFIED" }); expect(transport).not.toHaveBeenCalled(); });
  it("allows only configured loopback HTTP origins", () => { expect(localBackendOrigin(localEnvironment)).toBe("http://127.0.0.1:8000"); for (const value of ["https://127.0.0.1:8000", "http://backend.example", "http://127.0.0.1:8000/path", "http://user:pass@localhost:8000"]) expect(() => localBackendOrigin({ NODE_ENV: "test", SETU_BACKEND_URL: value })).toThrow(BffError); });
  it("accepts equivalent loopback aliases only on the same protocol and port", () => { const request = new Request("http://localhost:3000/api/query", { headers: { origin: "http://127.0.0.1:3000", "sec-fetch-site": "same-origin" } }); expect(validateSameSite(request)).toBe(true); expect(validateSameSite(new Request("http://localhost:3000/api/query", { headers: { origin: "http://127.0.0.1:3001", "sec-fetch-site": "same-origin" } }))).toBe(false); expect(validateSameSite(new Request("http://localhost:3000/api/query", { headers: { origin: "https://127.0.0.1:3000", "sec-fetch-site": "same-origin" } }))).toBe(false); expect(validateSameSite(new Request("http://localhost:3000/api/query", { headers: { origin: "https://evil.example", "x-forwarded-host": "evil.example" } }))).toBe(false); });
  it("attaches the API key once and rejects redirects", async () => { const transport = vi.fn(async (_url: string | URL | Request, init?: RequestInit) => { expect(new Headers(init?.headers).get("X-API-Key")).toBe("server-only-test-key"); expect(init?.redirect).toBe("error"); return new Response(JSON.stringify(demoResponse), { status: 200, headers: { "Content-Type": "application/json" } }); }); const result = await queryThroughBff(establishedQuestion, { transport: transport as typeof fetch, environment: localEnvironment }); expect(result.answer).toBe(demoResponse.answer); expect(JSON.stringify(result)).not.toContain("server-only-test-key"); expect(transport).toHaveBeenCalledTimes(1); });
  it("uses the bounded loopback HTTP transport when no test transport is injected", async () => {
    let receivedKey = "";
    const server = createServer((request, response) => {
      receivedKey = String(request.headers["x-api-key"] ?? "");
      setTimeout(() => {
        response.writeHead(200, { "Content-Type": "application/json" });
        response.end(JSON.stringify(demoResponse));
      }, 25);
    });
    await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
    try {
      const address = server.address();
      if (!address || typeof address === "string") throw new Error("Expected a TCP listener");
      const response = await queryThroughBff(establishedQuestion, { environment: { ...localEnvironment, SETU_BACKEND_URL: `http://127.0.0.1:${address.port}` } });
      expect(response.answer).toBe(demoResponse.answer);
      expect(receivedKey).toBe("server-only-test-key");
    } finally {
      await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
    }
  });
  it("rejects an oversized backend body in the default loopback transport", async () => {
    const server = createServer((_request, response) => {
      response.writeHead(200, { "Content-Type": "application/json" });
      response.end(`{"answer":"${"x".repeat(1_100_000)}"}`);
    });
    await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
    try {
      const address = server.address();
      if (!address || typeof address === "string") throw new Error("Expected a TCP listener");
      await expect(queryThroughBff(establishedQuestion, { environment: { ...localEnvironment, SETU_BACKEND_URL: `http://127.0.0.1:${address.port}` } })).rejects.toMatchObject({ code: "MALFORMED_RESPONSE" });
    } finally {
      await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
    }
  });
  it("does not follow redirects in the default loopback transport", async () => {
    let redirected = false;
    const server = createServer((request, response) => {
      if (request.url === "/redirected") {
        redirected = true;
        response.end(JSON.stringify(demoResponse));
        return;
      }
      const address = server.address();
      if (!address || typeof address === "string") throw new Error("Expected a TCP listener");
      response.writeHead(302, { Location: `http://127.0.0.1:${address.port}/redirected` });
      response.end();
    });
    await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
    try {
      const address = server.address();
      if (!address || typeof address === "string") throw new Error("Expected a TCP listener");
      await expect(queryThroughBff(establishedQuestion, { environment: { ...localEnvironment, SETU_BACKEND_URL: `http://127.0.0.1:${address.port}` } })).rejects.toMatchObject({ code: "BACKEND_UNAVAILABLE" });
      expect(redirected).toBe(false);
    } finally {
      await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
    }
  });
  it("preserves omitted and explicit language semantics in the upstream payload", async () => { const transport = vi.fn<(...args: [string | URL | Request, RequestInit?]) => Promise<Response>>(async () => new Response(JSON.stringify(demoResponse), { status: 200, headers: { "Content-Type": "application/json" } })); await queryThroughBff({ query: "भारत के डिजिटल ढांचे की मुख्य विशेषताएं क्या हैं?" }, { transport: transport as typeof fetch, environment: localEnvironment }); await queryThroughBff({ query: "ভারতের ডিজিটাল পরিকাঠামোর বৈশিষ্ট্য কী?", language: "bn" }, { transport: transport as typeof fetch, environment: localEnvironment }); expect(JSON.parse(String(transport.mock.calls[0][1]?.body))).not.toHaveProperty("language"); expect(JSON.parse(String(transport.mock.calls[1][1]?.body))).toMatchObject({ language: "bn" }); });
  it("forwards the exact synthetic question without trimming or normalization", async () => { const exact = "  How do I register for e-Shram and what do I need?\u00a0"; const transport = vi.fn<(...args: [string | URL | Request, RequestInit?]) => Promise<Response>>(async () => new Response(JSON.stringify(demoResponse), { status: 200, headers: { "Content-Type": "application/json" } })); await queryThroughBff({ query: exact, language: "en" }, { transport: transport as typeof fetch, environment: localEnvironment }); expect(JSON.parse(String(transport.mock.calls[0][1]?.body)).query).toBe(exact); });
  it("does not retry upstream failures and sanitizes them", async () => { const transport = vi.fn(async () => new Response("upstream secret body", { status: 500 })); await expect(queryThroughBff(establishedQuestion, { transport: transport as typeof fetch, environment: localEnvironment })).rejects.toMatchObject({ code: "BACKEND_UNAVAILABLE", message: "The backend is temporarily unavailable." }); expect(transport).toHaveBeenCalledTimes(1); });
  it("rejects malformed backend data", async () => { const transport = vi.fn(async () => new Response(JSON.stringify({ answer: 42, api_key: "leak" }), { status: 200 })); await expect(queryThroughBff(establishedQuestion, { transport: transport as typeof fetch, environment: localEnvironment })).rejects.toMatchObject({ code: "MALFORMED_RESPONSE" }); });
  it("rejects cross-site origins", () => { expect(validateSameSite(new Request("http://127.0.0.1:3000/api/query", { headers: { Origin: "https://evil.example", "Sec-Fetch-Site": "cross-site" } }))).toBe(false); expect(validateSameSite(new Request("http://127.0.0.1:3000/api/query", { headers: { Origin: "http://127.0.0.1:3000", "Sec-Fetch-Site": "same-origin" } }))).toBe(true); });
  it("rejects a malformed origin without throwing", () => { expect(validateSameSite(new Request("http://127.0.0.1:3000/api/query", { headers: { Origin: "not a URL" } }))).toBe(false); });
  it("bounds source pagination before any transport", async () => { const transport = vi.fn(); await expect(sourcesThroughBff(new URL("http://localhost/api/sources?page_size=26"), { transport, environment: localEnvironment })).rejects.toMatchObject({ code: "INVALID_REQUEST" }); expect(transport).not.toHaveBeenCalled(); });
});

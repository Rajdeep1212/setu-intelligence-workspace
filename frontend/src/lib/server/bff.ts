import { eligibilityResponse, getDemoSource, getDemoSources, demoResponse } from "@/lib/fixtures";
import { queryResponseSchema, sourceDetailSchema, sourceFiltersSchema, sourcesResponseSchema, type QueryRequest, type QueryResponse, type SourceDetail, type SourcesResponse } from "@/lib/contracts";

export type DataMode = "demo" | "local" | "cloud";
type Transport = typeof fetch;

export class BffError extends Error { constructor(public readonly code: string, public readonly status: number, message: string) { super(message); } }

export function dataMode(environment: NodeJS.ProcessEnv = process.env): DataMode { const value = environment.SETU_DATA_MODE ?? "demo"; return value === "local" || value === "cloud" ? value : "demo"; }
export function validateSameSite(request: Request): boolean { const site = request.headers.get("sec-fetch-site"); if (site && !["same-origin", "same-site", "none"].includes(site)) return false; const origin = request.headers.get("origin"); return !origin || new URL(origin).origin === new URL(request.url).origin; }

export function localBackendOrigin(environment: NodeJS.ProcessEnv = process.env): string {
  const raw = environment.SETU_BACKEND_URL; if (!raw) throw new BffError("LIVE_NOT_CONFIGURED", 503, "Local backend integration is not configured.");
  let url: URL; try { url = new URL(raw); } catch { throw new BffError("LIVE_NOT_CONFIGURED", 503, "Local backend integration is not configured."); }
  const allowedHost = url.hostname === "localhost" || url.hostname === "127.0.0.1" || url.hostname === "[::1]";
  if (url.protocol !== "http:" || !allowedHost || (url.pathname !== "/" && url.pathname !== "") || url.username || url.password || url.search || url.hash) throw new BffError("UPSTREAM_NOT_ALLOWED", 503, "The configured backend origin is not allowed.");
  return url.origin;
}

function apiKey(environment: NodeJS.ProcessEnv): string { const key = environment.SETU_BACKEND_API_KEY; if (!key) throw new BffError("LIVE_NOT_CONFIGURED", 503, "Local backend integration is not configured."); return key; }
function mapStatus(status: number): BffError { if (status === 401 || status === 403) return new BffError("AUTHENTICATION_FAILED", 502, "The backend rejected server authentication."); if (status === 422) return new BffError("INVALID_REQUEST", 400, "The backend rejected the request."); if (status === 404) return new BffError("SOURCE_NOT_FOUND", 404, "The requested source was not found."); return new BffError("BACKEND_UNAVAILABLE", 503, "The backend is temporarily unavailable."); }

async function upstream<T>(path: string, init: RequestInit, schema: { parse(value: unknown): T }, timeoutMs: number, transport: Transport, environment: NodeJS.ProcessEnv): Promise<T> {
  const controller = new AbortController(); const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await transport(`${localBackendOrigin(environment)}${path}`, { ...init, redirect: "error", cache: "no-store", signal: controller.signal, headers: { ...init.headers, "X-API-Key": apiKey(environment), Accept: "application/json" } });
    if (!response.ok) throw mapStatus(response.status);
    const declaredLength = Number(response.headers.get("content-length") ?? 0); if (Number.isFinite(declaredLength) && declaredLength > 1_048_576) throw new BffError("MALFORMED_RESPONSE", 502, "The backend returned an invalid response.");
    const raw = await response.text(); if (raw.length > 1_048_576) throw new BffError("MALFORMED_RESPONSE", 502, "The backend returned an invalid response.");
    let body: unknown; try { body = JSON.parse(raw); } catch { throw new BffError("MALFORMED_RESPONSE", 502, "The backend returned an invalid response."); }
    try { return schema.parse(body); } catch { throw new BffError("MALFORMED_RESPONSE", 502, "The backend returned an invalid response."); }
  } catch (error) { if (error instanceof BffError) throw error; if (error instanceof Error && error.name === "AbortError") throw new BffError("TIMEOUT", 504, "The backend did not respond in time."); throw new BffError("BACKEND_UNAVAILABLE", 503, "The backend is temporarily unavailable."); }
  finally { clearTimeout(timeout); }
}

export async function queryThroughBff(input: QueryRequest, options: { transport?: Transport; environment?: NodeJS.ProcessEnv } = {}): Promise<QueryResponse> {
  const environment = options.environment ?? process.env; const mode = dataMode(environment);
  if (mode === "demo") return input.query.startsWith("Eligibility assessment:") ? eligibilityResponse : demoResponse;
  if (mode === "cloud") throw new BffError("CLOUD_ADAPTER_DISABLED", 503, "The future cloud adapter is not active.");
  return upstream("/query", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(input) }, queryResponseSchema, 90_000, options.transport ?? fetch, environment);
}

export async function sourcesThroughBff(url: URL, options: { transport?: Transport; environment?: NodeJS.ProcessEnv } = {}): Promise<SourcesResponse> {
  const parsed = sourceFiltersSchema.safeParse(Object.fromEntries(url.searchParams)); if (!parsed.success) throw new BffError("INVALID_REQUEST", 400, "Source filters are invalid.");
  const environment = options.environment ?? process.env; const mode = dataMode(environment); const filters = parsed.data;
  if (mode === "demo") return getDemoSources({ page: filters.page, pageSize: filters.page_size, search: filters.search, language: filters.language, hasEligibility: filters.has_eligibility === undefined ? undefined : filters.has_eligibility === "true" });
  if (mode === "cloud") throw new BffError("CLOUD_ADAPTER_DISABLED", 503, "The future cloud adapter is not active.");
  const parameters = new URLSearchParams(); Object.entries(filters).forEach(([key, value]) => { if (value !== undefined && value !== "") parameters.set(key, String(value)); });
  return upstream(`/sources?${parameters}`, { method: "GET" }, sourcesResponseSchema, 5_000, options.transport ?? fetch, environment);
}

export async function sourceThroughBff(id: string, options: { transport?: Transport; environment?: NodeJS.ProcessEnv } = {}): Promise<SourceDetail> {
  if (!/^[A-Za-z0-9-]{1,64}$/.test(id)) throw new BffError("INVALID_REQUEST", 400, "The source identifier is invalid.");
  const environment = options.environment ?? process.env; const mode = dataMode(environment);
  if (mode === "demo") { const source = getDemoSource(id); if (!source) throw new BffError("SOURCE_NOT_FOUND", 404, "The requested source was not found."); return sourceDetailSchema.parse(source); }
  if (mode === "cloud") throw new BffError("CLOUD_ADAPTER_DISABLED", 503, "The future cloud adapter is not active.");
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(id)) throw new BffError("INVALID_REQUEST", 400, "The source identifier is invalid.");
  return upstream(`/sources/${encodeURIComponent(id)}`, { method: "GET" }, sourceDetailSchema, 5_000, options.transport ?? fetch, environment);
}

// Milestone 4A-3 contract: a dedicated frontend service identity will obtain an
// audience-bound Google identity token server-side and attach both it and the
// SETU API key in memory. No service-account key or token is persisted here.

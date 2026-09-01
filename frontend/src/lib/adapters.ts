import { demoResponse } from "@/lib/fixtures";
import { errorResponseSchema, queryRequestSchema, queryResponseSchema, sourceDetailSchema, sourcesResponseSchema, type QueryAdapter, type SourceFilters } from "@/lib/contracts";

export class SetuClientError extends Error { constructor(public readonly code: string, message: string) { super(message); this.name = "SetuClientError"; } }

async function safeJson(response: Response): Promise<unknown> { return response.json().catch(() => null); }
async function parseResponse<T>(response: Response, schema: { safeParse(value: unknown): { success: true; data: T } | { success: false } }): Promise<T> {
  const body = await safeJson(response);
  if (!response.ok) { const parsedError = errorResponseSchema.safeParse(body); throw new SetuClientError(parsedError.success ? parsedError.data.error.code : "BACKEND_UNAVAILABLE", parsedError.success ? parsedError.data.error.message : "SETU could not complete the request."); }
  const parsed = schema.safeParse(body); if (!parsed.success) throw new SetuClientError("MALFORMED_RESPONSE", "SETU received an invalid response."); return parsed.data;
}

export const demoAdapter: QueryAdapter = { async query(input) { queryRequestSchema.parse(input); return queryResponseSchema.parse(demoResponse); } };
export const bffAdapter: QueryAdapter = { async query(input, signal) { const payload = queryRequestSchema.parse(input); const response = await fetch("/api/query", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload), signal }); return parseResponse(response, queryResponseSchema); } };
export const liveAdapter: QueryAdapter = { async query(input) { queryRequestSchema.parse(input); throw new SetuClientError("LIVE_NOT_CONFIGURED", "Live backend is not configured. Demo mode remains active."); } };
export async function fetchSources(filters: SourceFilters, signal?: AbortSignal) { const query = new URLSearchParams(); for (const [key, value] of Object.entries(filters)) if (value !== undefined && value !== "") query.set(key, String(value)); return parseResponse(await fetch(`/api/sources?${query}`, { signal }), sourcesResponseSchema); }
export async function fetchSource(id: string, signal?: AbortSignal) { return parseResponse(await fetch(`/api/sources/${encodeURIComponent(id)}`, { signal }), sourceDetailSchema); }

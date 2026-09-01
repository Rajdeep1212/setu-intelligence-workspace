import { NextResponse } from "next/server";
import { queryRequestSchema } from "@/lib/contracts";
import { BffError, dataMode, queryThroughBff, validateSameSite } from "@/lib/server/bff";

export const runtime = "nodejs";

export async function POST(request: Request) {
  const requestId = crypto.randomUUID();
  if (!validateSameSite(request)) return NextResponse.json({ error: { code: "INVALID_ORIGIN", message: "The request origin is not allowed.", request_id: requestId } }, { status: 403 });
  const length = Number(request.headers.get("content-length") ?? 0); if (Number.isFinite(length) && length > 8192) return NextResponse.json({ error: { code: "INVALID_REQUEST", message: "The request is too large.", request_id: requestId } }, { status: 413 });
  const raw = await request.text(); if (raw.length > 8192) return NextResponse.json({ error: { code: "INVALID_REQUEST", message: "The request is too large.", request_id: requestId } }, { status: 413 });
  let body: unknown = null; try { body = JSON.parse(raw); } catch { /* stable invalid request below */ }
  const parsed = queryRequestSchema.safeParse(body);
  if (!parsed.success) return NextResponse.json({ error: { code: "INVALID_REQUEST", message: "Enter a valid question of up to 2,000 characters.", request_id: requestId } }, { status: 400 });
  try { const mode = dataMode(); return NextResponse.json({ ...(await queryThroughBff(parsed.data)), data_mode: mode }, { headers: { "X-SETU-Data-Mode": mode } }); }
  catch (error) { const safe = error instanceof BffError ? error : new BffError("BACKEND_UNAVAILABLE", 503, "The backend is temporarily unavailable."); return NextResponse.json({ error: { code: safe.code, message: safe.message, request_id: requestId } }, { status: safe.status }); }
}

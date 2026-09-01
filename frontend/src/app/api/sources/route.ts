import { NextResponse } from "next/server";
import { BffError, dataMode, sourcesThroughBff } from "@/lib/server/bff";
export const runtime = "nodejs";
export async function GET(request: Request) { const requestId = crypto.randomUUID(); try { return NextResponse.json(await sourcesThroughBff(new URL(request.url)), { headers: { "X-SETU-Data-Mode": dataMode() } }); } catch (error) { const safe = error instanceof BffError ? error : new BffError("BACKEND_UNAVAILABLE", 503, "The backend is temporarily unavailable."); return NextResponse.json({ error: { code: safe.code, message: safe.message, request_id: requestId } }, { status: safe.status }); } }

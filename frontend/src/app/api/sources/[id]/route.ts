import { NextResponse } from "next/server";
import { BffError, dataMode, sourceThroughBff } from "@/lib/server/bff";
export const runtime = "nodejs";
export async function GET(_: Request, context: { params: Promise<{ id: string }> }) { const requestId = crypto.randomUUID(); try { const { id } = await context.params; return NextResponse.json(await sourceThroughBff(id), { headers: { "X-SETU-Data-Mode": dataMode() } }); } catch (error) { const safe = error instanceof BffError ? error : new BffError("BACKEND_UNAVAILABLE", 503, "The backend is temporarily unavailable."); return NextResponse.json({ error: { code: safe.code, message: safe.message, request_id: requestId } }, { status: safe.status }); } }

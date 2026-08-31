import { NextResponse } from "next/server";
import { demoResponse } from "@/lib/fixtures";
import { queryRequestSchema, queryResponseSchema } from "@/lib/contracts";

export const runtime = "nodejs";

export async function POST(request: Request) {
  const parsed = queryRequestSchema.safeParse(await request.json().catch(() => null));
  if (!parsed.success) return NextResponse.json({ error: { code: "INVALID_REQUEST", message: "Enter a valid question of up to 2,000 characters.", request_id: crypto.randomUUID() } }, { status: 400 });
  if ((process.env.SETU_DATA_MODE ?? "demo") !== "live") return NextResponse.json(queryResponseSchema.parse(demoResponse));
  const url = process.env.SETU_BACKEND_URL;
  const key = process.env.SETU_BACKEND_API_KEY;
  if (!url || !key) return NextResponse.json({ error: { code: "LIVE_NOT_CONFIGURED", message: "Live backend is not configured. Demo mode remains available.", request_id: crypto.randomUUID() } }, { status: 503 });
  return NextResponse.json({ error: { code: "LIVE_DISABLED", message: "Live forwarding is intentionally disabled in this foundation milestone.", request_id: crypto.randomUUID() } }, { status: 503 });
}

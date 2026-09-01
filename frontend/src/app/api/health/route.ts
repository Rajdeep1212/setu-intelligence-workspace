import { NextResponse } from "next/server";
import { dataMode } from "@/lib/server/bff";
export const runtime = "nodejs";
export async function GET() { return NextResponse.json({ status: "ok", mode: dataMode(), upstream_checked: false }, { headers: { "Cache-Control": "no-store" } }); }

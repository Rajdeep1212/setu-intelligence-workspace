import { demoResponse } from "@/lib/fixtures";
import { queryRequestSchema, queryResponseSchema, type DemoStage, type QueryAdapter } from "@/lib/contracts";
const stages: DemoStage[] = ["securing", "routing", "retrieving", "generating", "validating"];
export const demoAdapter: QueryAdapter = { async query(input, onStage) { queryRequestSchema.parse(input); for (const stage of stages) { onStage?.(stage); await new Promise((resolve) => window.setTimeout(resolve, 210)); } return queryResponseSchema.parse(demoResponse); } };
export const liveAdapter: QueryAdapter = { async query(input) { queryRequestSchema.parse(input); throw new Error("Live backend is not configured. Demo mode remains active."); } };

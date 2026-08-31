import { z } from "zod";
export const languageSchema = z.enum(["en", "hi", "bn"]);
export const queryRequestSchema = z.object({ query: z.string().trim().min(1).max(2000), language: languageSchema.optional() });
export const citationSchema = z.object({ chunk_id: z.string().min(1), document_id: z.string().min(1), title: z.string().nullable().optional(), url: z.url().nullable().optional(), snippet: z.string().nullable().optional() });
export const queryResponseSchema = z.object({ answer: z.string(), citations: z.array(citationSchema), route: z.enum(["retrieve_docs", "check_eligibility"]).nullable().optional(), confidence: z.number().min(0).max(1).nullable().optional() });
export const errorResponseSchema = z.object({ error: z.object({ code: z.string(), message: z.string(), request_id: z.string() }) });
export type QueryRequest = z.infer<typeof queryRequestSchema>;
export type QueryResponse = z.infer<typeof queryResponseSchema>;
export type Citation = z.infer<typeof citationSchema>;
export type WorkspaceMode = "research" | "eligibility";
export type DemoStage = "securing" | "routing" | "retrieving" | "generating" | "validating";
export interface QueryAdapter { query(input: QueryRequest, onStage?: (stage: DemoStage) => void): Promise<QueryResponse>; }

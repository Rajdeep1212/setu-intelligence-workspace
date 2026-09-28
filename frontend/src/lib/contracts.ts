import { z } from "zod";
export const languageSchema = z.enum(["en", "hi", "bn"]);
export const queryRequestSchema = z.object({
  query: z.string().max(2000).refine((value) => value.trim().length > 0, "Question must not be blank."),
  language: languageSchema.optional(),
  clarification_context: z.object({ original_query: z.string().min(1).max(2000).refine((value) => value.trim().length > 0) }).optional(),
});
export const citationSchema = z.object({ chunk_id: z.string().min(1), document_id: z.string().min(1), title: z.string().nullable().optional(), source: z.string().nullable().optional(), url: z.url().nullable().optional(), snippet: z.string().nullable().optional() });
export const answerSectionSchema = z.object({
  text: z.string().trim().min(1),
  kind: z.enum(["direct_answer", "benefit", "conditions", "how_to_apply", "next_steps", "required_documents", "limitations"]).nullable().optional(),
  citation_ids: z.array(z.string().min(1)).max(5).refine((ids) => new Set(ids).size === ids.length, "Section citation IDs must be unique."),
});
export const officialLinkSchema = z.object({
  kind: z.enum(["application", "status", "help"]),
  label: z.string().trim().min(1).max(120),
  url: z.url(),
});
export const queryResponseSchema = z.object({
  answer: z.string(),
  citations: z.array(citationSchema).max(5),
  sections: z.array(answerSectionSchema).max(12).default([]),
  official_links: z.array(officialLinkSchema).max(6).default([]),
  route: z.enum(["retrieve_docs", "check_eligibility"]).nullable().optional(),
  confidence: z.number().min(0).max(1).nullable().optional(),
  response_status: z.enum(["answered", "abstained", "clarification_needed", "eligibility_unverified"]).default("answered"),
  data_mode: z.enum(["demo", "local", "cloud"]).optional(),
}).superRefine((response, context) => {
  const citationIds = response.citations.map((citation) => citation.chunk_id);
  if (new Set(citationIds).size !== citationIds.length) context.addIssue({ code: "custom", path: ["citations"], message: "Citation chunk IDs must be unique." });
  const retrievedIds = new Set(response.citations.map((citation) => citation.chunk_id));
  response.sections.forEach((section, sectionIndex) => section.citation_ids.forEach((citationId, citationIndex) => {
    if (!retrievedIds.has(citationId)) context.addIssue({ code: "custom", path: ["sections", sectionIndex, "citation_ids", citationIndex], message: "Section citation ID is not present in retrieved citations." });
  }));
});
export const errorResponseSchema = z.object({ error: z.object({ code: z.string(), message: z.string(), request_id: z.string() }) });
export const safeMetadataSchema = z.record(z.string(), z.string());
export const eligibilitySummarySchema = z.object({
  scheme_name: z.string().min(1),
  criteria: z.record(z.string(), z.union([z.string(), z.number(), z.boolean(), z.array(z.string())])),
});
export const sourceSummarySchema = z.object({
  id: z.string().min(1), title: z.string().nullable().optional(), source: z.string().min(1), language: languageSchema,
  metadata: safeMetadataSchema, chunk_count: z.number().int().nonnegative(), eligibility_count: z.number().int().nonnegative(), has_eligibility: z.boolean(),
});
export const sourcesResponseSchema = z.object({
  items: z.array(sourceSummarySchema), page: z.number().int().positive(), page_size: z.number().int().min(1).max(25), total: z.number().int().nonnegative(), total_pages: z.number().int().nonnegative(),
});
export const sourceDetailSchema = sourceSummarySchema.extend({ eligibility: z.array(eligibilitySummarySchema) });
export const sourceFiltersSchema = z.object({
  page: z.coerce.number().int().min(1).max(10_000).default(1),
  page_size: z.coerce.number().int().min(1).max(25).default(6),
  search: z.string().trim().max(100).optional(), language: languageSchema.optional(),
  has_eligibility: z.enum(["true", "false"]).optional(),
});
export type QueryRequest = z.infer<typeof queryRequestSchema>;
export type ResponseLanguage = z.infer<typeof languageSchema>;
export type QueryResponse = z.infer<typeof queryResponseSchema>;
export type AnswerSection = z.infer<typeof answerSectionSchema>;
export type Citation = z.infer<typeof citationSchema>;
export type OfficialLink = z.infer<typeof officialLinkSchema>;
export type SourceSummary = z.infer<typeof sourceSummarySchema>;
export type SourceDetail = z.infer<typeof sourceDetailSchema>;
export type SourcesResponse = z.infer<typeof sourcesResponseSchema>;
export type SourceFilters = z.infer<typeof sourceFiltersSchema>;
export type WorkspaceMode = "research" | "eligibility";
export type ProcessingStage = "sending" | "working" | "extended";
export interface QueryAdapter { query(input: QueryRequest, signal?: AbortSignal): Promise<QueryResponse>; }

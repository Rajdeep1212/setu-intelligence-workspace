import { queryResponseSchema, sourceDetailSchema, sourcesResponseSchema, type QueryRequest } from "@/lib/contracts";
export const establishedQuestion: QueryRequest = { query: "What are the core components of India's digital approach?", language: "en" };
export const demoResponse = queryResponseSchema.parse({
  answer: "India's digital approach connects digital identity, payments and consent-based data exchange through interoperable public rails. Open interfaces allow these foundations to work as a shared stack, while the JAM foundation links identity, banking and connectivity.", route: "retrieve_docs", confidence: 0.9,
  response_status: "answered",
  data_mode: "demo",
  citations: [
    { chunk_id: "dpi-evidence-01", document_id: "dpi-brief-01", title: "India's Digital Public Infrastructure", source: "Press Information Bureau · demo fixture", url: "https://www.pib.gov.in/", snippet: "The source describes identity, payments and data exchange as connected through interoperable public rails." },
    { chunk_id: "dpi-evidence-02", document_id: "dpi-brief-01", title: "The rise of India's DPI stack", source: "Press Information Bureau · demo fixture", url: "https://www.pib.gov.in/", snippet: "The DPI stack is presented as a connected framework built with open interfaces and shared public infrastructure." },
    { chunk_id: "dpi-evidence-03", document_id: "dpi-brief-01", title: "JAM and inclusive digital delivery", source: "Press Information Bureau · demo fixture", url: "https://www.pib.gov.in/", snippet: "The evidence links the JAM foundation to identity, access to banking and digital connectivity." },
  ],
  sections: [
    { text: "India's digital approach connects digital identity, payments and consent-based data exchange through interoperable public rails.", citation_ids: ["dpi-evidence-01"] },
    { text: "Open interfaces allow these foundations to work as a shared stack, while the JAM foundation links identity, banking and connectivity.", citation_ids: ["dpi-evidence-02", "dpi-evidence-03"] },
  ],
});
export const suggestedQuestions = [establishedQuestion.query, "How do open APIs support India's DPI stack?", "What role does JAM play in digital delivery?"];

const demoSourceDetails = [
  { id: "dpi-brief-01", title: "India's Digital Public Infrastructure", source: "PIB", language: "en" as const, metadata: { posted_on: "Sanitized demo metadata" }, chunk_count: 80, eligibility_count: 0, has_eligibility: false, eligibility: [] },
  { id: "eligibility-source-01", title: "Post-Matric Scholarship criteria preview", source: "Illustrative demo fixture", language: "en" as const, metadata: { provenance_status: "Unverified demonstration data" }, chunk_count: 42, eligibility_count: 1, has_eligibility: true, eligibility: [{ scheme_name: "Post-Matric Scholarship preview", criteria: { status: "illustrative_unverified", production_requirement: "Reviewed, versioned rules linked to official-source provenance" } }] },
  { id: "eligibility-source-02", title: "PM Kisan criteria preview", source: "Illustrative demo fixture", language: "hi" as const, metadata: { provenance_status: "Unverified demonstration data" }, chunk_count: 61, eligibility_count: 1, has_eligibility: true, eligibility: [{ scheme_name: "PM Kisan preview", criteria: { status: "illustrative_unverified", production_requirement: "Reviewed, versioned rules linked to official-source provenance" } }] },
  { id: "eligibility-source-03", title: "Jan Dhan criteria preview", source: "Illustrative demo fixture", language: "bn" as const, metadata: { provenance_status: "Unverified demonstration data" }, chunk_count: 56, eligibility_count: 1, has_eligibility: true, eligibility: [{ scheme_name: "Jan Dhan preview", criteria: { status: "illustrative_unverified", production_requirement: "Reviewed, versioned rules linked to official-source provenance" } }] },
].map((item) => sourceDetailSchema.parse(item));

export function getDemoSource(id: string) { return demoSourceDetails.find((item) => item.id === id); }
export function getDemoSources({ page = 1, pageSize = 6, search = "", language, hasEligibility }: { page?: number; pageSize?: number; search?: string; language?: "en" | "hi" | "bn"; hasEligibility?: boolean }) {
  const needle = search.trim().toLowerCase();
  const filtered = demoSourceDetails.filter((item) => (!needle || `${item.title ?? ""} ${item.source}`.toLowerCase().includes(needle)) && (!language || item.language === language) && (hasEligibility === undefined || item.has_eligibility === hasEligibility));
  const start = (page - 1) * pageSize;
  return sourcesResponseSchema.parse({ items: filtered.slice(start, start + pageSize), page, page_size: pageSize, total: filtered.length, total_pages: filtered.length ? Math.ceil(filtered.length / pageSize) : 0 });
}

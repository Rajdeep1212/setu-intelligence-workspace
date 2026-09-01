import { queryResponseSchema, sourceDetailSchema, sourcesResponseSchema, type QueryRequest } from "@/lib/contracts";
export const establishedQuestion: QueryRequest = { query: "What are the core components of India's digital approach?", language: "en" };
export const demoResponse = queryResponseSchema.parse({
  answer: "India's digital approach connects digital identity, payments and consent-based data exchange through interoperable public rails. Open interfaces allow these foundations to work as a shared stack, while the JAM foundation links identity, banking and connectivity.", route: "retrieve_docs", confidence: 0.9,
  data_mode: "demo",
  citations: [
    { chunk_id: "dpi-evidence-01", document_id: "dpi-brief-01", title: "India's Digital Public Infrastructure", url: "https://www.pib.gov.in/", snippet: "The source describes identity, payments and data exchange as connected through interoperable public rails." },
    { chunk_id: "dpi-evidence-02", document_id: "dpi-brief-01", title: "The rise of India's DPI stack", url: "https://www.pib.gov.in/", snippet: "The DPI stack is presented as a connected framework built with open interfaces and shared public infrastructure." },
    { chunk_id: "dpi-evidence-03", document_id: "dpi-brief-01", title: "JAM and inclusive digital delivery", url: "https://www.pib.gov.in/", snippet: "The evidence links the JAM foundation to identity, access to banking and digital connectivity." },
  ],
});
export const answerSections = [
  { text: "India's digital approach connects digital identity, payments and consent-based data exchange through interoperable public rails.", citations: [0] },
  { text: "Open interfaces allow these foundations to work as a shared stack, while the JAM foundation links identity, banking and connectivity.", citations: [1, 2] },
] as const;
export const suggestedQuestions = [establishedQuestion.query, "How do open APIs support India's DPI stack?", "What role does JAM play in digital delivery?"];

export const eligibilityResponse = queryResponseSchema.parse({
  answer: "The supplied profile appears to satisfy the selected demo criteria. Review each criterion and its source before relying on this informational guidance.",
  route: "check_eligibility", confidence: 0.86, data_mode: "demo",
  citations: [{ chunk_id: "eligibility-evidence-01", document_id: "eligibility-source-01", title: "Sanitized scholarship criteria", url: null, snippet: "The stored criteria describe the family-income threshold and supported applicant categories." }],
});

const demoSourceDetails = [
  { id: "dpi-brief-01", title: "India's Digital Public Infrastructure", source: "PIB", language: "en" as const, metadata: { posted_on: "Sanitized demo metadata" }, chunk_count: 80, eligibility_count: 0, has_eligibility: false, eligibility: [] },
  { id: "eligibility-source-01", title: "Post-Matric Scholarship criteria", source: "PIB", language: "en" as const, metadata: { posted_on: "Sanitized demo metadata" }, chunk_count: 42, eligibility_count: 1, has_eligibility: true, eligibility: [{ scheme_name: "National Scholarship Portal — Post-Matric Scholarship", criteria: { max_family_income: 250000, eligible_categories: ["SC", "ST", "OBC", "minority", "as per current guidelines"], description: "Scholarship for post-matric students from specified categories." } }] },
  { id: "eligibility-source-02", title: "PM Kisan programme criteria", source: "PIB", language: "hi" as const, metadata: { posted_on: "Sanitized demo metadata" }, chunk_count: 61, eligibility_count: 1, has_eligibility: true, eligibility: [{ scheme_name: "PM Kisan Samman Nidhi", criteria: { max_landholding: "no upper limit as of latest guidelines — verify", excluded_categories: ["income tax payers", "institutional landholders"], description: "Income support for landholding farmer families." } }] },
  { id: "eligibility-source-03", title: "Jan Dhan programme criteria", source: "PIB", language: "bn" as const, metadata: { posted_on: "Sanitized demo metadata" }, chunk_count: 56, eligibility_count: 1, has_eligibility: true, eligibility: [{ scheme_name: "Pradhan Mantri Jan Dhan Yojana", criteria: { min_age: 10, documents_required: ["Aadhaar or any valid ID proof"], description: "Zero-balance bank account scheme for financial inclusion." } }] },
].map((item) => sourceDetailSchema.parse(item));

export function getDemoSource(id: string) { return demoSourceDetails.find((item) => item.id === id); }
export function getDemoSources({ page = 1, pageSize = 6, search = "", language, hasEligibility }: { page?: number; pageSize?: number; search?: string; language?: "en" | "hi" | "bn"; hasEligibility?: boolean }) {
  const needle = search.trim().toLowerCase();
  const filtered = demoSourceDetails.filter((item) => (!needle || `${item.title ?? ""} ${item.source}`.toLowerCase().includes(needle)) && (!language || item.language === language) && (hasEligibility === undefined || item.has_eligibility === hasEligibility));
  const start = (page - 1) * pageSize;
  return sourcesResponseSchema.parse({ items: filtered.slice(start, start + pageSize), page, page_size: pageSize, total: filtered.length, total_pages: filtered.length ? Math.ceil(filtered.length / pageSize) : 0 });
}

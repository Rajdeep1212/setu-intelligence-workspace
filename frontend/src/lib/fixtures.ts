import { queryResponseSchema, type QueryRequest } from "@/lib/contracts";
export const establishedQuestion: QueryRequest = { query: "What are the core components of India's digital approach?", language: "en" };
export const demoResponse = queryResponseSchema.parse({
  answer: "India's digital approach connects digital identity, payments and consent-based data exchange through interoperable public rails. Open interfaces allow these foundations to work as a shared stack, while the JAM foundation links identity, banking and connectivity.", route: "retrieve_docs", confidence: 0.9,
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

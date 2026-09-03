"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Group, Panel, Separator } from "react-resizable-panels";
import * as Dialog from "@radix-ui/react-dialog";
import { ArrowUp, Ban, BookOpen, CheckCircle2, ChevronLeft, ChevronRight, Command, Copy, Download, FileText, Home, Moon, PanelRight, Plus, Scale, Search, ShieldCheck, Sun, X } from "lucide-react";

import { SetuMark } from "@/components/setu-mark";
import { EligibilityWorkflow } from "@/components/workspace/eligibility-workflow";
import { bffAdapter, SetuClientError } from "@/lib/adapters";
import { queryRequestSchema, type ProcessingStage, type QueryRequest, type QueryResponse, type WorkspaceMode } from "@/lib/contracts";
import { demoResponse, establishedQuestion, suggestedQuestions } from "@/lib/fixtures";

const processingCopy: Record<ProcessingStage, { title: string; detail: string }> = {
  sending: { title: "Sending securely to the SETU BFF", detail: "The browser is waiting for a single non-streaming response." },
  working: { title: "Preparing an evidence-linked response", detail: "No backend stage or token stream is inferred without telemetry." },
  extended: { title: "The request is still processing", detail: "You can cancel this browser wait; upstream execution may continue." },
};

function safeError(reason: unknown): string {
  if (reason instanceof DOMException && reason.name === "AbortError") return "Browser wait cancelled. This does not imply that upstream work was cancelled.";
  if (reason instanceof SetuClientError) {
    const messages: Record<string, string> = { INVALID_REQUEST: "Check the question and supported language.", AUTHENTICATION_FAILED: "The server-side backend authentication failed.", TIMEOUT: "The backend did not respond within the bounded wait.", BACKEND_UNAVAILABLE: "The backend is temporarily unavailable.", MALFORMED_RESPONSE: "The backend returned a response that failed contract validation." };
    return messages[reason.code] ?? reason.message;
  }
  return "SETU could not complete the request.";
}

export function WorkspaceDemo() {
  const [mode, setMode] = useState<WorkspaceMode>("research");
  const [query, setQuery] = useState(establishedQuestion.query);
  const [result, setResult] = useState<QueryResponse>(demoResponse);
  const [activeCitation, setActiveCitation] = useState(0);
  const [processing, setProcessing] = useState<ProcessingStage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [commandOpen, setCommandOpen] = useState(false);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const [layout, setLayout] = useState<Record<string, number>>({ answer: 68, evidence: 32 });
  const [navCollapsed, setNavCollapsed] = useState(false);
  const controller = useRef<AbortController | null>(null);

  useEffect(() => { const frame = window.requestAnimationFrame(() => { if (window.localStorage.getItem("setu-theme") === "dark") setTheme("dark"); const supplied = new URLSearchParams(window.location.search).get("q"); if (supplied && supplied.length <= 2000) setQuery(supplied); }); return () => window.cancelAnimationFrame(frame); }, []);
  useEffect(() => { document.documentElement.dataset.theme = theme; window.localStorage.setItem("setu-theme", theme); }, [theme]);
  useEffect(() => { const frame = window.requestAnimationFrame(() => { const saved = window.localStorage.getItem("setu-panel-layout"); if (saved) { try { setLayout(JSON.parse(saved)); } catch { window.localStorage.removeItem("setu-panel-layout"); } } setNavCollapsed(window.localStorage.getItem("setu-nav-collapsed") === "true"); }); return () => window.cancelAnimationFrame(frame); }, []);
  useEffect(() => { const handler = (event: KeyboardEvent) => { if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") { event.preventDefault(); setEvidenceOpen(false); setCommandOpen((open) => !open); } }; window.addEventListener("keydown", handler); return () => window.removeEventListener("keydown", handler); }, []);

  const mutation = useMutation({
    retry: false,
    mutationFn: ({ input, signal }: { input: QueryRequest; signal: AbortSignal }) => bffAdapter.query(input, signal),
    onSuccess: (data) => { setResult(data); setActiveCitation(0); setProcessing(null); setError(null); },
    onError: (reason) => { setProcessing(null); setError(safeError(reason)); },
  });
  useEffect(() => { if (!mutation.isPending) return; const working = window.setTimeout(() => setProcessing("working"), 900); const extended = window.setTimeout(() => setProcessing("extended"), 10_000); return () => { window.clearTimeout(working); window.clearTimeout(extended); }; }, [mutation.isPending]);

  const submit = () => { if (mutation.isPending) return; const parsed = queryRequestSchema.safeParse({ query }); if (!parsed.success) { setError("Enter a valid question of up to 2,000 characters."); return; } const next = new AbortController(); controller.current = next; setError(null); setProcessing("sending"); mutation.mutate({ input: parsed.data, signal: next.signal }); };
  const active = result.citations[activeCitation];
  const citationIndexById = useMemo(() => new Map(result.citations.map((citation, index) => [citation.chunk_id, index])), [result.citations]);
  const displaySections = result.sections.length ? result.sections : [{ text: result.answer, citation_ids: [] }];
  const linkedSectionCount = displaySections.filter((section) => section.citation_ids.length > 0).length;
  const copyAnswer = async () => { await navigator.clipboard.writeText(result.answer); setCopied(true); window.setTimeout(() => setCopied(false), 1200); };
  const exportEvidence = () => { const blob = new Blob([JSON.stringify({ answer: result.answer, sections: result.sections, citations: result.citations, route: result.route, model_reported_confidence: result.confidence, response_status: result.response_status }, null, 2)], { type: "application/json" }); const url = URL.createObjectURL(blob); const anchor = document.createElement("a"); anchor.href = url; anchor.download = "setu-evidence.json"; anchor.click(); URL.revokeObjectURL(url); };
  const switchMode = (next: WorkspaceMode) => { if (mutation.isPending) return; setMode(next); setError(null); };

  return <div className={`workspace-shell ${navCollapsed ? "nav-collapsed" : ""}`}>
    <a className="skip-link" href="#workspace-answer">Skip to answer</a>
    <aside className="workspace-nav" aria-label="Workspace navigation">
      <Link href="/" className="brand-lockup" aria-label="SETU home"><SetuMark /><span><strong>SETU</strong><small>Intelligence Workspace</small></span></Link>
      <button type="button" aria-label="New investigation" onClick={() => { switchMode("research"); setQuery(""); setResult(demoResponse); }}><Plus size={16} /><span className="nav-text">New investigation</span><span className="nav-kbd">N</span></button>
      <p className="nav-section-label">Modes</p>
      <button type="button" aria-label="Research mode" className={mode === "research" ? "nav-active" : ""} onClick={() => switchMode("research")}><Search size={16} /><span className="nav-text">Research mode</span></button>
      <button type="button" aria-label="Eligibility mode" className={mode === "eligibility" ? "nav-active" : ""} onClick={() => switchMode("eligibility")}><Scale size={16} /><span className="nav-text">Eligibility mode</span></button>
      <p className="nav-section-label">Explore</p>
      <Link href="/workspace" className="nav-active" aria-label="Workspace"><Home size={16} /><span className="nav-text">Workspace</span></Link><Link href="/sources" aria-label="Sources"><BookOpen size={16} /><span className="nav-text">Sources</span></Link><Link href="/system" aria-label="System trust"><ShieldCheck size={16} /><span className="nav-text">System trust</span></Link>
      <div className="nav-spacer" /><button type="button" className="nav-secondary collapse-control" aria-label={navCollapsed ? "Expand navigation" : "Collapse navigation"} onClick={() => { const next = !navCollapsed; setNavCollapsed(next); window.localStorage.setItem("setu-nav-collapsed", String(next)); }}>{navCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}<span className="nav-text">Collapse rail</span></button>
      <button type="button" className="nav-secondary" onClick={() => setTheme(theme === "light" ? "dark" : "light")} aria-label={`Switch to ${theme === "light" ? "dark" : "light"} theme`}>{theme === "light" ? <Moon size={16} /> : <Sun size={16} />}<span className="nav-text">{theme === "light" ? "Dark" : "Light"} theme</span></button>
      <button type="button" className="nav-secondary" aria-label="Commands" onClick={() => setCommandOpen(true)}><Command size={16} /><span className="nav-text">Commands</span><span className="nav-kbd">Ctrl K</span></button>
    </aside>
    <main className="workspace-main">
      <header className="workspace-header"><div><h1>{mode === "research" ? "Research with retrieved evidence" : "Eligibility experience preview"}</h1><p>Secure BFF · server-controlled adapter</p></div><div className="header-meta"><button className="mobile-theme-trigger" type="button" onClick={() => setTheme(theme === "light" ? "dark" : "light")} aria-label={`Switch to ${theme === "light" ? "dark" : "light"} theme`}>{theme === "light" ? <Moon size={15} /> : <Sun size={15} />}</button>{mode === "research" && <button className="mobile-evidence-trigger" type="button" onClick={() => setEvidenceOpen(true)}><PanelRight size={15} /> Evidence</button>}<span className="mode-pill">{(result.data_mode ?? "demo").toUpperCase()}</span></div></header>
      {mode === "eligibility" ? <div id="workspace-answer" className="eligibility-pane"><EligibilityWorkflow /></div> :
        <Group className="workspace-panels" orientation="horizontal" id="setu-workspace-layout" defaultLayout={layout} onLayoutChanged={(next, meta) => { if (meta.isUserInteraction) window.localStorage.setItem("setu-panel-layout", JSON.stringify(next)); }}>
          <Panel id="answer" defaultSize="68%" minSize="50%"><section id="workspace-answer" className="answer-pane" aria-labelledby="investigation-title"><div className="answer-inner">
            <div className="question-kicker">Corpus investigation</div><h2 id="investigation-title">{query || "Ask a question about the established corpus"}</h2>
            <div className="answer-statusbar"><span className="grounded-pill"><CheckCircle2 size={13} /> {linkedSectionCount ? `${linkedSectionCount}/${displaySections.length} sections evidence linked` : "Insufficient evidence"}</span><div className="answer-actions"><button type="button" onClick={copyAnswer}><Copy size={13} /> {copied ? "Copied" : "Copy"}</button><button type="button" onClick={exportEvidence}><Download size={13} /> Export</button></div></div>
            {mutation.isPending && processing ? <div className="loading-stage" role="status" aria-live="polite"><strong>{processingCopy[processing].title}</strong><span>{processingCopy[processing].detail}</span>{processing === "extended" && <button type="button" className="cancel-wait" onClick={() => controller.current?.abort()}><Ban size={13} /> Cancel browser wait</button>}</div> : result.citations.length ?
              <article className="answer-card" aria-label="Generated answer with retrieved citations">{displaySections.map((section, sectionIndex) => <p className="answer-claim" key={`${section.text}-${sectionIndex}`}>{section.text}{section.citation_ids.map((citationId) => { const index = citationIndexById.get(citationId); if (index === undefined) return null; return <button key={citationId} type="button" className="citation-button" aria-label={`Focus retrieved citation ${index + 1} for claim ${sectionIndex + 1}`} aria-pressed={activeCitation === index} onClick={() => { setActiveCitation(index); if (window.innerWidth <= 680) setEvidenceOpen(true); }}>{String(index + 1).padStart(2, "0")}</button>; })}</p>)}</article> :
              <article className="answer-card unanswerable-state"><ShieldCheck /><h3>Insufficient retrieved evidence</h3><p>The response did not include validated retrieved citations, so SETU abstained.</p></article>}
            <div className="suggestions" aria-label="Suggested investigations">{suggestedQuestions.map((suggestion) => <button key={suggestion} type="button" onClick={() => setQuery(suggestion)}>{suggestion}</button>)}</div>{error && <div className="inline-error" role="alert">{error}</div>}
            <div className="composer-wrap"><p className="composer-language">Ask in English, हिन्दी, or বাংলা</p><form className="composer" onSubmit={(event) => { event.preventDefault(); submit(); }}><label htmlFor="workspace-query" className="sr-only">Ask SETU a question</label><textarea id="workspace-query" value={query} onChange={(event) => setQuery(event.target.value)} maxLength={2000} rows={2} placeholder="Ask about India's digital public infrastructure…" /><button type="submit" disabled={mutation.isPending || !query.trim()} aria-label="Run corpus investigation"><ArrowUp size={18} /></button></form><div className="composer-meta"><span>{mutation.isPending ? "One request in progress · retries disabled" : `${(result.data_mode ?? "demo").toUpperCase()} adapter · selected by server`}</span><span>{query.length} / 2,000</span></div></div>
          </div></section></Panel>
          <Separator className="resize-handle" aria-label="Resize evidence panel" /><Panel id="evidence" defaultSize="32%" minSize="25%" maxSize="45%"><EvidencePanel result={result} activeCitation={activeCitation} setActiveCitation={setActiveCitation} active={active} /></Panel>
        </Group>}
    </main>
    <Dialog.Root open={evidenceOpen} onOpenChange={setEvidenceOpen}><Dialog.Portal><Dialog.Overlay className="dialog-overlay" /><Dialog.Content className="mobile-evidence-sheet" aria-describedby="mobile-evidence-description"><Dialog.Title>Evidence inspector</Dialog.Title><Dialog.Description id="mobile-evidence-description">Retrieved citations linked by ID to specific answer sections. Membership does not prove semantic support.</Dialog.Description><Dialog.Close className="dialog-close" aria-label="Close evidence"><X size={17} /></Dialog.Close>{result.citations.map((citation, index) => <button key={citation.chunk_id} type="button" className={`evidence-card ${index === activeCitation ? "is-active" : ""}`} aria-pressed={index === activeCitation} onClick={() => setActiveCitation(index)}><span className="evidence-index">E{String(index + 1).padStart(2, "0")}</span><h3>{citation.title ?? "Untitled retrieved source"}</h3><strong className="evidence-publisher">{citation.source ?? "Publisher unavailable"}</strong><p>{citation.snippet}</p></button>)}</Dialog.Content></Dialog.Portal></Dialog.Root>
    <Dialog.Root open={commandOpen} onOpenChange={setCommandOpen}><Dialog.Portal><Dialog.Overlay className="dialog-overlay" /><Dialog.Content className="command-dialog" aria-describedby="command-description"><Dialog.Title>Navigate SETU</Dialog.Title><Dialog.Description id="command-description">Choose a workspace destination.</Dialog.Description><Dialog.Close className="dialog-close" aria-label="Close commands"><X size={17} /></Dialog.Close><div className="command-list"><button type="button" onClick={() => { switchMode("research"); setCommandOpen(false); }}><Search size={16} /><span>Research mode<small>Document retrieval with validated citation IDs</small></span></button><button type="button" onClick={() => { switchMode("eligibility"); setCommandOpen(false); }}><Scale size={16} /><span>Eligibility preview<small>Session-only interaction; no determination</small></span></button><Link href="/sources"><BookOpen size={16} /><span>Explore sources<small>Corpus lineage and criteria</small></span></Link></div></Dialog.Content></Dialog.Portal></Dialog.Root>
  </div>;
}

function EvidencePanel({ result, activeCitation, setActiveCitation, active }: { result: QueryResponse; activeCitation: number; setActiveCitation(index: number): void; active: QueryResponse["citations"][number] | undefined }) {
  const distinctDocuments = new Set(result.citations.map((citation) => citation.document_id)).size;
  return <aside className="evidence-pane" aria-label="Evidence inspector"><div className="evidence-heading"><div><h2>Evidence inspector</h2><p>Retrieved records; semantic support is not automatically proven</p></div><span className="evidence-count">{result.citations.length}</span></div>{result.citations.map((citation, index) => <div key={citation.chunk_id} className={`evidence-card ${index === activeCitation ? "is-active" : ""}`}><button type="button" className="evidence-focus" aria-pressed={index === activeCitation} onClick={() => setActiveCitation(index)}><div className="evidence-card-top"><span className="evidence-index">E{String(index + 1).padStart(2, "0")}</span><span className="evidence-verified"><CheckCircle2 size={11} /> Retrieved citation</span></div><h3>{citation.title ?? "Untitled retrieved source"}</h3><strong className="evidence-publisher">{citation.source ?? "Publisher unavailable"}</strong><p>{citation.snippet}</p></button><Link className="source-link" href={`/sources?source=${encodeURIComponent(citation.document_id)}`}><FileText size={11} /> Open source record</Link></div>)}<div className="evidence-summary"><dl><div><dt>Active citation</dt><dd>{active ? `E${String(activeCitation + 1).padStart(2, "0")}` : "none"}</dd></div><div><dt>Distinct source documents</dt><dd>{distinctDocuments}</dd></div><div><dt>Retrieval route</dt><dd>{result.route ?? "none"}</dd></div><div><dt>Model-reported confidence</dt><dd>{result.confidence === null || result.confidence === undefined ? "n/a" : `${result.confidence.toFixed(2)} · uncalibrated`}</dd></div><div><dt>Citation validation</dt><dd>{result.citations.length} membership checked</dd></div></dl></div></aside>;
}

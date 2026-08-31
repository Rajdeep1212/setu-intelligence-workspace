"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Group, Panel, Separator } from "react-resizable-panels";
import * as Dialog from "@radix-ui/react-dialog";
import { ArrowUp, BookOpen, CheckCircle2, ChevronLeft, ChevronRight, Command, Copy, Download, FileText, History, Home, Moon, PanelRight, Plus, Scale, Search, ShieldCheck, Sun, X } from "lucide-react";

import { SetuMark } from "@/components/setu-mark";
import { demoAdapter } from "@/lib/adapters";
import { answerSections, demoResponse, establishedQuestion, suggestedQuestions } from "@/lib/fixtures";
import type { DemoStage, QueryResponse, WorkspaceMode } from "@/lib/contracts";

const stageLabels: Record<DemoStage, string> = {
  securing: "Securing request",
  routing: "Selecting retrieval route",
  retrieving: "Searching private corpus",
  generating: "Generating grounded answer",
  validating: "Validating citations",
};

export function WorkspaceDemo() {
  const [mode, setMode] = useState<WorkspaceMode>("research");
  const [query, setQuery] = useState(establishedQuestion.query);
  const [result, setResult] = useState<QueryResponse>(demoResponse);
  const [activeCitation, setActiveCitation] = useState(0);
  const [stage, setStage] = useState<DemoStage | null>(null);
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [commandOpen, setCommandOpen] = useState(false);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const [layout, setLayout] = useState<Record<string, number>>({ answer: 68, evidence: 32 });
  const [navCollapsed, setNavCollapsed] = useState(false);

  useEffect(() => { if (window.localStorage.getItem("setu-theme") !== "dark") return; const frame = window.requestAnimationFrame(() => setTheme("dark")); return () => window.cancelAnimationFrame(frame); }, []);
  useEffect(() => { document.documentElement.dataset.theme = theme; window.localStorage.setItem("setu-theme", theme); }, [theme]);
  useEffect(() => { const saved = window.localStorage.getItem("setu-panel-layout"); if (!saved) return; try { const parsed = JSON.parse(saved); const frame = window.requestAnimationFrame(() => setLayout(parsed)); return () => window.cancelAnimationFrame(frame); } catch { window.localStorage.removeItem("setu-panel-layout"); } }, []);
  useEffect(() => { if (window.localStorage.getItem("setu-nav-collapsed") !== "true") return; const frame = window.requestAnimationFrame(() => setNavCollapsed(true)); return () => window.cancelAnimationFrame(frame); }, []);
  useEffect(() => { const handler = (event: KeyboardEvent) => { if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") { event.preventDefault(); setEvidenceOpen(false); setCommandOpen((open) => !open); } }; window.addEventListener("keydown", handler); return () => window.removeEventListener("keydown", handler); }, []);

  const mutation = useMutation({
    mutationFn: () => demoAdapter.query({ query, language: "en" }, setStage),
    onSuccess: (data) => { setResult(data); setActiveCitation(0); setStage(null); },
    onError: () => setStage(null),
  });
  const active = result.citations[activeCitation];
  const confidence = useMemo(() => Math.round((result.confidence ?? 0) * 100), [result.confidence]);
  const copyAnswer = async () => { await navigator.clipboard.writeText(result.answer); setCopied(true); window.setTimeout(() => setCopied(false), 1200); };
  const exportEvidence = () => { const blob = new Blob([JSON.stringify({ answer: result.answer, citations: result.citations, route: result.route, confidence: result.confidence }, null, 2)], { type: "application/json" }); const url = URL.createObjectURL(blob); const anchor = document.createElement("a"); anchor.href = url; anchor.download = "setu-demo-evidence.json"; anchor.click(); URL.revokeObjectURL(url); };

  return (
    <div className={`workspace-shell ${navCollapsed ? "nav-collapsed" : ""}`}>
      <a className="skip-link" href="#workspace-answer">Skip to answer</a>
      <aside className="workspace-nav" aria-label="Workspace navigation">
        <Link href="/" className="brand-lockup" aria-label="SETU home"><SetuMark /><span><strong>SETU</strong><small>Intelligence Workspace</small></span></Link>
        <button type="button" aria-label="New investigation" onClick={() => { setMode("research"); setQuery(""); setResult(demoResponse); setStage(null); }}><Plus size={16} /><span className="nav-text">New investigation</span><span className="nav-kbd">N</span></button>
        <p className="nav-section-label">Modes</p>
        <button type="button" aria-label="Research mode" className={mode === "research" ? "nav-active" : ""} onClick={() => setMode("research")}><Search size={16} /><span className="nav-text">Research mode</span></button>
        <button type="button" aria-label="Eligibility mode" className={mode === "eligibility" ? "nav-active" : ""} onClick={() => setMode("eligibility")}><Scale size={16} /><span className="nav-text">Eligibility mode</span></button>
        <p className="nav-section-label">Samples</p>
        <button type="button" aria-label="Load digital approach sample" onClick={() => { setMode("research"); setQuery(establishedQuestion.query); }}><History size={16} /><span className="nav-text sample-label">Digital approach</span></button>
        <p className="nav-section-label">Explore</p>
        <Link href="/workspace" className="nav-active" aria-label="Workspace"><Home size={16} /><span className="nav-text">Workspace</span></Link>
        <Link href="/sources" aria-label="Sources"><BookOpen size={16} /><span className="nav-text">Sources</span></Link>
        <Link href="/system" aria-label="System trust"><ShieldCheck size={16} /><span className="nav-text">System trust</span></Link>
        <div className="nav-spacer" />
        <button type="button" className="nav-secondary collapse-control" aria-label={navCollapsed ? "Expand navigation" : "Collapse navigation"} onClick={() => { const next = !navCollapsed; setNavCollapsed(next); window.localStorage.setItem("setu-nav-collapsed", String(next)); }}>{navCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}<span className="nav-text">Collapse rail</span></button>
        <button type="button" className="nav-secondary" onClick={() => setTheme(theme === "light" ? "dark" : "light")} aria-label={`Switch to ${theme === "light" ? "dark" : "light"} theme`}>{theme === "light" ? <Moon size={16} /> : <Sun size={16} />}<span className="nav-text">{theme === "light" ? "Dark" : "Light"} theme</span></button>
        <button type="button" className="nav-secondary" aria-label="Commands" onClick={() => setCommandOpen(true)}><Command size={16} /><span className="nav-text">Commands</span><span className="nav-kbd">⌘ K</span></button>
      </aside>

      <main className="workspace-main">
        <header className="workspace-header">
          <div><h1>Digital public infrastructure</h1><p>Established corpus · demo adapter</p></div>
          <div className="header-meta"><button className="mobile-theme-trigger" type="button" onClick={() => setTheme(theme === "light" ? "dark" : "light")} aria-label={`Switch to ${theme === "light" ? "dark" : "light"} theme`}>{theme === "light" ? <Moon size={15} /> : <Sun size={15} />}</button><button className="mobile-evidence-trigger" type="button" onClick={() => setEvidenceOpen(true)}><PanelRight size={15} /> Evidence</button><span className="mode-pill">DEMO</span><span className="route-pill">{result.route}</span></div>
        </header>
        <Group className="workspace-panels" orientation="horizontal" id="setu-workspace-layout" defaultLayout={layout} onLayoutChanged={(next, meta) => { if (meta.isUserInteraction) window.localStorage.setItem("setu-panel-layout", JSON.stringify(next)); }}>
          <Panel id="answer" defaultSize="68%" minSize="50%">
            <section id="workspace-answer" className="answer-pane" aria-labelledby="investigation-title">
              <div className="answer-inner">
                <div className="question-kicker">Established investigation · en-2</div>
                <h2 id="investigation-title">{mode === "research" ? establishedQuestion.query : "Check scheme eligibility with verified criteria"}</h2>
                <div className="answer-statusbar"><span className="grounded-pill" aria-label="Grounding passed: every material demo claim has supporting evidence"><CheckCircle2 size={13} /> Grounding passed</span><span className="confidence-pill" title="Historical model confidence for the validated demo answer">CONFIDENCE {confidence}%</span><span className="route-pill" title="The backend selected private document retrieval">ROUTE {result.route}</span><div className="answer-actions"><button type="button" onClick={copyAnswer}><Copy size={13} /> {copied ? "Copied" : "Copy"}</button><button type="button" onClick={exportEvidence}><Download size={13} /> Export</button></div></div>
                {mutation.isPending && stage ? (
                  <div className="loading-stage" role="status" aria-live="polite"><strong>{stageLabels[stage]}</strong><span>Demo pipeline · no external request</span></div>
                ) : (
                  mode === "eligibility" ? <article className="answer-card eligibility-preview" aria-label="Eligibility preview"><p className="mono-label">Preview state · no personal data collected</p><h3>Eligibility checks will separate rules from evidence.</h3><p>Select a scheme, review verified criteria, then evaluate a locally entered profile. This foundation intentionally stops before secure backend integration.</p><div className="criteria-grid"><span>Scheme rules</span><span>Evidence required</span><span>Decision trace</span></div></article> : <article className="answer-card" aria-label="Grounded answer">
                    {answerSections.map((section) => <p key={section.text}>{section.text}{section.citations.map((citation) => <button key={citation} type="button" className="citation-button" aria-label={`Focus evidence ${citation + 1}`} aria-pressed={activeCitation === citation} onClick={() => { setActiveCitation(citation); if (window.innerWidth <= 680) setEvidenceOpen(true); }}>{String(citation + 1).padStart(2, "0")}</button>)}</p>)}
                  </article>
                )}
                <div className="suggestions" aria-label="Suggested investigations">{suggestedQuestions.slice(1).map((suggestion) => <button key={suggestion} type="button" onClick={() => { setMode("research"); setQuery(suggestion); }}>{suggestion}</button>)}</div>
                {mutation.isError && <div className="inline-error" role="alert">The demo could not be prepared. No external request was sent.</div>}
                <div className="composer-wrap">
                  <form className="composer" onSubmit={(event) => { event.preventDefault(); mutation.mutate(); }}>
                    <label htmlFor="workspace-query" className="sr-only">Ask SETU a question</label>
                    <textarea id="workspace-query" value={query} onChange={(event) => setQuery(event.target.value)} maxLength={2000} rows={2} placeholder="Ask about India's digital public infrastructure…" />
                    <button type="submit" disabled={mutation.isPending || !query.trim()} aria-label="Run demo investigation"><ArrowUp size={18} /></button>
                  </form>
                  <div className="composer-meta"><span>Demo mode · sanitized fixture</span><span>{query.length} / 2,000</span></div>
                </div>
              </div>
            </section>
          </Panel>
          <Separator className="resize-handle" aria-label="Resize evidence panel" />
          <Panel id="evidence" defaultSize="32%" minSize="25%" maxSize="45%">
            <aside className="evidence-pane" aria-label="Evidence inspector">
              <div className="evidence-heading"><div><h2>Evidence inspector</h2><p>Source material, not model output</p></div><span className="evidence-count">{result.citations.length}</span></div>
              {result.citations.map((citation, index) => (
                <button key={citation.chunk_id} type="button" className={`evidence-card ${index === activeCitation ? "is-active" : ""}`} aria-pressed={index === activeCitation} onClick={() => setActiveCitation(index)}>
                  <div className="evidence-card-top"><span className="evidence-index">E{String(index + 1).padStart(2, "0")}</span><span className="evidence-verified"><CheckCircle2 size={11} /> Grounded fact</span></div>
                  <h3>{citation.title}</h3><p>{citation.snippet}</p><div className="doc-relation"><FileText size={11} /> DOCUMENT RELATION · {citation.document_id}</div>
                </button>
              ))}
              <div className="evidence-summary"><dl><div><dt>Active evidence</dt><dd>{active?.chunk_id ?? "none"}</dd></div><div><dt>Retrieval route</dt><dd>{result.route}</dd></div><div><dt>Confidence</dt><dd>{result.confidence?.toFixed(2)}</dd></div><div><dt>Validation</dt><dd>3 / 3 valid</dd></div></dl></div>
            </aside>
          </Panel>
        </Group>
      </main>
      <Dialog.Root open={evidenceOpen} onOpenChange={setEvidenceOpen}><Dialog.Portal><Dialog.Overlay className="dialog-overlay" /><Dialog.Content className="mobile-evidence-sheet" aria-describedby="mobile-evidence-description"><Dialog.Title>Evidence inspector</Dialog.Title><Dialog.Description id="mobile-evidence-description">Stored source chunks supporting the demo answer.</Dialog.Description><Dialog.Close className="dialog-close" aria-label="Close evidence"><X size={17} /></Dialog.Close>{result.citations.map((citation, index) => <button key={citation.chunk_id} type="button" className={`evidence-card ${index === activeCitation ? "is-active" : ""}`} onClick={() => setActiveCitation(index)}><span className="evidence-index">E{String(index + 1).padStart(2, "0")}</span><h3>{citation.title}</h3><p>{citation.snippet}</p></button>)}</Dialog.Content></Dialog.Portal></Dialog.Root>
      <Dialog.Root open={commandOpen} onOpenChange={setCommandOpen}><Dialog.Portal><Dialog.Overlay className="dialog-overlay" /><Dialog.Content className="command-dialog" aria-describedby="command-description"><Dialog.Title>Navigate SETU</Dialog.Title><Dialog.Description id="command-description">Choose a workspace destination or action.</Dialog.Description><Dialog.Close className="dialog-close" aria-label="Close commands"><X size={17} /></Dialog.Close><div className="command-list"><button type="button" onClick={() => { setMode("research"); setCommandOpen(false); }}><Search size={16} /><span>Research mode<small>Grounded document retrieval</small></span><kbd>R</kbd></button><button type="button" onClick={() => { setMode("eligibility"); setCommandOpen(false); }}><Scale size={16} /><span>Eligibility mode<small>Criteria-led preview</small></span><kbd>E</kbd></button><Link href="/sources"><BookOpen size={16} /><span>Explore sources<small>Corpus lineage and chunks</small></span></Link><Link href="/system"><ShieldCheck size={16} /><span>Review system trust<small>Security boundaries</small></span></Link></div></Dialog.Content></Dialog.Portal></Dialog.Root>
    </div>
  );
}

"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import * as Dialog from "@radix-ui/react-dialog";
import {
  ArrowUp,
  BookOpen,
  Check,
  Copy,
  Download,
  ExternalLink,
  Menu,
  Moon,
  MoreHorizontal,
  Scale,
  Search,
  ShieldCheck,
  SquarePen,
  Sun,
  X,
} from "lucide-react";

import { SetuMark } from "@/components/setu-mark";
import { EligibilityWorkflow } from "@/components/workspace/eligibility-workflow";
import { bffAdapter, SetuClientError } from "@/lib/adapters";
import {
  queryRequestSchema,
  type QueryRequest,
  type QueryResponse,
  type ResponseLanguage,
  type WorkspaceMode,
} from "@/lib/contracts";
import { demoResponse, establishedQuestion, suggestedQuestions } from "@/lib/fixtures";

const languageOptions: ReadonlyArray<{ code: ResponseLanguage; label: string }> = [
  { code: "en", label: "English" },
  { code: "hi", label: "हिंदी" },
  { code: "bn", label: "বাংলা" },
];
const languageStorageKey = "setu-response-language-v1";

function languageLabel(language: ResponseLanguage): string {
  return languageOptions.find((option) => option.code === language)?.label ?? "English";
}

const sectionLabels = {
  benefit: "Benefit",
  conditions: "Conditions",
  how_to_apply: "How to apply",
  next_steps: "Next steps",
  required_documents: "Documents",
  limitations: "Important limitations",
} as const;

function safeError(reason: unknown): string {
  if (reason instanceof DOMException && reason.name === "AbortError") {
    return "Browser wait cancelled. Upstream work may continue.";
  }
  if (reason instanceof SetuClientError) {
    const messages: Record<string, string> = {
      INVALID_REQUEST: "Check the question and try again.",
      invalid_request: "Check the question and try again.",
      AUTHENTICATION_FAILED: "The server could not authenticate this request.",
      TIMEOUT: "The backend did not respond within the bounded wait.",
      BACKEND_UNAVAILABLE: "SETU is temporarily unavailable.",
      MALFORMED_RESPONSE: "The response could not be safely displayed.",
    };
    return messages[reason.code] ?? reason.message;
  }
  return "SETU could not complete the request.";
}

function isOfficialSource(url: string): boolean {
  try {
    const hostname = new URL(url).hostname.toLowerCase();
    return hostname === "myscheme.gov.in" || hostname.endsWith(".gov.in") || hostname.endsWith(".nic.in");
  } catch {
    return false;
  }
}

function LanguageMenu({ language, onSelect }: { language: ResponseLanguage; onSelect(language: ResponseLanguage): void }) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const itemRefs = useRef<Array<HTMLButtonElement | null>>([]);

  const openAndFocus = (index = languageOptions.findIndex((option) => option.code === language)) => {
    setOpen(true);
    window.requestAnimationFrame(() => itemRefs.current[Math.max(index, 0)]?.focus());
  };

  useEffect(() => {
    if (!open) return;
    const closeOnOutsidePointer = (event: PointerEvent) => {
      const target = event.target;
      if (target instanceof Node && !menuRef.current?.contains(target) && !triggerRef.current?.contains(target)) {
        setOpen(false);
      }
    };
    document.addEventListener("pointerdown", closeOnOutsidePointer);
    return () => document.removeEventListener("pointerdown", closeOnOutsidePointer);
  }, [open]);

  const handleMenuKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const currentIndex = itemRefs.current.findIndex((item) => item === document.activeElement);
    let nextIndex: number | null = null;
    if (event.key === "ArrowDown") nextIndex = (currentIndex + 1) % languageOptions.length;
    if (event.key === "ArrowUp") nextIndex = (currentIndex - 1 + languageOptions.length) % languageOptions.length;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = languageOptions.length - 1;
    if (nextIndex !== null) {
      event.preventDefault();
      itemRefs.current[nextIndex]?.focus();
    } else if (event.key === "Escape") {
      event.preventDefault();
      setOpen(false);
      triggerRef.current?.focus();
    } else if (event.key === "Tab") {
      setOpen(false);
    }
  };

  return (
    <div className="language-control">
      <button
        ref={triggerRef}
        type="button"
        className="composer-menu-trigger"
        aria-label={`Response language: ${languageLabel(language)}`}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => (open ? setOpen(false) : openAndFocus())}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            openAndFocus(event.key === "ArrowDown" ? 0 : undefined);
          }
        }}
      >
        <MoreHorizontal size={20} aria-hidden="true" />
      </button>
      {open && (
        <div ref={menuRef} className="language-menu" role="menu" aria-label="Response language" onKeyDown={handleMenuKeyDown}>
          <p>Response language</p>
          {languageOptions.map((option, index) => (
            <button
              key={option.code}
              ref={(element) => { itemRefs.current[index] = element; }}
              type="button"
              role="menuitemradio"
              aria-checked={language === option.code}
              tabIndex={-1}
              onClick={() => {
                onSelect(option.code);
                setOpen(false);
                triggerRef.current?.focus();
              }}
            >
              <span lang={option.code}>{option.label}</span>
              {language === option.code && <Check size={15} aria-hidden="true" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function WorkspaceDemo() {
  const [mode, setMode] = useState<WorkspaceMode>("research");
  const [query, setQuery] = useState(establishedQuestion.query);
  const [submittedQuery, setSubmittedQuery] = useState(establishedQuestion.query);
  const [responseLanguage, setResponseLanguage] = useState<ResponseLanguage>("en");
  const [submittedLanguage, setSubmittedLanguage] = useState<ResponseLanguage>("en");
  const [result, setResult] = useState<QueryResponse | null>(demoResponse);
  const [activeCitation, setActiveCitation] = useState(0);
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [commandOpen, setCommandOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const [clarificationContext, setClarificationContext] = useState<QueryRequest["clarification_context"]>();
  const controller = useRef<AbortController | null>(null);
  const sourceRefs = useRef<Record<string, HTMLElement | null>>({});
  const citationFocusRequested = useRef(false);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      if (window.localStorage.getItem("setu-theme") === "dark") setTheme("dark");
      const savedLanguage = window.localStorage.getItem(languageStorageKey);
      if (savedLanguage === "en" || savedLanguage === "hi" || savedLanguage === "bn") setResponseLanguage(savedLanguage);
      const supplied = new URLSearchParams(window.location.search).get("q");
      if (supplied && supplied.length <= 2000) setQuery(supplied);
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem("setu-theme", theme);
  }, [theme]);

  useEffect(() => {
    const handler = (event: globalThis.KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setCommandOpen((open) => !open);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  useEffect(() => {
    if (!sourcesOpen || !citationFocusRequested.current) return;
    const frame = window.requestAnimationFrame(() => {
      const source = sourceRefs.current[`source-${activeCitation}`];
      source?.scrollIntoView({ behavior: "smooth", block: "center" });
      source?.focus({ preventScroll: true });
      citationFocusRequested.current = false;
    });
    return () => window.cancelAnimationFrame(frame);
  }, [activeCitation, sourcesOpen]);

  const mutation = useMutation({
    retry: false,
    mutationFn: ({ input, signal }: { input: QueryRequest; signal: AbortSignal }) => bffAdapter.query(input, signal),
    onSuccess: (data, { input, signal }) => {
      if (signal.aborted || controller.current?.signal !== signal) return;
      setResult(data);
      setSubmittedQuery(input.clarification_context ? `${input.clarification_context.original_query}\n${input.query}` : input.query);
      setSubmittedLanguage(input.language ?? "en");
      setClarificationContext(data.response_status === "clarification_needed" ? (input.clarification_context ?? { original_query: input.query }) : undefined);
      setCopied(false);
      setActiveCitation(0);
      setSourcesOpen(false);
      setDetailsOpen(false);
      setError(null);
    },
    onError: (reason, { signal }) => {
      if (controller.current?.signal === signal) setError(safeError(reason));
    },
    onSettled: (_data, _error, { signal }) => {
      if (controller.current?.signal === signal) controller.current = null;
    },
  });

  const selectLanguage = (language: ResponseLanguage) => {
    setResponseLanguage(language);
    window.localStorage.setItem(languageStorageKey, language);
  };

  const submit = () => {
    if (controller.current || mutation.isPending) return;
    const parsed = queryRequestSchema.safeParse({ query, language: responseLanguage, ...(clarificationContext ? { clarification_context: clarificationContext } : {}) });
    if (!parsed.success) {
      setError("Enter a valid question of up to 2,000 characters.");
      return;
    }
    const next = new AbortController();
    controller.current = next;
    setError(null);
    mutation.mutate({ input: parsed.data, signal: next.signal });
  };

  const focusCitation = (index: number) => {
    citationFocusRequested.current = true;
    setActiveCitation(index);
    setSourcesOpen(true);
  };

  const copyAnswer = async () => {
    if (!result) return;
    await navigator.clipboard.writeText(result.answer);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1200);
  };

  const exportEvidence = () => {
    if (!result) return;
    const blob = new Blob([JSON.stringify({
      question: submittedQuery,
      response_language: submittedLanguage,
      answer: result.answer,
      sections: result.sections,
      citations: result.citations,
      official_links: result.official_links,
      route: result.route,
      model_reported_confidence: result.confidence,
      response_status: result.response_status,
    }, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "setu-evidence.json";
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const switchMode = (next: WorkspaceMode) => {
    if (mutation.isPending) return;
    setMode(next);
    setError(null);
  };

  const startNewQuestion = () => {
    if (mutation.isPending) return;
    setQuery("");
    setSubmittedQuery("");
    setResult(null);
    setClarificationContext(undefined);
    setError(null);
    setSourcesOpen(false);
    setDetailsOpen(false);
  };

  const displaySections = result ? (result.sections.length ? result.sections : [{ text: result.answer, citation_ids: [] }])
    .filter((section, index, sections) => section.text.trim() && sections.findIndex((candidate) => candidate.text.trim() === section.text.trim()) === index)
    .sort((a, b) => Number(b.kind === "direct_answer") - Number(a.kind === "direct_answer")) : [];
  const hasCitedAnswer = result?.response_status === "answered" && result.citations.length > 0;
  const sourceLinks = result?.citations.filter((citation, index, citations) => (
    citation.url && citations.findIndex((candidate) => candidate.url === citation.url) === index
  )) ?? [];

  return (
    <div className="workspace-shell conversation-workspace">
      <a className="skip-link" href="#workspace-answer">Skip to answer</a>
      <header className="conversation-header">
        <Link href="/" className="brand-lockup" aria-label="SETU home"><SetuMark /><span><strong>SETU</strong><small>Evidence for public services</small></span></Link>
        <nav aria-label="Workspace navigation">
          <Link className="active" href="/workspace"><Search size={15} /> Ask</Link>
          <Link href="/sources"><BookOpen size={15} /> Sources</Link>
          <Link href="/system"><ShieldCheck size={15} /> Trust</Link>
        </nav>
        <div className="conversation-actions">
          <button type="button" className="conversation-icon" aria-label="New question" disabled={mutation.isPending} onClick={startNewQuestion}><SquarePen size={17} /></button>
          <button type="button" className="conversation-icon" aria-label={`Switch to ${theme === "light" ? "dark" : "light"} theme`} onClick={() => setTheme(theme === "light" ? "dark" : "light")}>
            {theme === "light" ? <Moon size={16} /> : <Sun size={16} />}
          </button>
          <button type="button" className="conversation-icon mobile-menu-button" aria-label="Open commands" onClick={() => setCommandOpen(true)}><Menu size={17} /></button>
        </div>
      </header>

      {mode === "eligibility" ? (
        <main className="eligibility-pane conversation-eligibility"><EligibilityWorkflow /></main>
      ) : (
        <main className="conversation-main">
          <div className="conversation-column">
            <section className="conversation-intro" aria-labelledby="investigation-title">
              <p className="mono-label">Ask SETU</p>
              <h1 id="investigation-title">Understand government information in your language.</h1>
              <p>Ask about the public systems and services represented in SETU&apos;s available sources.</p>
            </section>

            <section id="workspace-answer" className="conversation-answer" aria-labelledby="question-title">
              <div className="question-label">{result?.data_mode === "demo" ? "Illustrative example — not a retrieved answer" : submittedQuery ? "Your question" : "Ready for a question"}</div>
              <h2 id="question-title">{submittedQuery || "Ask about the available sources"}</h2>

              {mutation.isPending ? (
                <div className="conversation-loading" role="status" aria-live="polite">
                  <span className="loading-mark" aria-hidden="true" />
                  <div><strong>Request in progress</strong><p>Waiting for a single evidence-linked server response.</p></div>
                  <button type="button" onClick={() => controller.current?.abort()}>Stop waiting</button>
                </div>
              ) : hasCitedAnswer && result ? (
                <article className="conversation-answer-copy" lang={submittedLanguage} aria-label="Generated answer with retrieved citations">
                  {displaySections.map((section, sectionIndex) => (
                    <section key={`${section.text}-${sectionIndex}`}>
                      {section.kind && section.kind !== "direct_answer" && <h3>{sectionLabels[section.kind]}</h3>}
                      <p>
                        {section.text}
                        {section.citation_ids.map((citationId) => {
                          const index = result.citations.findIndex((citation) => citation.chunk_id === citationId);
                          if (index < 0) return null;
                          return <button key={citationId} type="button" className="inline-citation" aria-label={`Open source ${index + 1} for claim ${sectionIndex + 1}`} onClick={() => focusCitation(index)}>{index + 1}</button>;
                        })}
                      </p>
                    </section>
                  ))}
                </article>
              ) : result ? (
                <article className="conversation-abstention" lang={submittedLanguage}>
                  <ShieldCheck size={22} aria-hidden="true" />
                  <div><h3>{result.response_status === "clarification_needed" ? "Clarification needed" : "SETU stopped without a cited answer"}</h3><p>{result.answer}</p></div>
                </article>
              ) : (
                <div className="conversation-empty">Choose an example below or type a question. Retrieval starts automatically when you submit.</div>
              )}

              {result && (sourceLinks.length > 0 || result.official_links.length > 0) && <nav className="answer-links" aria-label="Official source and service links">
                <h3>Official links</h3>
                {sourceLinks.map((citation) => <a key={citation.url} href={citation.url ?? undefined} target="_blank" rel="noreferrer">
                  <span>{isOfficialSource(citation.url ?? "") ? "Official source" : "Source"}: {citation.title ?? citation.source ?? "Retrieved document"}</span><ExternalLink size={13} />
                </a>)}
                {result.official_links.map((link) => <a key={`${link.kind}-${link.url}`} href={link.url} target="_blank" rel="noreferrer" data-link-kind={link.kind}>
                  <span>{link.label}</span><ExternalLink size={13} />
                </a>)}
              </nav>}

              {result && <div className="answer-toolbar">
                <button type="button" onClick={copyAnswer}>{copied ? <Check size={14} /> : <Copy size={14} />} {copied ? "Copied" : "Copy answer"}</button>
                <button type="button" onClick={exportEvidence}><Download size={14} /> Export evidence</button>
              </div>}
            </section>

            {result && <section className="disclosure-section">
              <button type="button" className="disclosure-toggle" aria-expanded={sourcesOpen} onClick={() => setSourcesOpen((open) => !open)}>
                <span><strong>Sources</strong><small>{result.citations.length} retrieved {result.citations.length === 1 ? "record" : "records"}</small></span>
                <span className="disclosure-chevron" aria-hidden="true">{sourcesOpen ? "−" : "+"}</span>
              </button>
              {sourcesOpen && <div className="source-list" role="region" aria-label="Retrieved sources">
                {result.citations.length ? result.citations.map((citation, index) => (
                  <article className={`conversation-source ${index === activeCitation ? "is-active" : ""}`} id={`source-${index}`} ref={(element) => { sourceRefs.current[`source-${index}`] = element; }} tabIndex={-1} key={citation.chunk_id}>
                    <div className="source-number">{index + 1}</div>
                    <div>
                      <p className="source-type">{citation.source ?? "Source unavailable"}{citation.url && <span> · {isOfficialSource(citation.url) ? "Official source" : "Source link"}</span>}</p>
                      <h3>{citation.title ?? "Untitled retrieved source"}</h3>
                      <p className="source-snippet">&quot;{citation.snippet ?? "No excerpt available."}&quot;</p>
                      {citation.url && <a href={citation.url} target="_blank" rel="noreferrer">View source <ExternalLink size={13} /></a>}
                    </div>
                  </article>
                )) : <p className="no-sources">No source passage was cited for this response.</p>}
              </div>}
            </section>}

            {result && <section className="disclosure-section technical-section">
              <button type="button" className="disclosure-toggle" aria-expanded={detailsOpen} onClick={() => setDetailsOpen((open) => !open)}>
                <span><strong>Technical details</strong><small>How this response was assembled</small></span>
                <span className="disclosure-chevron" aria-hidden="true">{detailsOpen ? "−" : "+"}</span>
              </button>
              {detailsOpen && <div className="technical-details">
                <dl>
                  <div><dt>Route</dt><dd>{result.route ?? "Not available"}</dd></div>
                  <div><dt>Data mode</dt><dd>{(result.data_mode ?? "demo").toUpperCase()}</dd></div>
                  <div><dt>Answer sections</dt><dd>{displaySections.length}</dd></div>
                  <div><dt>Citations</dt><dd>{result.citations.length} membership checked</dd></div>
                  {result.confidence !== null && result.confidence !== undefined && <div><dt>Model-reported confidence</dt><dd>{result.confidence.toFixed(2)} · uncalibrated</dd></div>}
                </dl>
                <p>Citation membership confirms that an ID came from the retrieved set; it does not independently prove semantic support.</p>
              </div>}
            </section>}

            <section className="explore-section" aria-labelledby="explore-heading">
              <p className="mono-label">Continue exploring</p><h2 id="explore-heading">Example questions</h2>
              <div className="explore-list">{suggestedQuestions.map((suggestion) => <button key={suggestion} type="button" onClick={() => setQuery(suggestion)}>{suggestion}<span aria-hidden="true">→</span></button>)}</div>
            </section>

            <div className="conversation-composer-wrap">
              {error && <div className="inline-error" role="alert">{error}</div>}
              {clarificationContext && <p role="status">Replying to the clarification. Use New question to start a different topic.</p>}
              <form className="conversation-composer" onSubmit={(event) => { event.preventDefault(); submit(); }}>
                <label htmlFor="workspace-query" className="sr-only">Ask SETU a question</label>
                <textarea id="workspace-query" value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); submit(); }
                }} maxLength={2000} rows={3} placeholder="Ask about the public information in SETU’s sources…" />
                <div className="composer-controls">
                  <LanguageMenu language={responseLanguage} onSelect={selectLanguage} />
                  <button type="submit" className="composer-submit" disabled={mutation.isPending || !query.trim()} aria-label="Ask SETU"><ArrowUp size={19} /></button>
                </div>
              </form>
              <div className="composer-meta"><span>{mutation.isPending ? "One request in progress" : "Available sources only"}</span><span>{query.length} / 2,000</span></div>
            </div>
          </div>
        </main>
      )}

      <Dialog.Root open={commandOpen} onOpenChange={setCommandOpen}><Dialog.Portal>
        <Dialog.Overlay className="dialog-overlay" />
        <Dialog.Content className="command-dialog" aria-describedby="command-description">
          <Dialog.Title>Navigate SETU</Dialog.Title><Dialog.Description id="command-description">Choose a workspace destination.</Dialog.Description>
          <Dialog.Close className="dialog-close" aria-label="Close commands"><X size={17} /></Dialog.Close>
          <div className="command-list">
            <button type="button" onClick={() => { switchMode("research"); setCommandOpen(false); }}><Search size={16} /><span>Ask SETU<small>Research with retrieved evidence</small></span></button>
            <button type="button" onClick={() => { switchMode("eligibility"); setCommandOpen(false); }}><Scale size={16} /><span>Eligibility preview<small>Illustrative only; no determination</small></span></button>
            <Link href="/sources"><BookOpen size={16} /><span>Explore sources<small>Corpus lineage and records</small></span></Link>
          </div>
        </Dialog.Content>
      </Dialog.Portal></Dialog.Root>
    </div>
  );
}

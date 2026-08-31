import Link from "next/link";
import { ArrowRight, CheckCircle2, Clock3, Quote } from "lucide-react";
import { SiteShell } from "@/components/site-shell";

const decisions = [
  ["Problem", "Useful answers were insufficient without a visible chain back to the small, validated corpus."],
  ["Product hypothesis", "Put answer, route, confidence, and source evidence in one working surface so trust can be inspected immediately."],
  ["Architecture", "An IAM-protected Cloud Run API retrieves from private Cloud SQL; the browser-facing BFF keeps credentials server-side."],
  ["Security design", "Private networking, least-privilege identities, sealed secrets, immutable images, and no public principal form the boundary."],
  ["Recovery discipline", "Interrupted hardening and deployment work was reconciled before any single retry; historical failed revisions remain evidence."],
  ["Evaluation", "One authenticated en-2 execution returned 200 with three valid citations, 0.9 confidence, and no unsupported numeric claim."],
];
const limitations = ["Approximately 69-second validated query latency", "No production query_logs insertion", "No exact successful provider-attempt telemetry", "Word-form numbers are outside the digit-expression guard", "Scale-to-zero cold starts and an approximately 3.37 GB image"];

export const metadata = { title: "Case study" };
export default function CaseStudyPage() { return <SiteShell section="case-study" eyebrow="Validated journey · en-2" title="From one question to auditable evidence" intro="A concise engineering case study of one authenticated query moving through routing, retrieval, grounded generation, and citation review—without claims of production scale or adoption.">
  <section className="case-hero"><div><Quote size={26} /><blockquote>What are the core components of India&apos;s digital approach?</blockquote><p>The answer connected digital identity, payments, data exchange, open interfaces, and the JAM foundation—with every material claim traceable to stored evidence.</p></div><dl><div><dt>HTTP result</dt><dd>200</dd></div><div><dt>Route</dt><dd>retrieve_docs</dd></div><div><dt>Confidence</dt><dd>0.90</dd></div><div><dt>Citations</dt><dd>3 valid</dd></div></dl></section>
  <section className="decision-grid" aria-label="Engineering case study details">{decisions.map(([title, body]) => <article key={title}><p className="mono-label">{title}</p><p>{body}</p></article>)}</section>
  <section className="journey" aria-labelledby="journey-title"><div className="section-heading"><div><p className="mono-label">Request path</p><h2 id="journey-title">One controlled execution</h2></div><span className="count-badge"><Clock3 size={12} /> 69.138s end to end</span></div>{["Authenticated request accepted", "Retrieval route selected", "Private corpus evidence retrieved", "Grounded response generated", "Citations and numeric claim validated"].map((item, index) => <div className="journey-step" key={item}><span>{String(index + 1).padStart(2, "0")}</span><strong>{item}</strong><CheckCircle2 size={16} /></div>)}</section>
  <section className="case-limitations"><div><p className="mono-label">Current limitations</p><h2>What the evidence does not claim</h2></div><ul>{limitations.map((item) => <li key={item}>{item}</li>)}</ul></section>
  <section className="case-close"><div><p className="mono-label">Roadmap</p><h2>Secure integration, then deeper evidence exploration.</h2><p>The next milestone connects the BFF to the proven backend, turns eligibility preview into a secure experience, and expands evidence navigation without weakening the established boundary.</p></div><Link className="button button-primary" href="/workspace">Explore the demo <ArrowRight size={15} /></Link></section>
</SiteShell>; }

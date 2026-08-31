import Link from "next/link";
import { ArrowRight, Database, LockKeyhole, Waypoints } from "lucide-react";
import { SetuMark } from "@/components/setu-mark";
import { Button } from "@/components/ui/button";

export default function Home() {
  return (
    <main className="landing-shell">
      <a className="skip-link" href="#main-content">Skip to content</a>
      <header className="landing-nav" aria-label="Primary navigation">
        <Link href="/" className="brand-lockup" aria-label="SETU home"><SetuMark /><span><strong>SETU</strong><small>Intelligence Workspace</small></span></Link>
        <nav><Link href="/sources">Sources</Link><Link href="/system">System trust</Link><Link href="/case-study">Case study</Link></nav>
        <Button asChild size="sm"><Link href="/workspace">Open workspace <ArrowRight size={15} aria-hidden="true" /></Link></Button>
      </header>
      <section id="main-content" className="landing-hero">
        <div className="hero-copy">
          <div className="eyebrow"><span className="status-dot" /> Evidence-backed civic intelligence</div>
          <h1>Understand India&apos;s digital public infrastructure through its evidence.</h1>
          <p className="hero-lede">Ask policy and product questions, trace every material claim to the corpus, and inspect the retrieval path—not just the generated answer.</p>
          <div className="hero-actions"><Button asChild><Link href="/workspace">Open workspace <ArrowRight size={17} aria-hidden="true" /></Link></Button><Button asChild variant="secondary"><Link href="/case-study">Read the engineering case</Link></Button></div>
          <div className="trust-row" aria-label="System trust summary"><span><LockKeyhole size={15} /> IAM protected</span><span><Database size={15} /> Private corpus</span><span><Waypoints size={15} /> Citation validated</span></div>
        </div>
        <div className="investigation-preview" aria-label="Example grounded investigation">
          <div className="preview-topline"><span className="mono-label">INVESTIGATION / EN-2</span><span className="verified-pill"><span /> Grounded</span></div>
          <p className="preview-query">What are the core components of India&apos;s digital approach?</p>
          <div className="rail-divider"><span /><i /><span /><i /><span /></div>
          <div className="preview-answer"><p>India&apos;s approach connects digital identity, payments and data exchange through interoperable public rails.</p><div className="citation-strip"><span>01</span><span>02</span><span>03</span><small>3 linked evidence records</small></div></div>
          <dl className="preview-metrics"><div><dt>Route</dt><dd>retrieve_docs</dd></div><div><dt>Confidence</dt><dd>0.90</dd></div><div><dt>Grounding</dt><dd>Passed</dd></div></dl>
        </div>
      </section>
    </main>
  );
}

import Link from "next/link";
import type { ReactNode } from "react";
import { ArrowLeft, BookOpen, BriefcaseBusiness, ShieldCheck } from "lucide-react";
import { SetuMark } from "@/components/setu-mark";
import { ThemeToggle } from "@/components/theme-toggle";

export function SiteShell({ section, eyebrow, title, intro, children }: { section: string; eyebrow: string; title: string; intro: string; children: ReactNode }) {
  return <div className="site-shell"><a className="skip-link" href="#content">Skip to content</a><header className="site-header"><Link href="/" className="brand-lockup"><SetuMark /><span><strong>SETU</strong><small>Intelligence Workspace</small></span></Link><nav aria-label="Primary"><Link href="/workspace">Workspace</Link><Link className={section === "sources" ? "active" : ""} href="/sources"><BookOpen size={14} /> Sources</Link><Link className={section === "system" ? "active" : ""} href="/system"><ShieldCheck size={14} /> System</Link><Link className={section === "case-study" ? "active" : ""} href="/case-study"><BriefcaseBusiness size={14} /> Case study</Link></nav><ThemeToggle compact /></header><main id="content" className="site-main"><Link href="/workspace" className="back-link"><ArrowLeft size={14} /> Back to workspace</Link><div className="page-heading"><p className="mono-label">{eyebrow}</p><h1>{title}</h1><p>{intro}</p></div>{children}</main></div>;
}

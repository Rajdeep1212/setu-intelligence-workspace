import { CheckCircle2, Cloud, Database, KeyRound, LockKeyhole, Network, Route, ShieldCheck } from "lucide-react";
import { SiteShell } from "@/components/site-shell";

const controls = [
  { icon: LockKeyhole, title: "IAM-authenticated access", body: "No public principal. Requests require an authorized identity before application authentication." },
  { icon: Network, title: "Private data path", body: "The application reaches Cloud SQL over private networking; the database has no public address or authorized network." },
  { icon: KeyRound, title: "Sealed secrets", body: "Runtime access is scoped per secret. Values never enter browser-visible configuration or this demo fixture." },
  { icon: Database, title: "Read-only runtime", body: "The runtime database identity retains only the privileges required for grounded retrieval." },
];
const stages = ["IAM and API-key boundary", "Route selection", "Private corpus retrieval", "Grounded generation", "Citation de-duplication", "Digit-expression numerical review"];
const limitations = ["Production query_logs insertion is absent", "Exact successful provider-attempt telemetry is unavailable", "Word-form numbers bypass the deployed digit-expression guard", "Scale-to-zero can produce cold starts", "Internet-reachable ingress remains protected by IAM"];

export const metadata = { title: "System trust" };
export default function SystemPage() { return <SiteShell section="system" eyebrow="Trust architecture" title="Private by construction" intro="A content-safe engineering view of the controls, execution stages, deployment health, and known limits of the validated system.">
  <div className="trust-banner"><ShieldCheck /><div><strong>Established cloud baseline</strong><span>Healthy active revision · IAM required · no public principals</span></div><span className="verified-pill"><span /> VERIFIED</span></div>
  <section className="control-grid" aria-label="Security controls">{controls.map(({ icon: Icon, title, body }) => <article key={title}><Icon size={22} /><h2>{title}</h2><p>{body}</p><span><CheckCircle2 size={13} /> Control evidenced</span></article>)}</section>
  <section className="architecture-strip" aria-label="Private deployment architecture"><div><Cloud size={20} /><strong>Cloud Run</strong><small>IAM-authenticated</small></div><i /><div><Network size={20} /><strong>Direct VPC</strong><small>private egress</small></div><i /><div><Database size={20} /><strong>Cloud SQL</strong><small>encrypted, protected</small></div></section>
  <div className="system-details"><section className="lifecycle-card"><div className="section-heading"><div><p className="mono-label">Request lifecycle</p><h2>Evidence before answer</h2></div><Route size={19} /></div>{stages.map((stage, index) => <div className="lifecycle-step" key={stage}><span>{String(index + 1).padStart(2, "0")}</span><strong>{stage}</strong><CheckCircle2 size={14} /></div>)}</section><section className="health-card"><p className="mono-label">Frozen deployment evidence</p><h2>Healthy, private, immutable</h2><dl><div><dt>Service</dt><dd>1 active</dd></div><div><dt>Ready revision</dt><dd>1 at 100%</dd></div><div><dt>Database</dt><dd>RUNNABLE</dd></div><div><dt>Corpus</dt><dd>8 / 239 / 3</dd></div><div><dt>Query logs</dt><dd>0</dd></div></dl><p>Historical authenticated checks: health 200, database health 200, readiness 200. No endpoint request is made by this page.</p></section></div>
  <section className="limitations-card"><p className="mono-label">Known limitations</p><h2>Visible engineering edges</h2><ul>{limitations.map((item) => <li key={item}>{item}</li>)}</ul></section>
  <div className="disclosure-note"><p className="mono-label">Deliberate disclosure boundary</p><p>Service URLs, project identifiers, private addresses, credentials, secret payloads, and connection identifiers are excluded from the interface.</p></div>
</SiteShell>; }

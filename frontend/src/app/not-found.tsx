import Link from "next/link";
export default function NotFound() { return <main className="route-state"><p className="mono-label">404 · route not found</p><h1>This intelligence path does not exist.</h1><Link className="button button-primary" href="/workspace">Return to workspace</Link></main>; }

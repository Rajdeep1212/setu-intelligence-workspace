"use client";
import { AlertTriangle } from "lucide-react";
export default function ErrorPage({ reset }: { error: Error & { digest?: string }; reset: () => void }) { return <main className="route-state"><AlertTriangle size={34} /><p className="mono-label">Local interface error</p><h1>This view could not be prepared.</h1><p>No cloud request was submitted. You can safely try the local render again.</p><button className="button button-secondary" type="button" onClick={reset}>Try again</button></main>; }

import { SiteShell } from "@/components/site-shell";
import { SourceExplorer } from "@/components/sources/source-explorer";
import { Providers } from "@/components/providers";
import { Suspense } from "react";

export const metadata = { title: "Sources" };
export default function SourcesPage() {
  return <SiteShell section="sources" eyebrow="Corpus explorer" title="Evidence before inference" intro="Inspect the sanitized evidence model used by the workspace demo. Source relationships stay visible from answer to stored chunk.">
    <Providers><Suspense fallback={<div className="catalog-state" role="status">Loading source explorer…</div>}><SourceExplorer /></Suspense></Providers>
  </SiteShell>;
}

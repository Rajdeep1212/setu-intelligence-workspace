import { SiteShell } from "@/components/site-shell";
import { SourceExplorer } from "@/components/sources/source-explorer";

export const metadata = { title: "Sources" };
export default function SourcesPage() {
  return <SiteShell section="sources" eyebrow="Corpus explorer" title="Evidence before inference" intro="Inspect the sanitized evidence model used by the workspace demo. Source relationships stay visible from answer to stored chunk.">
    <SourceExplorer />
  </SiteShell>;
}

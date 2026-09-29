import { SiteShell } from "@/components/site-shell";
import { RoadsideMode } from "@/components/roadside/roadside-mode";

export const metadata = { title: "Roadside Mode" };

export default function RoadsidePage() {
  return (
    <SiteShell
      section="roadside"
      eyebrow="Works offline"
      title="Roadside Mode"
      intro="Check a traffic offence, the official on-the-spot amount and where it comes from. Open this page once while online and it keeps working without a network."
    >
      <RoadsideMode />
    </SiteShell>
  );
}

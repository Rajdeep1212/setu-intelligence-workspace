// Display rules for Roadside Mode. Pure functions over the offline bundle, so
// every rule is unit-tested (roadside.test.ts) and nothing depends on the network.
//
// The rules that protect people at a checkpoint:
// - A number is shown only for a VERIFIED state compounding row.
// - Red-light jumping never shows an amount: how it is booked is under legal review.
// - A state amount below the Act's fixed fine is flagged and shown beside it, never merged.
// - Police fine lists are observations, labelled as not being notifications.
import bundleJson from "@/data/roadside-bundle.json";

export type Occurrence = "first" | "subsequent" | "any";
export type Amount = { occurrence: Occurrence; vehicle_class: string; inr: number };
export type Source = {
  title: string;
  issuer: string;
  kind: string;
  notification_reference: string;
  notification_date?: string;
  effective_from?: string;
  url: string;
  sha256: string;
  retrieved_at: string;
  provenance_note?: string;
};
export type Offence = {
  offence_id: string;
  label: string;
  central_law: {
    provision: string;
    penalty_text: string;
    fixed_fine_inr?: number;
    source_id: string;
    commencement_source_id?: string;
    effective_from: string;
    note?: string;
  };
  state_compounding: {
    status: "VERIFIED" | "UNVERIFIED";
    amounts: Amount[];
    source_id?: string;
    schedule_row?: string;
    effective_from?: string;
    effective_to?: string;
    additional_consequence?: string;
    note?: string;
    settle_with?: string;
  };
  observations: { source_id: string; row: string; summary: string }[];
};
export type OffenceTable = {
  schema_version: string;
  jurisdiction: string;
  jurisdiction_name: string;
  retrieved_at: string;
  notes?: string[];
  sources: Record<string, Source>;
  offences: Offence[];
};
export type RoadsideBundle = { schema: string; valid_as_of: string; sha256: string; tables: OffenceTable[] };

// The JSON import is typed structurally; the build script and tests guarantee its shape.
export const bundle = bundleJson as unknown as RoadsideBundle;
export const STALE_AFTER_DAYS = 90;
export const LEGAL_REVIEW_OFFENCES = new Set(["red_light"]);

const OCCURRENCE_LABELS: Record<Occurrence, string> = {
  first: "First offence",
  subsequent: "Repeat offence",
  any: "Any offence",
};
const VEHICLE_LABELS: Record<string, string> = {
  any: "All vehicles",
  two_three_wheeler: "Two- and three-wheelers",
  two_three_wheeler_and_lmv: "Two- and three-wheelers, light motor vehicles",
  light_motor_vehicle: "Light motor vehicles",
  medium_heavy: "Medium and heavy vehicles",
  heavy_and_others: "Heavy and other vehicles",
  others: "Other vehicles",
};

export function formatInr(value: number): string {
  return `₹${value.toLocaleString("en-IN")}`;
}

export type AmountLine = { occurrence: string; vehicle: string; inr: number; text: string; belowCentral: boolean };
export type SourceRef = { title: string; reference: string; url: string; date?: string };
export type StateView =
  | { kind: "verified"; amounts: AmountLine[]; source: SourceRef; scheduleRow: string; effectiveFrom: string; note?: string; consequence?: string; belowCentral: boolean }
  | { kind: "unverified"; message: string; settleWith?: string }
  | { kind: "legal_review"; message: string; settleWith?: string };
export type ObservationView = { label: string; row: string; summary: string; source: SourceRef };
export type OffenceView = {
  id: string;
  label: string;
  central: { provision: string; penaltyText: string; fixedFine?: number; note?: string; source: SourceRef; effectiveFrom: string };
  state: StateView;
  observations: ObservationView[];
};

function sourceRef(table: OffenceTable, sourceId: string | undefined): SourceRef {
  const source = sourceId ? table.sources[sourceId] : undefined;
  if (!source) throw new Error(`Unknown source ${sourceId} in ${table.jurisdiction}`);
  return { title: source.title, reference: source.notification_reference, url: source.url, date: source.notification_date };
}

/**
 * Notes in the data are written for maintainers too. Drop sentences that point
 * at repository files (for example "see docs/FINDINGS.md, claim C3") and
 * cross-references to other rows, so public text stays self-contained.
 */
export function publicNote(text: string | undefined): string | undefined {
  if (!text) return undefined;
  const withoutFileRefs = text
    // "…question; see docs/FINDINGS.md, claim C3." and "… 2017. See docs/FINDINGS.md, claim C2."
    .replace(/[;,]?\s*\bsee\s+docs\/[\w./-]+(?:,\s*claims?\s+C\d+(?:\s*(?:and|,)\s*C\d+)*)?\.?/gi, ".")
    .replace(/\.{2,}/g, ".")
    .replace(/\s+\./g, ".");
  const kept = withoutFileRefs
    .split(/(?<=\.)\s+/)
    .map((sentence) => sentence.trim())
    .filter((sentence) => sentence && sentence !== "." && !/docs\/|\bsame open legal question as\b/i.test(sentence));
  const result = kept.join(" ").trim();
  if (!result) return undefined;
  return /[.!?]$/.test(result) ? result : `${result.replace(/[;,]$/, "")}.`;
}

export function observationLabel(kind: string): string {
  if (kind === "police_schedule") return "Police fine list (not a notification)";
  if (kind === "superseded_notification") return "Superseded notification (not current)";
  return "Other official material (not a compounding notification)";
}

export function describeOffence(table: OffenceTable, offenceId: string): OffenceView {
  const offence = table.offences.find((item) => item.offence_id === offenceId);
  if (!offence) throw new Error(`Unknown offence ${offenceId} in ${table.jurisdiction}`);
  const law = offence.central_law;
  const state = offence.state_compounding;
  const fixedFine = law.fixed_fine_inr;

  let stateView: StateView;
  if (LEGAL_REVIEW_OFFENCES.has(offence.offence_id)) {
    stateView = {
      kind: "legal_review",
      message:
        "No amount is shown. It depends on how the offence is booked: as a signal violation or as dangerous driving. This is under legal review.",
      settleWith: state.settle_with,
    };
  } else if (state.status !== "VERIFIED" || state.amounts.length === 0) {
    stateView = { kind: "unverified", message: "No verified amount yet", settleWith: state.settle_with };
  } else {
    const amounts = state.amounts.map((amount) => ({
      occurrence: OCCURRENCE_LABELS[amount.occurrence],
      vehicle: VEHICLE_LABELS[amount.vehicle_class] ?? amount.vehicle_class,
      inr: amount.inr,
      text: formatInr(amount.inr),
      belowCentral: fixedFine !== undefined && amount.inr < fixedFine,
    }));
    stateView = {
      kind: "verified",
      amounts,
      source: sourceRef(table, state.source_id),
      scheduleRow: state.schedule_row ?? "",
      effectiveFrom: state.effective_from ?? "",
      // When an amount is below the central fine, the page shows its own callout
      // for that question, so the maintainer note would only repeat it.
      note: amounts.some((amount) => amount.belowCentral) ? undefined : publicNote(state.note),
      consequence: state.additional_consequence,
      belowCentral: amounts.some((amount) => amount.belowCentral),
    };
  }

  return {
    id: offence.offence_id,
    label: offence.label,
    central: {
      provision: law.provision,
      penaltyText: law.penalty_text,
      fixedFine,
      note: publicNote(law.note),
      source: sourceRef(table, law.source_id),
      effectiveFrom: law.effective_from,
    },
    state: stateView,
    observations: offence.observations.map((observation) => ({
      label: observationLabel(table.sources[observation.source_id]?.kind ?? ""),
      row: observation.row,
      summary: observation.summary,
      source: sourceRef(table, observation.source_id),
    })),
  };
}

export function bundleAgeDays(validAsOf: string, now: Date): number {
  const start = Date.parse(`${validAsOf}T00:00:00Z`);
  const today = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());
  return Math.max(0, Math.floor((today - start) / 86_400_000));
}

export function isStale(validAsOf: string, now: Date): boolean {
  return bundleAgeDays(validAsOf, now) > STALE_AFTER_DAYS;
}

export function formatDate(iso: string): string {
  const [year, month, day] = iso.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day)).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

export function tableFor(jurisdiction: string, source: RoadsideBundle = bundle): OffenceTable {
  const table = source.tables.find((item) => item.jurisdiction === jurisdiction);
  if (!table) throw new Error(`No table for ${jurisdiction}`);
  return table;
}

import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { BUNDLE_PATH, buildBundle, serialize } from "../../scripts/roadside-bundle.mjs";
import {
  bundle,
  bundleAgeDays,
  describeOffence,
  formatInr,
  isStale,
  observationLabel,
  publicNote,
  tableFor,
  type OffenceTable,
} from "./roadside";

describe("offline bundle", () => {
  it("matches what the build script produces from data/traffic_offences", () => {
    expect(readFileSync(BUNDLE_PATH, "utf8")).toBe(serialize(buildBundle()));
  });

  it("covers West Bengal, Karnataka and Delhi with a valid-as-of date and hash", () => {
    expect(bundle.tables.map((table) => table.jurisdiction)).toEqual(["IN-DL", "IN-KA", "IN-WB"]);
    expect(bundle.valid_as_of).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(bundle.sha256).toMatch(/^[0-9a-f]{64}$/);
  });
});

describe("verified amounts", () => {
  it("shows the West Bengal handheld-device amounts with their notification", () => {
    const view = describeOffence(tableFor("IN-WB"), "phone_device");
    expect(view.state.kind).toBe("verified");
    if (view.state.kind !== "verified") return;
    expect(view.state.amounts.map((line) => [line.occurrence, line.text])).toEqual([
      ["First offence", "₹5,000"],
      ["Repeat offence", "₹10,000"],
    ]);
    expect(view.state.source.reference).toContain("208-WT");
    expect(view.state.source.url).toMatch(/^https:\/\/transport\.wb\.gov\.in\//);
    expect(view.state.scheduleRow).toBe("Schedule II Sl. No. 11");
    expect(view.state.belowCentral).toBe(false);
  });
});

describe("unverified rows", () => {
  it("never show a number for Delhi", () => {
    for (const offence of tableFor("IN-DL").offences) {
      const view = describeOffence(tableFor("IN-DL"), offence.offence_id);
      expect(view.state.kind).not.toBe("verified");
      expect(JSON.stringify(view.state)).not.toMatch(/₹/);
    }
    expect(describeOffence(tableFor("IN-DL"), "helmet").state).toMatchObject({
      kind: "unverified",
      message: "No verified amount yet",
    });
  });

  it("stay without a number even if a row were marked verified with no amounts", () => {
    const table: OffenceTable = structuredClone(tableFor("IN-DL"));
    table.offences[0].state_compounding.status = "VERIFIED";
    expect(describeOffence(table, table.offences[0].offence_id).state.kind).toBe("unverified");
  });
});

describe("amounts below the central fine", () => {
  it("flags Karnataka's helmet amount and keeps the central fine beside it", () => {
    const view = describeOffence(tableFor("IN-KA"), "helmet");
    expect(view.central.fixedFine).toBe(1000);
    expect(view.state.kind).toBe("verified");
    if (view.state.kind !== "verified") return;
    expect(view.state.belowCentral).toBe(true);
    expect(view.state.amounts).toEqual([expect.objectContaining({ inr: 500, belowCentral: true })]);
  });

  it("flags only the vehicle classes that are below the fine", () => {
    const view = describeOffence(tableFor("IN-KA"), "no_licence");
    if (view.state.kind !== "verified") throw new Error("expected verified");
    expect(view.state.amounts.map((line) => [line.inr, line.belowCentral])).toEqual([
      [1000, true],
      [2000, true],
      [5000, false],
    ]);
  });

  it("does not flag ranges, where the Act names no single fine", () => {
    const view = describeOffence(tableFor("IN-KA"), "phone_device");
    expect(view.central.fixedFine).toBeUndefined();
    if (view.state.kind !== "verified") throw new Error("expected verified");
    expect(view.state.belowCentral).toBe(false);
  });
});

describe("red-light jumping", () => {
  it("shows no amount in any state and explains the legal review", () => {
    for (const table of bundle.tables) {
      const view = describeOffence(table, "red_light");
      expect(view.state.kind).toBe("legal_review");
      expect(JSON.stringify(view.state)).not.toMatch(/₹/);
      if (view.state.kind === "legal_review") {
        expect(view.state.message).toMatch(/signal violation/);
        expect(view.state.message).toMatch(/dangerous driving/);
      }
    }
  });

  it("stays under review even if a verified amount were added", () => {
    const table: OffenceTable = structuredClone(tableFor("IN-WB"));
    const row = table.offences.find((offence) => offence.offence_id === "red_light")!;
    row.state_compounding.status = "VERIFIED";
    row.state_compounding.amounts = [{ occurrence: "first", vehicle_class: "any", inr: 500 }];
    expect(describeOffence(table, "red_light").state.kind).toBe("legal_review");
  });
});

describe("police fine lists", () => {
  it("are labelled as observations, not notifications", () => {
    const view = describeOffence(tableFor("IN-WB"), "red_light");
    expect(view.observations.length).toBeGreaterThan(0);
    for (const observation of view.observations) {
      expect(observation.label).toBe("Police fine list (not a notification)");
    }
    expect(observationLabel("state_s200_notification")).toMatch(/not a compounding notification/);
  });
});

describe("data age", () => {
  it("counts whole days and warns after 90", () => {
    expect(bundleAgeDays("2026-09-27", new Date("2026-09-28T10:00:00Z"))).toBe(1);
    expect(isStale("2026-09-27", new Date("2026-12-26T00:00:00Z"))).toBe(false);
    expect(isStale("2026-09-27", new Date("2026-12-27T00:00:00Z"))).toBe(true);
  });

  it("formats rupees in the Indian style", () => {
    expect(formatInr(100000)).toBe("₹1,00,000");
  });
});

describe("public notes", () => {
  it("remove repository file references without leaving fragments", () => {
    expect(
      publicNote("Earphones or headphones for music are not named in s.184 or the Motor Vehicles (Driving) Regulations 2017. See docs/FINDINGS.md, claim C2."),
    ).toBe("Earphones or headphones for music are not named in s.184 or the Motor Vehicles (Driving) Regulations 2017.");
    expect(
      publicNote("Whether a state may compound below the statutory fine is an open legal question; see docs/FINDINGS.md, claim C3."),
    ).toBe("Whether a state may compound below the statutory fine is an open legal question.");
  });

  it("drop cross-references to other rows", () => {
    expect(
      publicNote("The central Act sets a fine of Rs 5,000; the notification sets lower amounts for two/three-wheelers and LMVs. Same open legal question as the helmet row."),
    ).toBe("The central Act sets a fine of Rs 5,000; the notification sets lower amounts for two/three-wheelers and LMVs.");
  });

  it("keep ordinary notes unchanged and never leak a file path anywhere in the bundle", () => {
    expect(publicNote("Medium/heavy means MGV, MPV, HGV and HPV as written in the notification.")).toBe(
      "Medium/heavy means MGV, MPV, HGV and HPV as written in the notification.",
    );
    for (const table of bundle.tables) {
      for (const offence of table.offences) {
        const view = describeOffence(table, offence.offence_id);
        const visible = JSON.stringify([view.central.note, view.state.kind === "verified" ? view.state.note : view.state.settleWith]);
        expect(visible).not.toMatch(/docs\/|FINDINGS|\bmd,/);
      }
    }
  });
});

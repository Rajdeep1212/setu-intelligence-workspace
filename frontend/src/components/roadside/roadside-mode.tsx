"use client";

import { useEffect, useMemo, useState, useSyncExternalStore } from "react";
import { CircleCheck, ExternalLink, FileCheck2, Info, Scale, ShieldAlert, TriangleAlert, WifiOff } from "lucide-react";
import {
  bundle,
  bundleAgeDays,
  describeOffence,
  formatDate,
  formatInr,
  isStale,
  STALE_AFTER_DAYS,
  tableFor,
  type SourceRef,
} from "@/lib/roadside";

const STATES = [
  { code: "IN-WB", name: "West Bengal" },
  { code: "IN-KA", name: "Karnataka" },
  { code: "IN-DL", name: "Delhi" },
] as const;
const OFFENCE_ORDER = ["phone_device", "helmet", "triple_riding", "no_licence", "no_insurance", "overspeeding", "red_light"];
const DOCUMENT_SOURCES: SourceRef[] = [
  { title: "PIB, 9 Aug 2018: documents in DigiLocker or mParivahan accepted as valid", reference: "MoRTH advisory", url: "https://pib.gov.in/newsite/PrintRelease.aspx?relid=181696" },
  { title: "PIB: G.S.R. 584(E), in force 1 Oct 2020", reference: "Central Motor Vehicles Rules amendment", url: "https://www.pib.gov.in/PressReleasePage.aspx?PRID=1659408" },
];
const SERVICE_WORKER_URL = "/roadside-sw.js";

type OfflineStatus = "checking" | "ready" | "unsupported" | "failed";

const subscribeNever = () => () => {};

/** Today's date on the client; null during server rendering, so hydration matches. */
function useToday(): Date | null {
  const today = useSyncExternalStore(
    subscribeNever,
    () => new Date().toISOString().slice(0, 10),
    () => null,
  );
  return today ? new Date(`${today}T12:00:00Z`) : null;
}

function SourceLink({ source, label = "Official source" }: { source: SourceRef; label?: string }) {
  return (
    <a className="roadside-source-link" href={source.url} target="_blank" rel="noreferrer">
      {label}
      <ExternalLink size={12} aria-hidden="true" />
      <span className="sr-only">: {source.title} (opens in a new tab)</span>
    </a>
  );
}

function useOfflineCopy(): OfflineStatus {
  const supported = useSyncExternalStore(
    subscribeNever,
    () => "serviceWorker" in navigator,
    () => true,
  );
  const [status, setStatus] = useState<OfflineStatus>("checking");
  useEffect(() => {
    if (!supported) return;
    let cancelled = false;
    navigator.serviceWorker
      .register(SERVICE_WORKER_URL, { scope: "/roadside" })
      .then((registration) => {
        const worker = registration.active ?? registration.waiting ?? registration.installing;
        if (registration.active) return;
        return new Promise<void>((resolve) => {
          worker?.addEventListener("statechange", () => {
            if (worker.state === "activated") resolve();
          });
        });
      })
      .then(() => {
        if (!cancelled) setStatus("ready");
      })
      .catch(() => {
        if (!cancelled) setStatus("failed");
      });
    return () => {
      cancelled = true;
    };
  }, [supported]);
  return supported ? status : "unsupported";
}

const OFFLINE_TEXT: Record<OfflineStatus, string> = {
  checking: "Saving this page for offline use…",
  ready: "Saved for offline use on this device",
  unsupported: "This browser cannot save the page for offline use",
  failed: "Could not save the page for offline use. It still works while you are online.",
};

export function RoadsideMode() {
  const [jurisdiction, setJurisdiction] = useState<string>("IN-WB");
  const [offenceId, setOffenceId] = useState<string>("phone_device");
  const now = useToday();
  const offline = useOfflineCopy();

  const table = tableFor(jurisdiction);
  const stateName = STATES.find((state) => state.code === jurisdiction)?.name ?? table.jurisdiction_name;
  const offences = useMemo(
    () => OFFENCE_ORDER.map((id) => table.offences.find((offence) => offence.offence_id === id)).filter((offence) => offence !== undefined),
    [table],
  );
  const view = describeOffence(table, offenceId);
  const stale = now ? isStale(bundle.valid_as_of, now) : false;
  const ageDays = now ? bundleAgeDays(bundle.valid_as_of, now) : null;

  return (
    <div className="roadside">
      <section className="roadside-freshness" aria-label="About this data">
        <div>
          <p className="mono-label">Data checked</p>
          <strong>Valid as of {formatDate(bundle.valid_as_of)}</strong>
          <span>
            Bundle <code>{bundle.sha256.slice(0, 12)}</code>
            {ageDays !== null ? ` · ${ageDays} day${ageDays === 1 ? "" : "s"} old` : ""}
          </span>
        </div>
        <p className={`roadside-offline roadside-offline-${offline}`} role="status">
          {offline === "ready" ? <CircleCheck size={15} aria-hidden="true" /> : <WifiOff size={15} aria-hidden="true" />}
          {OFFLINE_TEXT[offline]}
        </p>
      </section>
      {stale ? (
        <p className="roadside-callout roadside-callout-warn" role="alert">
          <TriangleAlert size={16} aria-hidden="true" />
          This data is more than {STALE_AFTER_DAYS} days old. Amounts may have changed. Check the official source when you can.
        </p>
      ) : null}

      <form className="roadside-pickers" onSubmit={(event) => event.preventDefault()}>
        <label htmlFor="roadside-state">
          State
          <select id="roadside-state" value={jurisdiction} onChange={(event) => setJurisdiction(event.target.value)}>
            {STATES.map((state) => (
              <option key={state.code} value={state.code}>
                {state.name}
              </option>
            ))}
          </select>
        </label>
        <label htmlFor="roadside-offence">
          Offence
          <select id="roadside-offence" value={offenceId} onChange={(event) => setOffenceId(event.target.value)}>
            {offences.map((offence) => (
              <option key={offence.offence_id} value={offence.offence_id}>
                {offence.label}
              </option>
            ))}
          </select>
        </label>
      </form>

      <article className="roadside-card" aria-labelledby="roadside-offence-title">
        <header>
          <p className="mono-label">{stateName}</p>
          <h2 id="roadside-offence-title">{view.label}</h2>
        </header>

        <section className="roadside-block" aria-labelledby="roadside-state-amount">
          <h3 id="roadside-state-amount">On-the-spot amount in {stateName}</h3>
          {view.state.kind === "verified" ? (
            <>
              <div className="roadside-table-wrap">
                <table className="roadside-amounts">
                  <thead>
                    <tr>
                      <th scope="col">When</th>
                      <th scope="col">Vehicles</th>
                      <th scope="col">Amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {view.state.amounts.map((line) => (
                      <tr key={`${line.occurrence}-${line.vehicle}`}>
                        <td>{line.occurrence}</td>
                        <td>{line.vehicle}</td>
                        <td className="roadside-inr">
                          {line.text}
                          {line.belowCentral ? <span className="roadside-flag">Below central fine</span> : null}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {view.state.consequence ? <p className="roadside-note">Also: {view.state.consequence}.</p> : null}
              <p className="roadside-provenance">
                <FileCheck2 size={14} aria-hidden="true" />
                <span>
                  {view.state.source.reference} · {view.state.scheduleRow} · in force from {formatDate(view.state.effectiveFrom)}
                  <SourceLink source={view.state.source} />
                </span>
              </p>
              {view.state.belowCentral && view.central.fixedFine ? (
                <p className="roadside-callout roadside-callout-info">
                  <Scale size={16} aria-hidden="true" />
                  <span>
                    The central Act names a fine of {formatInr(view.central.fixedFine)}. This state&apos;s on-the-spot amount is
                    lower. Both are shown as published. Whether a state may set a lower amount is an open legal question.
                  </span>
                </p>
              ) : null}
              {view.state.note ? <p className="roadside-note">{view.state.note}</p> : null}
            </>
          ) : (
            <div className={`roadside-empty roadside-empty-${view.state.kind}`}>
              {view.state.kind === "legal_review" ? <ShieldAlert size={18} aria-hidden="true" /> : <Info size={18} aria-hidden="true" />}
              <div>
                <strong>{view.state.kind === "legal_review" ? "Under legal review" : view.state.message}</strong>
                {view.state.kind === "legal_review" ? <p>{view.state.message}</p> : null}
                {view.state.settleWith ? <p className="roadside-note">What would settle it: {view.state.settleWith}</p> : null}
              </div>
            </div>
          )}
        </section>

        <section className="roadside-block" aria-labelledby="roadside-central">
          <h3 id="roadside-central">Central law</h3>
          <p className="roadside-law">{view.central.penaltyText}</p>
          <p className="roadside-provenance">
            <span>
              {view.central.provision} · in force from {formatDate(view.central.effectiveFrom)}
              <SourceLink source={view.central.source} label="The Act" />
            </span>
          </p>
          {view.central.note ? <p className="roadside-note">{view.central.note}</p> : null}
        </section>

        {view.observations.length > 0 ? (
          <section className="roadside-block" aria-labelledby="roadside-observations">
            <h3 id="roadside-observations">Other official lists</h3>
            <ul className="roadside-observations">
              {view.observations.map((observation) => (
                <li key={`${observation.label}-${observation.row}`}>
                  <span className="roadside-chip">{observation.label}</span>
                  <p>
                    Row {observation.row}: {observation.summary}
                  </p>
                  <SourceLink source={observation.source} label="View list" />
                </li>
              ))}
            </ul>
          </section>
        ) : null}
      </article>

      <section className="roadside-checkpoint" aria-labelledby="roadside-checkpoint-title">
        <h2 id="roadside-checkpoint-title">At a checkpoint</h2>
        <ul>
          <li>Stay calm and polite. You can ask which offence and section the challan is for.</li>
          <li>Pay only through an e-challan or an official receipt that shows the amount.</li>
          <li>If you disagree with a challan, you can contest it later through official channels, such as the e-challan portal or the court named on it.</li>
          <li>
            Documents inside the DigiLocker or mParivahan apps are valid in place of paper copies. A photo or PDF on your phone does not
            count.
            <span className="roadside-inline-sources">
              {DOCUMENT_SOURCES.map((source) => (
                <SourceLink key={source.url} source={source} label={source.reference} />
              ))}
            </span>
          </li>
        </ul>
        <p className="roadside-disclaimer">Not legal advice. Amounts come from the official notifications linked above.</p>
      </section>
    </div>
  );
}

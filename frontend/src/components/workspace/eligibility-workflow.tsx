"use client";

import { useMemo, useState } from "react";
import { ArrowLeft, ArrowRight, CircleAlert, RotateCcw, ShieldCheck } from "lucide-react";

type SchemeId = "scholarship" | "kisan" | "jandhan";
type Profile = { income: string; category: string; landholding: string; excluded: string; age: string; documents: string };

const schemes = {
  scholarship: { name: "Post-Matric Scholarship", description: "Illustrative family-income and category inputs", fields: ["income", "category"] as const },
  kisan: { name: "PM Kisan Samman Nidhi", description: "Illustrative landholding and exclusion inputs", fields: ["landholding", "excluded"] as const },
  jandhan: { name: "Pradhan Mantri Jan Dhan Yojana", description: "Illustrative age and document-readiness inputs", fields: ["age", "documents"] as const },
};

const fieldLabels: Record<keyof Profile, string> = {
  income: "Annual family income",
  category: "Applicant category",
  landholding: "Landholding-family response",
  excluded: "Exclusion-category response",
  age: "Applicant age",
  documents: "Document-readiness response",
};

const emptyProfile: Profile = { income: "", category: "", landholding: "", excluded: "", age: "", documents: "" };

export function EligibilityWorkflow() {
  const [step, setStep] = useState<"scheme" | "profile" | "review" | "preview">("scheme");
  const [schemeId, setSchemeId] = useState<SchemeId>("scholarship");
  const [profile, setProfile] = useState<Profile>(emptyProfile);
  const scheme = schemes[schemeId];
  const preview = useMemo(() => scheme.fields.map((field) => ({ field, label: fieldLabels[field], value: profile[field], supplied: Boolean(profile[field]) })), [profile, scheme.fields]);
  const missingCount = preview.filter((item) => !item.supplied).length;
  const update = (key: keyof Profile, value: string) => setProfile((current) => ({ ...current, [key]: value }));
  const reset = () => { setProfile(emptyProfile); setStep("scheme"); };

  return <section className="eligibility-flow" aria-labelledby="eligibility-heading">
    <div className="eligibility-notice" role="note"><ShieldCheck size={18} /><p><strong>Illustrative eligibility experience</strong><span>The criteria are demonstration data. This preview never decides whether you are eligible and must not replace verification against the applicable official source.</span></p></div>
    <ol className="eligibility-steps" aria-label="Eligibility preview progress">{["Scheme", "Profile", "Review", "Preview"].map((label, index) => <li key={label} aria-current={["scheme", "profile", "review", "preview"].indexOf(step) === index ? "step" : undefined}><span>{index + 1}</span>{label}</li>)}</ol>

    {step === "scheme" && <div className="eligibility-card"><p className="mono-label">Step 01 · demonstration programme</p><h3 id="eligibility-heading">Choose an illustrative criteria set</h3><p className="form-intro">These choices demonstrate product interaction only. Their rules have not yet been reviewed, versioned, or linked to official-source provenance.</p><div className="scheme-grid">{(Object.entries(schemes) as [SchemeId, typeof scheme][]).map(([id, item]) => <button type="button" key={id} className={schemeId === id ? "is-selected" : ""} aria-pressed={schemeId === id} onClick={() => setSchemeId(id)}><strong>{item.name}</strong><span>{item.description}</span></button>)}</div><div className="flow-actions"><button type="button" className="button button-primary" onClick={() => setStep("profile")}>Continue <ArrowRight size={15} /></button></div></div>}

    {step === "profile" && <div className="eligibility-card"><p className="mono-label">Step 02 · session-only example</p><h3>{scheme.name}</h3><p className="form-intro">Only non-identifying demonstration inputs are requested. They stay in component memory and are not sent to a backend or provider.</p><div className="profile-grid">
      {schemeId === "scholarship" && <><label>Demonstration annual family income (₹)<span>No threshold or decision is applied.</span><input inputMode="numeric" min="0" type="number" value={profile.income} onChange={(event) => update("income", event.target.value)} /></label><label>Demonstration applicant category<span>No official category rule is applied.</span><select value={profile.category} onChange={(event) => update("category", event.target.value)}><option value="">Not supplied</option><option>SC</option><option>ST</option><option>OBC</option><option>Minority</option><option>Other / verify officially</option></select></label></>}
      {schemeId === "kisan" && <><label>Landholding farmer family?<span>Demonstrates a binary criteria input only.</span><select value={profile.landholding} onChange={(event) => update("landholding", event.target.value)}><option value="">Not supplied</option><option value="yes">Yes</option><option value="no">No</option></select></label><label>Possible exclusion category?<span>No authoritative exclusion list is applied.</span><select value={profile.excluded} onChange={(event) => update("excluded", event.target.value)}><option value="">Not supplied</option><option value="no">No / unknown</option><option value="yes">Yes / possible</option></select></label></>}
      {schemeId === "jandhan" && <><label>Demonstration applicant age<span>No official age criterion is applied.</span><input inputMode="numeric" min="0" max="120" type="number" value={profile.age} onChange={(event) => update("age", event.target.value)} /></label><label>Document types available?<span>No document identifiers or uploads are collected.</span><select value={profile.documents} onChange={(event) => update("documents", event.target.value)}><option value="">Not supplied</option><option value="yes">Yes</option><option value="no">No / unsure</option></select></label></>}
    </div><div className="flow-actions"><button type="button" className="button button-secondary" onClick={() => setStep("scheme")}><ArrowLeft size={15} /> Back</button><button type="button" className="button button-primary" onClick={() => setStep("review")}>Review inputs <ArrowRight size={15} /></button></div></div>}

    {step === "review" && <div className="eligibility-card"><p className="mono-label">Step 03 · review</p><h3>Review the demonstration inputs</h3><dl className="review-list"><div><dt>Programme preview</dt><dd>{scheme.name}</dd></div>{preview.map((item) => <div key={item.field}><dt>{item.label}</dt><dd>{item.value || "Not supplied"}</dd></div>)}</dl><p className="privacy-copy">Inputs remain only in this component’s memory. Live eligibility submission is intentionally unavailable until reviewed, versioned rules and official-source provenance exist.</p><div className="flow-actions"><button type="button" className="button button-secondary" onClick={() => setStep("profile")}><ArrowLeft size={15} /> Edit</button><button type="button" className="button button-primary" onClick={() => setStep("preview")}>Show safe preview</button></div></div>}

    {step === "preview" && <div className="eligibility-card eligibility-result"><p className="mono-label">Step 04 · non-decision preview</p><div className="result-title"><CircleAlert /><div><h3>No eligibility determination is made</h3><p>{missingCount ? `${missingCount} demonstration input${missingCount === 1 ? " is" : "s are"} missing.` : "All demonstration inputs were supplied."} Completeness is not eligibility.</p></div></div><div className="criteria-results">{preview.map((item) => <article key={item.field}><span className={`criterion-state ${item.supplied ? "state-pass" : "state-missing"}`}>{item.supplied ? "supplied" : "not supplied"}</span><h4>{item.label}</h4><p>{item.supplied ? "Recorded only for this local interaction preview." : "The preview demonstrates missing-information handling without inferring a result."}</p></article>)}</div><div className="result-evidence"><strong>Production provenance requirement</strong><span>Each future rule must be reviewed, versioned, effective-dated, and linked to an applicable official source before SETU can evaluate it.</span><span>Verify current eligibility directly with the applicable official programme source.</span></div><div className="flow-actions"><button type="button" className="button button-secondary" onClick={() => setStep("profile")}><ArrowLeft size={15} /> Edit inputs</button><button type="button" className="button button-primary" onClick={reset}><RotateCcw size={15} /> Start over</button></div></div>}
  </section>;
}

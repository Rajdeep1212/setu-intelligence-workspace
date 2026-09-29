import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Providers } from "@/components/providers";
import { WorkspaceDemo } from "@/components/workspace/workspace-demo";
import { queryRequestSchema } from "@/lib/contracts";
import { demoResponse, demoResponseForQuery } from "@/lib/fixtures";

describe("WorkspaceDemo", () => {
  afterEach(() => vi.restoreAllMocks());
  it("links claim citations to retrieved evidence and opens the keyboard command menu", async () => { const user = userEvent.setup(); render(<Providers><WorkspaceDemo /></Providers>); expect(screen.getByText("2/2 sections evidence linked")).toBeInTheDocument(); await user.click(screen.getByLabelText("Focus retrieved citation 2 for claim 2")); expect(screen.getAllByRole("button", { pressed: true }).some((button) => button.textContent?.includes("E02"))).toBe(true); expect(screen.getByText("1", { selector: "dd" })).toBeInTheDocument(); await user.keyboard("{Control>}k{/Control}"); expect(screen.getByRole("dialog", { name: "Navigate SETU" })).toBeInTheDocument(); });
  it("exposes multilingual prompts and renders Hindi and Bengali demo fixtures", () => { render(<Providers><WorkspaceDemo /></Providers>); expect(screen.getByText("Ask in English, हिन्दी, or বাংলা")).toBeInTheDocument(); expect(demoResponseForQuery({ query: "भारत में आधार का क्या उपयोग है?" }).sections[0].text).toMatch(/[\u0900-\u097f]/); expect(demoResponseForQuery({ query: "ভারতে আধারের ব্যবহার কী?" }).sections[0].text).toMatch(/[\u0980-\u09ff]/); });
  it("submits a Hindi query without forcing an English language filter", async () => { const expectedHindiQuery = "भारत में आधार का क्या उपयोग है?"; const network = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(demoResponse), { status: 200 })); const user = userEvent.setup(); render(<Providers><WorkspaceDemo /></Providers>); const query = screen.getByLabelText("Ask SETU a question"); const submit = screen.getByRole("button", { name: "Run corpus investigation" }); fireEvent.change(query, { target: { value: expectedHindiQuery } }); expect(query).toHaveValue(expectedHindiQuery); expect(submit).toBeEnabled(); expect(queryRequestSchema.safeParse({ query: expectedHindiQuery }).success).toBe(true); await user.click(submit); await waitFor(() => expect(network).toHaveBeenCalledTimes(1)); const requestInit = network.mock.calls[0]?.[1]; expect(requestInit).toBeDefined(); const payload = JSON.parse(String(requestInit?.body)); expect(payload).toEqual({ query: expectedHindiQuery }); expect(payload).not.toHaveProperty("language"); });
  it("quarantines eligibility and never submits profile data", async () => { const network = vi.spyOn(globalThis, "fetch"); const user = userEvent.setup(); render(<Providers><WorkspaceDemo /></Providers>); await user.click(screen.getByRole("button", { name: /Eligibility mode/ })); expect(screen.getByText("Illustrative eligibility experience")).toBeInTheDocument(); expect(screen.getByRole("heading", { name: "Choose an illustrative criteria set" })).toBeInTheDocument(); await user.click(screen.getByRole("button", { name: /Continue/ })); expect(screen.getByLabelText(/Demonstration annual family income/)).toBeInTheDocument(); await user.click(screen.getByRole("button", { name: /Review inputs/ })); await user.click(screen.getByRole("button", { name: "Show safe preview" })); expect(screen.getByRole("heading", { name: "No eligibility determination is made" })).toBeInTheDocument(); expect(screen.queryByText(/appears to meet|not eligible|eligible result/i)).not.toBeInTheDocument(); expect(network).not.toHaveBeenCalled(); });
  it("shows a traffic-rule answer with its official source instead of an abstention", async () => {
    const ruleAnswer = {
      answer: "The official on-the-spot amount in West Bengal for riding without a helmet is ₹1,000. ₹5,000 does not match this amount.",
      citations: [],
      sections: [
        { text: "The official on-the-spot amount in West Bengal for riding without a helmet is ₹1,000.", citation_ids: [] },
        { text: "₹5,000 does not match this amount.", citation_ids: [] },
      ],
      route: "traffic_rules",
      response_status: "rule_lookup",
      premise_check: {
        verdict: "contradicted", offence_id: "helmet", jurisdiction: "IN-WB", claimed_inr: 5000,
        verified_amounts: [{ occurrence: "first", vehicle_class: "any", inr: 1000 }],
        source: { title: "Compounding of offences", reference: "No. 208-WT/3M-128/97 (Pt.III)(D) dated 24 Jan 2022", url: "https://transport.wb.gov.in/wp-content/uploads/2022/02/208-WT-DATE-24-01-2022.pdf" },
        schedule_row: "Schedule II Sl. No. 22", missing: [],
      },
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(ruleAnswer), { status: 200 }));
    const user = userEvent.setup();
    render(<Providers><WorkspaceDemo /></Providers>);
    await user.click(screen.getByRole("button", { name: "Run corpus investigation" }));
    const card = await screen.findByRole("article", { name: "Answer from verified offence tables" });
    expect(card).toHaveTextContent("₹5,000 does not match this amount.");
    expect(screen.getByRole("link", { name: "Official notification" })).toHaveAttribute("href", expect.stringMatching(/^https:\/\/transport\.wb\.gov\.in\//));
    expect(screen.getByText("From verified offence tables")).toBeInTheDocument();
    expect(screen.queryByText("Insufficient retrieved evidence")).not.toBeInTheDocument();
  });
  it("shows a message check with cited warnings and never makes the pasted link clickable", async () => {
    const scamAnswer = {
      answer: "This message shows strong signs of a scam. The link uses a shortened address. Check challans only on https://echallan.parivahan.gov.in/.",
      citations: [],
      sections: [
        { text: "This message shows strong signs of a scam.", citation_ids: [] },
        { text: "The link uses a shortened address.", citation_ids: [] },
        { text: "Check challans only on https://echallan.parivahan.gov.in/.", citation_ids: [] },
      ],
      route: "scam_check",
      response_status: "scam_check",
      scam_check: {
        verdict: "likely_scam",
        signals: ["shortened_link", "payment_link_not_official"],
        links: [{ url: "bit.ly/3xYzAb", host: "bit.ly", official: false, kinds: ["shortened_link"] }],
        debunks: [{ id: "fake-echallan-links-2026", kind: "channel_warning", topic: "Fake traffic e-challan messages", summary: "Scammers send fake challan links.", date: "2026-07-10", issuer: "PIB Fact Check", source: "https://www.business-standard.com/india-news/fake-traffic-challan-scam-pib-warning-whatsapp-sms-links-126071000400_1.html" }],
      },
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(scamAnswer), { status: 200 }));
    const user = userEvent.setup();
    render(<Providers><WorkspaceDemo /></Providers>);
    await user.click(screen.getByRole("button", { name: "Run corpus investigation" }));
    const card = await screen.findByRole("article", { name: "Message check" });
    expect(card).toHaveAttribute("data-verdict", "likely_scam");
    expect(screen.getByText("Likely scam")).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Links in the message" })).toHaveTextContent("bit.ly");
    expect(screen.getByRole("list", { name: "Links in the message" })).toHaveTextContent("Not a government domain");
    const links = within(card).getAllByRole("link");
    expect(links).toHaveLength(1);
    expect(links[0]).toHaveTextContent("Read the warning");
    expect(links.some((link) => link.getAttribute("href")?.includes("bit.ly"))).toBe(false);
    expect(screen.queryByText("Insufficient retrieved evidence")).not.toBeInTheDocument();
  });
  it("shows the eligibility notice as a notice, with official next steps", async () => {
    const notice = "Live eligibility evaluation is intentionally unavailable. Verify eligibility with the applicable official source.";
    const eligibilityAnswer = {
      answer: notice,
      citations: [],
      sections: [{ text: notice, citation_ids: [] }],
      route: "check_eligibility",
      response_status: "eligibility_unverified",
      next_steps: [
        { id: "pmkisan_status", label: "Check PM-KISAN registration and payment status on the official portal", url: "https://pmkisan.gov.in/BeneficiaryStatus_New.aspx", operator: "Department of Agriculture & Farmers Welfare" },
        { id: "myscheme", label: "Find government schemes you may qualify for on myScheme", url: "https://www.myscheme.gov.in/", operator: "Digital India Corporation (MeitY)" },
      ],
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(eligibilityAnswer), { status: 200 }));
    const user = userEvent.setup();
    render(<Providers><WorkspaceDemo /></Providers>);
    await user.click(screen.getByRole("button", { name: "Run corpus investigation" }));
    expect(await screen.findByRole("article", { name: "Eligibility not assessed" })).toHaveTextContent(notice);
    expect(screen.getByText("Eligibility not assessed", { selector: ".grounded-pill" })).toBeInTheDocument();
    expect(screen.queryByText("Insufficient retrieved evidence")).not.toBeInTheDocument();
    const steps = screen.getByRole("navigation", { name: "Official next steps" });
    expect(steps.querySelectorAll("a")).toHaveLength(2);
    expect(screen.getByRole("link", { name: /PM-KISAN registration/ })).toHaveAttribute("href", "https://pmkisan.gov.in/BeneficiaryStatus_New.aspx");
    expect(screen.queryByText(/appears to meet|you are eligible|not eligible/i)).not.toBeInTheDocument();
  });
  it("shows no next steps for an ordinary answer", () => { render(<Providers><WorkspaceDemo /></Providers>); expect(screen.queryByRole("navigation", { name: "Official next steps" })).not.toBeInTheDocument(); });
  it("labels demo answers as illustrative and tags each answer with its language", async () => {
    render(<Providers><WorkspaceDemo /></Providers>);
    expect(screen.getByText("Illustrative example: not a retrieved answer")).toBeInTheDocument();
    expect(screen.getByRole("article", { name: "Generated answer with retrieved citations" })).toHaveAttribute("lang", "en");
    const hindi = demoResponseForQuery({ query: "भारत में आधार का क्या उपयोग है?" });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ ...hindi, data_mode: "local" }), { status: 200 }));
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Run corpus investigation" }));
    await waitFor(() => expect(screen.getByRole("article", { name: "Generated answer with retrieved citations" })).toHaveAttribute("lang", "hi"));
    expect(screen.getByText("Corpus investigation")).toBeInTheDocument();
  });
  it("keeps the completed research query for edit and resubmit", async () => { vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(demoResponse), { status: 200 })); const user = userEvent.setup(); render(<Providers><WorkspaceDemo /></Providers>); const query = screen.getByLabelText("Ask SETU a question"); const before = (query as HTMLTextAreaElement).value; await user.click(screen.getByRole("button", { name: "Run corpus investigation" })); await screen.findByText("2/2 sections evidence linked"); expect(query).toHaveValue(before); });
  it("prevents duplicate query submissions while one request is pending", async () => { let resolve!: (value: Response) => void; const network = vi.spyOn(globalThis, "fetch").mockImplementation(() => new Promise((done) => { resolve = done; })); const user = userEvent.setup(); render(<Providers><WorkspaceDemo /></Providers>); const submit = screen.getByRole("button", { name: "Run corpus investigation" }); await user.click(submit); await user.click(submit); expect(network).toHaveBeenCalledTimes(1); expect(submit).toBeDisabled(); resolve(new Response(JSON.stringify({ answer: "No evidence.", citations: [], route: "retrieve_docs", confidence: 0 }), { status: 200 })); });
});

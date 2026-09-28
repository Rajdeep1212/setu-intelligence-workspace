import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
  it("keeps the completed research query for edit and resubmit", async () => { vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(demoResponse), { status: 200 })); const user = userEvent.setup(); render(<Providers><WorkspaceDemo /></Providers>); const query = screen.getByLabelText("Ask SETU a question"); const before = (query as HTMLTextAreaElement).value; await user.click(screen.getByRole("button", { name: "Run corpus investigation" })); await screen.findByText("2/2 sections evidence linked"); expect(query).toHaveValue(before); });
  it("prevents duplicate query submissions while one request is pending", async () => { let resolve!: (value: Response) => void; const network = vi.spyOn(globalThis, "fetch").mockImplementation(() => new Promise((done) => { resolve = done; })); const user = userEvent.setup(); render(<Providers><WorkspaceDemo /></Providers>); const submit = screen.getByRole("button", { name: "Run corpus investigation" }); await user.click(submit); await user.click(submit); expect(network).toHaveBeenCalledTimes(1); expect(submit).toBeDisabled(); resolve(new Response(JSON.stringify({ answer: "No evidence.", citations: [], route: "retrieve_docs", confidence: 0 }), { status: 200 })); });
});

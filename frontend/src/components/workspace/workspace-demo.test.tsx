import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Providers } from "@/components/providers";
import { WorkspaceDemo } from "@/components/workspace/workspace-demo";

describe("WorkspaceDemo", () => {
  afterEach(() => vi.restoreAllMocks());
  it("links inline citations to evidence and opens the keyboard command menu", async () => { const user = userEvent.setup(); render(<Providers><WorkspaceDemo /></Providers>); expect(screen.getByText("Evidence linked")).toBeInTheDocument(); await user.click(screen.getByLabelText("Focus evidence 2")); expect(screen.getAllByRole("button", { pressed: true }).some((button) => button.textContent?.includes("E02"))).toBe(true); await user.keyboard("{Control>}k{/Control}"); expect(screen.getByRole("dialog", { name: "Navigate SETU" })).toBeInTheDocument(); });
  it("shows the session-only progressive eligibility workflow", async () => { const user = userEvent.setup(); render(<Providers><WorkspaceDemo /></Providers>); await user.click(screen.getByRole("button", { name: /Eligibility mode/ })); expect(screen.getByText("SETU provides evidence-backed informational guidance, not an official eligibility decision.")).toBeInTheDocument(); expect(screen.getByRole("heading", { name: "Choose a supported criteria set" })).toBeInTheDocument(); await user.click(screen.getByRole("button", { name: /Continue/ })); expect(screen.getByLabelText(/Annual family income/)).toBeInTheDocument(); });
  it("prevents duplicate query submissions while one request is pending", async () => { let resolve!: (value: Response) => void; const network = vi.spyOn(globalThis, "fetch").mockImplementation(() => new Promise((done) => { resolve = done; })); const user = userEvent.setup(); render(<Providers><WorkspaceDemo /></Providers>); const submit = screen.getByRole("button", { name: "Run grounded investigation" }); await user.click(submit); await user.click(submit); expect(network).toHaveBeenCalledTimes(1); expect(submit).toBeDisabled(); resolve(new Response(JSON.stringify({ answer: "Grounded", citations: [], route: "retrieve_docs", confidence: 0 }), { status: 200 })); });
});

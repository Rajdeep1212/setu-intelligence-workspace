import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { Providers } from "@/components/providers";
import { WorkspaceDemo } from "@/components/workspace/workspace-demo";

describe("WorkspaceDemo", () => {
  it("links inline citations to evidence and opens the keyboard command menu", async () => { const user = userEvent.setup(); render(<Providers><WorkspaceDemo /></Providers>); expect(screen.getByText("Grounding passed")).toBeInTheDocument(); await user.click(screen.getByLabelText("Focus evidence 2")); expect(screen.getAllByRole("button", { pressed: true }).some((button) => button.textContent?.includes("E02"))).toBe(true); await user.keyboard("{Control>}k{/Control}"); expect(screen.getByRole("dialog", { name: "Navigate SETU" })).toBeInTheDocument(); });
  it("shows the content-safe eligibility preview", async () => { const user = userEvent.setup(); render(<Providers><WorkspaceDemo /></Providers>); await user.click(screen.getByRole("button", { name: /Eligibility mode/ })); expect(screen.getByText("No personal data collected", { exact: false })).toBeInTheDocument(); });
});

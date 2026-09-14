import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Providers } from "@/components/providers";
import { WorkspaceDemo } from "@/components/workspace/workspace-demo";
import { demoResponse } from "@/lib/fixtures";

function renderWorkspace() {
  return render(<Providers><WorkspaceDemo /></Providers>);
}

async function chooseLanguage(user: ReturnType<typeof userEvent.setup>, label: "English" | "हिन्दी" | "বাংলা") {
  await user.click(screen.getByRole("button", { name: /Response language:/ }));
  const menu = screen.getByRole("menu", { name: "Response language" });
  await user.click(within(menu).getByRole("menuitemradio", { name: label }));
}

describe("WorkspaceDemo", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    window.localStorage.clear();
  });

  it("defaults to English, supports keyboard menu navigation, and has no attachment control", async () => {
    const user = userEvent.setup();
    renderWorkspace();

    const trigger = screen.getByRole("button", { name: "Response language: English" });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByLabelText("Selected response language: English")).not.toBeInTheDocument();
    expect(screen.queryByText("Response language applies to your next request.")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /attach|upload/i })).not.toBeInTheDocument();

    trigger.focus();
    await user.keyboard("{ArrowDown}");
    const menu = screen.getByRole("menu", { name: "Response language" });
    await waitFor(() => expect(within(menu).getByRole("menuitemradio", { name: "English" })).toHaveFocus());
    await user.keyboard("{ArrowDown}{ArrowDown}{Enter}");
    expect(screen.getByRole("button", { name: "Response language: বাংলা" })).toHaveFocus();
  });

  it("persists the response-language selection without storing the question", async () => {
    const user = userEvent.setup();
    const first = renderWorkspace();
    await chooseLanguage(user, "हिन्दी");
    expect(window.localStorage.getItem("setu-response-language-v1")).toBe("hi");
    expect(JSON.stringify(window.localStorage)).not.toContain("What are the core components");

    first.unmount();
    renderWorkspace();
    await waitFor(() => expect(screen.getByRole("button", { name: "Response language: हिन्दी" })).toBeInTheDocument());
  });

  it("captures the exact question and selected language for each request", async () => {
    let resolveRequest!: (value: Response) => void;
    const network = vi.spyOn(globalThis, "fetch").mockImplementation(() => new Promise((resolve) => { resolveRequest = resolve; }));
    const user = userEvent.setup();
    renderWorkspace();
    const query = screen.getByLabelText("Ask SETU a question");
    const exactQuestion = "  What does PM-KISAN provide?  ";

    fireEvent.change(query, { target: { value: exactQuestion } });
    await chooseLanguage(user, "বাংলা");
    await user.click(screen.getByRole("button", { name: "Ask SETU" }));
    expect(screen.getByText("Request in progress")).toBeInTheDocument();

    await chooseLanguage(user, "हिन्दी");
    const payload = JSON.parse(String(network.mock.calls[0]?.[1]?.body));
    expect(payload).toEqual({ query: exactQuestion, language: "bn" });
    expect(query).toHaveValue(exactQuestion);

    resolveRequest(new Response(JSON.stringify(demoResponse), { status: 200 }));
    await waitFor(() => expect(screen.queryByText("Request in progress")).not.toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Response language: हिन्दी" })).toBeInTheDocument();
  });

  it("shows official source and application links as distinct actions", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
      ...demoResponse,
      official_links: [{ kind: "application", label: "Official application page", url: "https://apply.example.gov.in/" }],
    }), { status: 200 }));
    const user = userEvent.setup();
    renderWorkspace();

    await user.click(screen.getByRole("button", { name: "Ask SETU" }));

    const links = await screen.findByRole("navigation", { name: "Official source and service links" });
    expect(within(links).getByRole("link", { name: /Official source: India's Digital Public Infrastructure/ })).toHaveAttribute("href", "https://www.pib.gov.in/");
    expect(within(links).getByRole("link", { name: "Official application page" })).toHaveAttribute("data-link-kind", "application");
  });

  it("preserves input and the prior answer when a request fails", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
      error: { code: "BACKEND_UNAVAILABLE", message: "unsafe upstream detail", request_id: "request-1" },
    }), { status: 503 }));
    const user = userEvent.setup();
    renderWorkspace();
    const query = screen.getByLabelText("Ask SETU a question");
    const exactQuestion = "A question that should remain editable";
    fireEvent.change(query, { target: { value: exactQuestion } });

    await user.click(screen.getByRole("button", { name: "Ask SETU" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("SETU is temporarily unavailable.");
    expect(query).toHaveValue(exactQuestion);
    expect(screen.getByText(/India's digital approach connects digital identity/)).toBeInTheDocument();
  });

  it("expands and focuses source passages from claim citations", async () => {
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", { configurable: true, value: vi.fn() });
    const user = userEvent.setup();
    renderWorkspace();

    await user.click(screen.getByRole("button", { name: "Open source 2 for claim 2" }));
    const sources = screen.getByRole("region", { name: "Retrieved sources" });
    expect(within(sources).getByRole("heading", { name: "The rise of India's DPI stack" })).toBeVisible();
    await waitFor(() => expect(document.querySelector("#source-1")).toHaveFocus());
    expect(within(sources).getAllByRole("link", { name: "View source" })[0]).toHaveAttribute("target", "_blank");
  });

  it("keeps eligibility quarantined and opens navigation from the keyboard", async () => {
    const user = userEvent.setup();
    renderWorkspace();
    await user.keyboard("{Control>}k{/Control}");
    const dialog = screen.getByRole("dialog", { name: "Navigate SETU" });
    await user.click(within(dialog).getByRole("button", { name: /Eligibility preview/ }));
    expect(screen.getByText("Illustrative eligibility experience")).toBeInTheDocument();
  });
});

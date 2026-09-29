import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { RoadsideMode } from "@/components/roadside/roadside-mode";

function stateAmountSection() {
  return screen.getByRole("region", { name: /On-the-spot amount in/ });
}

describe("RoadsideMode", () => {
  it("opens on West Bengal handheld-device use with the verified amounts and their notification", () => {
    render(<RoadsideMode />);
    const section = stateAmountSection();
    expect(within(section).getByText("₹5,000")).toBeInTheDocument();
    expect(within(section).getByText("₹10,000")).toBeInTheDocument();
    expect(within(section).getByText(/208-WT/)).toBeInTheDocument();
    expect(within(section).getByRole("link", { name: /Official source/ })).toHaveAttribute(
      "href",
      expect.stringMatching(/^https:\/\/transport\.wb\.gov\.in\//),
    );
  });

  it("shows no number for Delhi", async () => {
    const user = userEvent.setup();
    render(<RoadsideMode />);
    await user.selectOptions(screen.getByLabelText("State"), "IN-DL");
    const section = stateAmountSection();
    expect(within(section).getByText("No verified amount yet")).toBeInTheDocument();
    expect(section.textContent).not.toMatch(/₹/);
  });

  it("shows Karnataka's lower helmet amount beside the central fine, clearly labelled", async () => {
    const user = userEvent.setup();
    render(<RoadsideMode />);
    await user.selectOptions(screen.getByLabelText("State"), "IN-KA");
    await user.selectOptions(screen.getByLabelText("Offence"), "helmet");
    const section = stateAmountSection();
    expect(within(section).getByText("₹500")).toBeInTheDocument();
    expect(within(section).getByText("Below central fine")).toBeInTheDocument();
    expect(within(section).getByText(/central Act names a fine of ₹1,000/)).toBeInTheDocument();
  });

  it("explains red-light jumping is under legal review without an amount", async () => {
    const user = userEvent.setup();
    render(<RoadsideMode />);
    await user.selectOptions(screen.getByLabelText("Offence"), "red_light");
    const section = stateAmountSection();
    expect(within(section).getByText("Under legal review")).toBeInTheDocument();
    expect(section.textContent).not.toMatch(/₹/);
    expect(screen.getAllByText("Police fine list (not a notification)").length).toBeGreaterThan(0);
  });

  it("gives calm checkpoint guidance and never coaches confrontation", () => {
    render(<RoadsideMode />);
    const checkpoint = screen.getByRole("region", { name: "At a checkpoint" });
    expect(checkpoint).toHaveTextContent(/e-challan or an official receipt/);
    expect(checkpoint).toHaveTextContent(/contest it later through official channels/);
    expect(checkpoint).toHaveTextContent(/DigiLocker or mParivahan/);
    expect(checkpoint).toHaveTextContent(/Not legal advice/);
    const page = document.body.textContent ?? "";
    for (const phrase of [/\brefuse\b/i, /\bargue\b/i, /officer is wrong/i, /don't pay/i, /bribe/i, /record the officer/i]) {
      expect(page).not.toMatch(phrase);
    }
  });
});

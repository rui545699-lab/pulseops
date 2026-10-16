import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { RunInvestigation } from "@/components/run-investigation";
import { dataQualityRun, lifecycleOpportunity, lifecycleRun, noSignalRun, opportunity, run } from "@/test/fixtures";

describe("Run Investigation", () => {
  beforeEach(() => vi.clearAllMocks());

  it("POSTs a run and navigates to its generated opportunity", async () => {
    const navigate = vi.fn();
    const createRun = vi.fn().mockResolvedValue(run);
    render(<RunInvestigation createRun={createRun} listOpportunities={async () => [opportunity]} onNavigate={navigate} />);
    await fillAndSubmit();
    await waitFor(() => expect(createRun).toHaveBeenCalledWith(expect.objectContaining({ planner_mode: "deterministic", analysis_type: "CONVERSION" })));
    expect(navigate).toHaveBeenCalledWith("/opportunities/opportunity-01");
  });

  it("offers AI Planner without exposing the provider brand", async () => {
    render(<RunInvestigation />);
    await userEvent.click(screen.getByRole("button", { name: "New investigation" }));
    expect(screen.getByRole("option", { name: "AI Planner" })).toBeInTheDocument();
    expect(screen.queryByText("DeepSeek")).not.toBeInTheDocument();
  });

  it("shows Data Quality Alert without inventing an opportunity", async () => {
    render(<RunInvestigation createRun={async () => dataQualityRun} listOpportunities={vi.fn()} />);
    await fillAndSubmit();
    expect(await screen.findByText("Data Quality Alert")).toBeInTheDocument();
    expect(screen.getByText(/No opportunity was created/)).toBeInTheDocument();
  });

  it("shows the no-material-signal state", async () => {
    render(<RunInvestigation createRun={async () => noSignalRun} listOpportunities={vi.fn()} />);
    await fillAndSubmit();
    expect(await screen.findByText("No material opportunity detected.")).toBeInTheDocument();
  });

  it("shows a concise API error", async () => {
    render(<RunInvestigation createRun={async () => { throw new Error("Service unavailable"); }} />);
    await fillAndSubmit();
    expect(await screen.findByRole("alert")).toHaveTextContent("Service unavailable");
  });

  it("includes Post dates for a Lifecycle Risk investigation", async () => {
    const createRun = vi.fn().mockResolvedValue(lifecycleRun);
    render(<RunInvestigation createRun={createRun} listOpportunities={async () => [lifecycleOpportunity]} onNavigate={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "New investigation" }));
    await userEvent.selectOptions(screen.getByLabelText("Analysis Type"), "LIFECYCLE_RISK");
    fireEvent.change(screen.getByLabelText("Baseline Start"), { target: { value: "2020-11-30" } });
    fireEvent.change(screen.getByLabelText("Baseline End"), { target: { value: "2020-12-13" } });
    fireEvent.change(screen.getByLabelText("Target Start"), { target: { value: "2020-12-21" } });
    fireEvent.change(screen.getByLabelText("Target End"), { target: { value: "2021-01-03" } });
    fireEvent.change(screen.getByLabelText("Post Start"), { target: { value: "2021-01-04" } });
    fireEvent.change(screen.getByLabelText("Post End"), { target: { value: "2021-01-24" } });
    await userEvent.click(screen.getByRole("button", { name: "Run investigation" }));
    await waitFor(() => expect(createRun).toHaveBeenCalledWith(expect.objectContaining({
      analysis_type: "LIFECYCLE_RISK",
      post_start: "2021-01-04",
      post_end: "2021-01-24",
    })));
  });
});

async function fillAndSubmit() {
  if (!screen.queryByLabelText("Baseline Start")) {
    await userEvent.click(screen.getByRole("button", { name: "New investigation" }));
  }
  fireEvent.change(screen.getByLabelText("Baseline Start"), { target: { value: "2020-12-07" } });
  fireEvent.change(screen.getByLabelText("Baseline End"), { target: { value: "2020-12-13" } });
  fireEvent.change(screen.getByLabelText("Target Start"), { target: { value: "2020-12-21" } });
  fireEvent.change(screen.getByLabelText("Target End"), { target: { value: "2020-12-27" } });
  await userEvent.click(screen.getByRole("button", { name: "Run investigation" }));
}

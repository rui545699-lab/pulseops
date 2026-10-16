import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RunDetailView } from "@/components/run-detail";
import { growthRun, growthSteps, lifecycleRun, lifecycleSteps, run, steps } from "@/test/fixtures";

describe("Investigation Run", () => {
  it("sorts the timeline by step_order", () => {
    render(<RunDetailView run={run} steps={steps} />);
    const headings = screen.getAllByRole("heading", { level: 3 }).map((item) => item.textContent);
    expect(headings).toEqual([
      "Validate Data",
      "Scan Metrics",
      "Strict Funnel",
      "Lifecycle",
      "Device",
      "Acquisition",
      "Category",
      "Stop Investigation",
    ]);
  });

  it("renders accepted and rejected guard outcomes", () => {
    render(<RunDetailView run={run} steps={steps} />);
    expect(screen.getAllByText("Accepted").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Rejected").length).toBeGreaterThanOrEqual(1);
  });

  it("shows planner, provider, and model only as technical details", () => {
    render(<RunDetailView run={run} steps={steps} />);
    expect(screen.getByText("AI Planner")).toBeInTheDocument();
    expect(screen.getByText("DeepSeek")).toBeInTheDocument();
    expect(screen.getByText("planner-model")).toBeInTheDocument();
  });

  it("explains allowed-dimensions stop as correct behavior", () => {
    render(<RunDetailView run={run} steps={steps} />);
    expect(screen.getByRole("heading", { name: "Investigation stopped" })).toBeInTheDocument();
    expect(screen.getAllByText(/All permitted dimensions were investigated/).length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText("Analysis failed.")).not.toBeInTheDocument();
  });

  it("summarizes what each investigation step established from stored tool output", () => {
    render(<RunDetailView run={run} steps={steps} />);
    expect(screen.getByText("Required data-quality checks passed.")).toBeInTheDocument();
    expect(screen.getByText("View→Cart decline detected: -8.68pp.")).toBeInTheDocument();
    expect(screen.getByText(/31.60% → 22.92%.*strict same-user \/ same-session ordering/)).toBeInTheDocument();
    expect(screen.getAllByText(/New Users: -11.56pp.*Returning Users: -0.57pp/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Desktop: -11.74pp.*Mobile: -11.01pp.*Device concentration rejected/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Major sources declined within-source.*Acquisition-mix explanation rejected/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Category effects were mixed.*Insufficient evidence/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/All permitted dimensions were investigated/).length).toBeGreaterThanOrEqual(1);
  });

  it("keeps fallback hidden when no fallback occurred", () => {
    render(<RunDetailView run={run} steps={steps} />);
    expect(screen.queryByText("Fallback")).not.toBeInTheDocument();
  });

  it("renders the lifecycle investigation as product findings", () => {
    render(<RunDetailView run={lifecycleRun} steps={lifecycleSteps} />);
    const headings = screen.getAllByRole("heading", { level: 3 }).map((item) => item.textContent);
    expect(headings).toEqual([
      "Validate Data",
      "Analyze Retention",
      "Return Timing",
      "Recovery",
      "Acquisition",
      "Device",
      "Activation Depth",
      "Stop Investigation",
    ]);
    expect(screen.getByText(/D7 Return 8.33% → 5.11%, -3.22pp/)).toBeInTheDocument();
    expect(screen.getByText(/Users shifted shallower.*within-bucket decline dominated/)).toBeInTheDocument();
  });

  it("derives recovery timeline copy from stored lifecycle results", () => {
    const stepsWithFullRecovery = lifecycleSteps.map((step) => step.node === "CHECK_RECOVERY"
      ? { ...step, tool_output_summary: { post_rate: 8.3, risk_pattern: "FULL_RECOVERY" } }
      : step);
    render(<RunDetailView run={{ ...lifecycleRun, post_rate: 8.3, risk_pattern: "FULL_RECOVERY" }} steps={stepsWithFullRecovery} />);
    expect(screen.getByText("Post D7 Return: 8.30%. Recovery classification: Full Recovery.")).toBeInTheDocument();
  });

  it("renders positive-growth segment findings as observational breadth without negative-case leakage", () => {
    render(<RunDetailView run={growthRun} steps={growthSteps} />);

    expect(screen.getByText(/New users improved \+9.21pp and Returning users improved \+5.61pp/)).toBeInTheDocument();
    expect(screen.getByText(/Within-device improvement \(\+10.80pp\) dominated device composition effect \(-0.02pp\)/)).toBeInTheDocument();
    expect(screen.getByText(/Major acquisition sources broadly improved within-source/)).toBeInTheDocument();
    expect(screen.getAllByText("Observed breadth")).toHaveLength(3);
    expect(screen.getAllByText(/no causal mechanism is established/)).toHaveLength(3);
    expect(screen.queryByText(/declined within-source|device concentration supported|acquisition-mix explanation supported/i)).not.toBeInTheDocument();
    expect(screen.queryByText("Hypothesis:")).not.toBeInTheDocument();
  });
});

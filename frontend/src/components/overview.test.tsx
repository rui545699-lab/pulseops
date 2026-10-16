import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { OverviewClient, OverviewView } from "@/components/overview";
import { growthOpportunity, growthRun, multiOpportunityOverview, overviewData } from "@/test/fixtures";

describe("Overview", () => {
  it("loads an opportunity from the supplied API loader", async () => {
    render(<OverviewClient loader={async () => overviewData} />);
    expect(await screen.findByRole("heading", { name: "New-user View→Cart decline" })).toBeInTheDocument();
  });

  it("shows a loading state while API data is pending", () => {
    render(<OverviewClient loader={() => new Promise(() => undefined)} />);
    expect(screen.getByRole("status", { name: "Loading overview" })).toBeInTheDocument();
  });

  it("shows a concise API error state", async () => {
    render(<OverviewClient loader={async () => { throw new Error("Backend unavailable"); }} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Backend unavailable");
  });

  it("keeps localized and overall metric scopes distinct", () => {
    render(<OverviewView data={overviewData} />);
    const localized = screen.getByText("Localized opportunity").parentElement;
    const overall = screen.getByText("Overall detected signal").parentElement;
    expect(localized).toHaveTextContent("31.04%");
    expect(localized).toHaveTextContent("19.48%");
    expect(localized).toHaveTextContent("-11.56pp");
    expect(overall).toHaveTextContent("31.60% → 22.92%");
    expect(overall).toHaveTextContent("-8.68pp");
  });

  it("computes summary values from API records", () => {
    render(<OverviewView data={overviewData} />);
    const summary = screen.getByRole("region", { name: "Workspace summary" });
    expect(summary).toHaveTextContent("Active Opportunities1");
    expect(summary).toHaveTextContent("Completed Runs1");
    expect(summary).toHaveTextContent("Needs Evidence1");
    expect(summary).toHaveTextContent("High-confidence Signals1");
  });

  it("uses explicit root-cause terminology", () => {
    render(<OverviewView data={overviewData} />);
    expect(screen.getByText("Root Cause LOW")).toBeInTheDocument();
    expect(screen.queryByText("Cause LOW")).not.toBeInTheDocument();
  });

  it("distinguishes conversion and lifecycle opportunity types", () => {
    render(<OverviewView data={multiOpportunityOverview} />);
    expect(screen.getByText("Lifecycle Risk")).toBeInTheDocument();
    expect(screen.getByText("Conversion / Activation")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "New-user 7-day return risk with partial recovery" })).toBeInTheDocument();
  });

  it("shows a positive-growth opportunity with reproducibility evidence", () => {
    render(<OverviewView data={{ opportunities: [{ opportunity: growthOpportunity, run: growthRun }], runs: [growthRun] }} />);
    expect(screen.getByText("Positive Growth")).toBeInTheDocument();
    expect(screen.getByText("Reproducibility")).toBeInTheDocument();
    expect(screen.getByText("Reproduced")).toBeInTheDocument();
  });

  it("renders a truthful empty state", () => {
    render(<OverviewView data={{ opportunities: [], runs: [] }} />);
    expect(screen.getByText("No opportunities detected.")).toBeInTheDocument();
    expect(screen.getByText("No investigations yet.")).toBeInTheDocument();
  });
});

import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { OpportunityDetailView } from "@/components/opportunity-detail";
import { growthOpportunity, growthRun, lifecycleOpportunity, lifecycleRun, opportunity, run } from "@/test/fixtures";

describe("Opportunity Detail", () => {
  it("renders the localized opportunity metric", () => {
    render(<OpportunityDetailView opportunity={opportunity} run={run} />);
    const scopes = screen.getByRole("region", { name: "Metric scope comparison" });
    expect(scopes).toHaveTextContent("31.04%");
    expect(scopes).toHaveTextContent("19.48%");
    expect(scopes).toHaveTextContent("-11.56pp");
  });

  it("renders the weaker overall detected signal beside it", () => {
    render(<OpportunityDetailView opportunity={opportunity} run={run} />);
    expect(screen.getByText(/Overall detected signal/).parentElement).toHaveTextContent("31.60%");
    expect(screen.getByText(/Overall detected signal/).parentElement).toHaveTextContent("-8.68pp");
  });

  it("separates Evidence, Hypotheses, and Unknowns", () => {
    render(<OpportunityDetailView opportunity={opportunity} run={run} />);
    const discipline = screen.getByRole("region", { name: "Evidence discipline" });
    expect(within(discipline).getByRole("heading", { name: "Evidence" })).toBeInTheDocument();
    expect(within(discipline).getByRole("heading", { name: "Hypotheses" })).toBeInTheDocument();
    expect(within(discipline).getByRole("heading", { name: "Unknowns" })).toBeInTheDocument();
  });

  it("labels hypotheses as unverified", () => {
    render(<OpportunityDetailView opportunity={opportunity} run={run} />);
    expect(screen.getByText("Unverified")).toBeInTheDocument();
    expect(screen.getByText("Plausible explanations—not established facts.")).toBeInTheDocument();
    expect(screen.queryByText(/this is unverified/i)).not.toBeInTheDocument();
  });

  it("shows HIGH signal and LOW root-cause confidence together", () => {
    render(<OpportunityDetailView opportunity={opportunity} run={run} />);
    const confidence = screen.getByRole("region", { name: "Confidence" });
    expect(confidence).toHaveTextContent("Signal ConfidenceHIGH");
    expect(confidence).toHaveTextContent("Root-cause ConfidenceLOW");
  });

  it("renders the recommended evidence-collection action", () => {
    render(<OpportunityDetailView opportunity={opportunity} run={run} />);
    expect(screen.getByRole("heading", { name: "Evidence Collection" })).toBeInTheDocument();
    expect(screen.getByText(opportunity.recommended_next_action!)).toBeInTheDocument();
  });

  it("renders do-not-recommend-yet boundaries", () => {
    render(<OpportunityDetailView opportunity={opportunity} run={run} />);
    expect(screen.getByText("Do not recommend yet")).toBeInTheDocument();
    expect(screen.getByText("Broad discounts or coupons")).toBeInTheDocument();
  });

  it("renders lifecycle recovery and return timing without causalizing calendar context", () => {
    render(<OpportunityDetailView opportunity={lifecycleOpportunity} run={lifecycleRun} />);
    expect(screen.getByRole("heading", { name: "New-user 7-day return risk with partial recovery" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Partial Recovery relative to Baseline" })).toBeInTheDocument();
    expect(screen.getByText("55.73%")).toBeInTheDocument();
    const timing = screen.getByRole("heading", { name: "Return Timing" }).parentElement;
    expect(timing).toHaveTextContent("4.60%");
    expect(timing).toHaveTextContent("2.90%");
    expect(timing).toHaveTextContent("6.90%");
    expect(screen.getByText(/Calendar timing remains a hypothesis, not a proven cause/)).toBeInTheDocument();
  });

  it("derives lifecycle recovery labels from the stored risk pattern", () => {
    render(
      <OpportunityDetailView
        opportunity={{
          ...lifecycleOpportunity,
          title: "New-user 7-day return risk with no observed recovery",
          risk_pattern: "NO_RECOVERY",
        }}
        run={{ ...lifecycleRun, risk_pattern: "NO_RECOVERY" }}
      />,
    );
    expect(screen.getByRole("heading", { name: "No Recovery relative to Baseline" })).toBeInTheDocument();
  });

  it("renders positive growth persistence without causalizing the lift", () => {
    render(<OpportunityDetailView opportunity={growthOpportunity} run={growthRun} />);
    expect(screen.getByText("Positive Growth")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Growth confirmation and holdouts" })).toBeInTheDocument();
    expect(screen.getByText("55.07%")).toBeInTheDocument();
    const confidence = screen.getByRole("region", { name: "Confidence" });
    expect(confidence).toHaveTextContent("Growth Signal ConfidenceHIGH");
    expect(confidence).toHaveTextContent("Reproducibility ConfidenceHIGH");
    expect(screen.getByText(/Validated lift ≠ proven growth mechanism/)).toBeInTheDocument();
  });

  it.each(["PARTIALLY_REPRODUCED", "NOT_REPRODUCED"])(
    "renders %s as its actual reproducibility state",
    (reproducibility) => {
      render(
        <OpportunityDetailView
          opportunity={{ ...growthOpportunity, reproducibility }}
          run={{ ...growthRun, reproducibility }}
        />,
      );
      expect(screen.getByText(reproducibility === "PARTIALLY_REPRODUCED" ? "Partially Reproduced" : "Not Reproduced")).toBeInTheDocument();
      expect(screen.queryByText("REPRODUCED")).not.toBeInTheDocument();
    },
  );

  it("renders missing positive-growth localization as Unknown", () => {
    render(
      <OpportunityDetailView
        opportunity={{ ...growthOpportunity, growth_localization: null }}
        run={{ ...growthRun, growth_localization: null }}
      />,
    );
    expect(screen.getByText("Localization · Unknown")).toBeInTheDocument();
  });

  it("renders safely without AOV context", () => {
    render(
      <OpportunityDetailView
        opportunity={{ ...growthOpportunity, order_value_context: null }}
        run={growthRun}
      />,
    );
    expect(screen.getByRole("heading", { name: "Growth confirmation and holdouts" })).toBeInTheDocument();
    expect(screen.queryByText(/AOV context:/)).not.toBeInTheDocument();
  });
});

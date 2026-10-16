"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ArrowRightIcon } from "@/components/icons";
import { MetricScope } from "@/components/metric-scope";
import { RunInvestigation } from "@/components/run-investigation";
import { EmptyState, ErrorState, PageLoading } from "@/components/states";
import { StatusBadge } from "@/components/status-badge";
import { loadOverview } from "@/lib/api";
import { dateTimeLabel, formatDelta, formatRate, humanize, opportunityTitle, plannerLabel, segmentLabel } from "@/lib/format";
import type { OverviewData } from "@/lib/types";

export function OverviewClient({ loader = loadOverview }: { loader?: () => Promise<OverviewData> }) {
  const [data, setData] = useState<OverviewData | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function retry() {
    setError(null);
    try {
      setData(await loader());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The Product API is unavailable.");
    }
  }

  useEffect(() => {
    let active = true;
    void loader().then(
      (value) => active && setData(value),
      (reason: unknown) => active && setError(reason instanceof Error ? reason.message : "The Product API is unavailable."),
    );
    return () => {
      active = false;
    };
  }, [loader]);

  if (error) return <ErrorState message={error} retry={() => void retry()} />;
  if (!data) return <PageLoading label="Loading overview" />;
  return <OverviewView data={data} />;
}

export function OverviewView({ data }: { data: OverviewData }) {
  const active = data.opportunities.filter(({ opportunity }) => opportunity.status !== "CLOSED").length;
  const needsEvidence = data.opportunities.filter(({ opportunity }) => opportunity.status === "NEEDS_EVIDENCE").length;
  const completed = data.runs.filter((run) => run.status === "COMPLETED").length;
  const highConfidence = data.runs.filter((run) => run.signal_confidence === "HIGH" && run.detected_signal).length;

  return (
    <div className="space-y-12">
      <section className="grid gap-8 lg:grid-cols-[1fr_auto] lg:items-end">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[#777771]">AI User Operations Agent</p>
          <h1 className="mt-3 text-4xl font-semibold tracking-[-0.045em] sm:text-5xl">PulseOps</h1>
          <p className="mt-4 max-w-2xl text-base leading-7 text-[#666660] sm:text-lg">
            Discover what changed, who it affects, and what to do next.
          </p>
        </div>
        <p className="max-w-sm text-sm leading-6 text-[#777771] lg:text-right">
          Evidence-led investigations that know when to continue—and when to stop.
        </p>
      </section>

      <SummaryGrid active={active} completed={completed} needsEvidence={needsEvidence} highConfidence={highConfidence} />
      <RunInvestigation />

      <section id="opportunities" aria-labelledby="recent-opportunities-heading" className="scroll-mt-24">
        <SectionHeading id="recent-opportunities-heading" title="Recent Opportunities" description="Material behavioral shifts, localized to the people they affect." />
        <div className="mt-5 space-y-4">
          {data.opportunities.length ? data.opportunities.map(({ opportunity, run }) => (
            <Link key={opportunity.id} href={`/opportunities/${opportunity.id}`} className="group block rounded-xl border border-[#deded9] bg-white p-5 transition-all hover:-translate-y-0.5 hover:border-[#c5c5bf] hover:shadow-[0_12px_35px_rgba(0,0,0,0.05)] sm:p-6">
              <div className="grid gap-7 lg:grid-cols-[1.2fr_1fr_0.9fr_auto] lg:items-center">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusBadge value={opportunity.status} />
                    <StatusBadge
                      value={opportunity.opportunity_type}
                      label={opportunity.opportunity_type === "LIFECYCLE_RISK" ? "Lifecycle Risk" : opportunity.opportunity_type === "POSITIVE_GROWTH" ? "Positive Growth" : "Conversion / Activation"}
                    />
                    <span className="text-[11px] text-[#8a8a84]">{dateTimeLabel(opportunity.created_at)}</span>
                  </div>
                  <h3 className="mt-3 text-xl font-semibold tracking-[-0.025em]">{opportunity.opportunity_type === "LIFECYCLE_RISK" || opportunity.opportunity_type === "POSITIVE_GROWTH" ? opportunity.title : opportunityTitle(opportunity.metric, opportunity.affected_segment)}</h3>
                  <p className="mt-1.5 text-sm text-[#72726c]">Affected segment: <span className="font-medium text-[#343431]">{segmentLabel(opportunity.affected_segment)}</span></p>
                </div>
                <MetricScope eyebrow={opportunity.opportunity_type === "LIFECYCLE_RISK" ? "Lifecycle risk" : opportunity.opportunity_type === "POSITIVE_GROWTH" ? "Validated growth signal" : "Localized opportunity"} baseline={opportunity.baseline_rate} target={opportunity.target_rate} delta={opportunity.delta_pp} />
                <div className="border-l-0 border-[#e8e8e4] lg:border-l lg:pl-7">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[#8a8a84]">{opportunity.opportunity_type === "LIFECYCLE_RISK" ? "Recovery" : opportunity.opportunity_type === "POSITIVE_GROWTH" ? "Reproducibility" : "Overall detected signal"}</p>
                  <p className="mt-2 text-sm font-medium">{opportunity.opportunity_type === "LIFECYCLE_RISK" ? opportunity.risk_pattern?.replaceAll("_", " ") : opportunity.opportunity_type === "POSITIVE_GROWTH" ? humanize(opportunity.reproducibility) : (run?.detected_signal ?? opportunity.metric)}</p>
                  <p className="mt-1 text-sm tabular-nums text-[#686862]">
                    {opportunity.opportunity_type === "LIFECYCLE_RISK" ? (
                      <>Target {formatRate(opportunity.target_rate)} → Post {formatRate(opportunity.post_rate)}</>
                    ) : opportunity.opportunity_type === "POSITIVE_GROWTH" ? (
                      <>Confirmation {formatRate(opportunity.confirmation_period?.conversion_rate ?? null)} <span className="ml-1 text-[#2f7666]">{formatDelta(opportunity.delta_pp)}</span></>
                    ) : (
                      <>{formatRate(run?.overall_baseline_rate ?? null)} → {formatRate(run?.overall_target_rate ?? null)} <span className="ml-1 text-[#984a3e]">{formatDelta(run?.overall_delta_pp ?? null)}</span></>
                    )}
                  </p>
                </div>
                <div className="flex items-center justify-between gap-5 lg:justify-end">
                  <div className="flex gap-2 lg:flex-col">
                    <StatusBadge value={opportunity.signal_confidence} label={`Signal ${opportunity.signal_confidence}`} />
                    {opportunity.opportunity_type === "POSITIVE_GROWTH" ? <StatusBadge value={opportunity.reproducibility_confidence ?? "LOW"} label={`Repro ${opportunity.reproducibility_confidence ?? "LOW"}`} /> : null}
                    <StatusBadge value={opportunity.root_cause_confidence} label={`Root Cause ${opportunity.root_cause_confidence}`} />
                  </div>
                  <ArrowRightIcon className="size-5 text-[#999993] transition-transform group-hover:translate-x-1" />
                </div>
              </div>
            </Link>
          )) : <EmptyState title="No opportunities detected." body="Run an investigation to evaluate a new comparison window. Data-quality failures and non-material signals will not create opportunities." />}
        </div>
      </section>

      <section id="runs" aria-labelledby="recent-runs-heading" className="scroll-mt-24">
        <SectionHeading id="recent-runs-heading" title="Investigation Runs" description="A traceable record of what the agent checked and why it stopped." />
        <div className="mt-5 overflow-hidden rounded-xl border border-[#deded9] bg-white">
          {data.runs.length ? (
            <div className="divide-y divide-[#ecece8]">
              {data.runs.slice(0, 8).map((run) => (
                <Link href={`/runs/${run.id}`} key={run.id} className="grid gap-3 px-5 py-4 transition-colors hover:bg-[#fafaf8] sm:grid-cols-[1fr_1fr_auto_auto] sm:items-center sm:px-6">
                  <div>
                    <p className="text-sm font-medium">{run.detected_signal ?? (run.recommended_status === "DATA_QUALITY_ALERT" ? "Data quality check" : "No material signal")}</p>
                    <p className="mt-1 text-xs text-[#85857f]">{run.baseline_start} – {run.target_end}</p>
                  </div>
                  <p className="text-xs text-[#666660]">{plannerLabel(run.planner_mode)}</p>
                  <StatusBadge value={run.recommended_status ?? run.status} />
                  <ArrowRightIcon className="hidden size-4 text-[#aaa9a3] sm:block" />
                </Link>
              ))}
            </div>
          ) : <EmptyState title="No investigations yet." body="Create the first bounded analysis from the form above." />}
        </div>
      </section>
    </div>
  );
}

function SummaryGrid({ active, completed, needsEvidence, highConfidence }: { active: number; completed: number; needsEvidence: number; highConfidence: number }) {
  const items = [
    ["Active Opportunities", active],
    ["Completed Runs", completed],
    ["Needs Evidence", needsEvidence],
    ["High-confidence Signals", highConfidence],
  ] as const;
  return (
    <section aria-label="Workspace summary" className="grid overflow-hidden rounded-xl border border-[#deded9] bg-white sm:grid-cols-2 lg:grid-cols-4">
      {items.map(([label, value], index) => (
        <div key={label} className={`p-5 sm:p-6 ${index ? "border-t border-[#e8e8e4] sm:border-l sm:border-t-0" : ""} ${index === 2 ? "sm:border-l-0 lg:border-l" : ""}`}>
          <p className="text-[11px] font-medium text-[#777771]">{label}</p>
          <p className="mt-3 text-3xl font-semibold tracking-[-0.04em] tabular-nums">{value}</p>
        </div>
      ))}
    </section>
  );
}

function SectionHeading({ id, title, description }: { id: string; title: string; description: string }) {
  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
      <h2 id={id} className="text-xl font-semibold tracking-[-0.025em]">{title}</h2>
      <p className="text-sm text-[#777771]">{description}</p>
    </div>
  );
}

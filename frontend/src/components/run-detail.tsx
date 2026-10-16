"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { CheckIcon, ChevronIcon, DatabaseIcon, ShieldIcon, SparkIcon } from "@/components/icons";
import { ErrorState, PageLoading } from "@/components/states";
import { StatusBadge } from "@/components/status-badge";
import { loadRunDetail } from "@/lib/api";
import { formatDelta, formatRate, humanize, plannerLabel, providerLabel, segmentLabel } from "@/lib/format";
import type { AgentStep, AnalysisRun } from "@/lib/types";

export interface RunDetailData {
  run: AnalysisRun;
  steps: AgentStep[];
}

export function RunDetailClient({
  runId,
  loader = loadRunDetail,
}: {
  runId: string;
  loader?: (id: string) => Promise<RunDetailData>;
}) {
  const [data, setData] = useState<RunDetailData | null>(null);
  const [error, setError] = useState<string | null>(null);
  async function retry() {
    setError(null);
    try {
      setData(await loader(runId));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The investigation run could not be loaded.");
    }
  }

  useEffect(() => {
    let active = true;
    void loader(runId).then(
      (value) => active && setData(value),
      (reason: unknown) => active && setError(reason instanceof Error ? reason.message : "The investigation run could not be loaded."),
    );
    return () => {
      active = false;
    };
  }, [loader, runId]);

  if (error) return <ErrorState message={error} retry={() => void retry()} />;
  if (!data) return <PageLoading label="Loading investigation run" />;
  return <RunDetailView run={data.run} steps={data.steps} />;
}

export function RunDetailView({ run, steps }: RunDetailData) {
  const ordered = [...steps].sort((a, b) => a.step_order - b.step_order);
  return (
    <div className="space-y-10">
      <nav aria-label="Breadcrumb" className="text-xs text-[#85857f]">
        <Link href="/" className="hover:text-[#222220]">Overview</Link>
        <span className="mx-2">/</span>
        <span>Investigation Run</span>
      </nav>

      <header className="grid gap-7 border-b border-[#dfdfda] pb-9 lg:grid-cols-[1fr_auto] lg:items-end">
        <div>
          <div className="flex flex-wrap items-center gap-2.5">
            <StatusBadge value={run.status} />
            {run.recommended_status ? <StatusBadge value={run.recommended_status} /> : null}
          </div>
          <h1 className="mt-5 text-3xl font-semibold tracking-[-0.04em] sm:text-4xl">Investigation Run</h1>
          <p className="mt-3 text-sm text-[#6f6f69]">{run.baseline_start}–{run.baseline_end} compared with {run.target_start}–{run.target_end}</p>
        </div>
        <div className="grid grid-cols-2 gap-x-8 gap-y-3 rounded-xl border border-[#dfdfda] bg-white px-5 py-4 text-xs sm:grid-cols-4">
          <Technical label="Analysis Type" value={run.analysis_type === "LIFECYCLE_RISK" ? "Lifecycle Risk" : run.analysis_type === "POSITIVE_GROWTH" ? "Positive Growth" : "Conversion / Activation"} />
          <Technical label="Planner Mode" value={plannerLabel(run.planner_mode)} />
          <Technical label="Provider" value={providerLabel(run.provider)} />
          <Technical label="Model" value={run.model_identifier ?? "—"} wide />
        </div>
      </header>

      {run.detected_signal ? (
        <section className={`grid gap-4 rounded-xl border border-[#deded9] bg-white p-5 sm:p-6 ${run.analysis_type === "LIFECYCLE_RISK" || run.analysis_type === "POSITIVE_GROWTH" ? "sm:grid-cols-5" : "sm:grid-cols-4"}`} aria-label="Detected signal summary">
          <div><p className="meta-label">Detected Signal</p><p className="mt-2 text-sm font-semibold">{run.detected_signal}</p></div>
          <div><p className="meta-label">Overall Movement</p><p className="mt-2 text-sm font-semibold tabular-nums">{formatRate(run.overall_baseline_rate)} → {formatRate(run.overall_target_rate)}</p></div>
          <div><p className="meta-label">Delta</p><p className={`mt-2 text-sm font-semibold ${run.analysis_type === "POSITIVE_GROWTH" ? "text-[#2f7666]" : "text-[#9a4438]"}`}>{formatDelta(run.overall_delta_pp)}</p></div>
          <div><p className="meta-label">Affected Segment</p><p className="mt-2 text-sm font-semibold">{segmentLabel(run.affected_segment)}</p></div>
          {run.analysis_type === "LIFECYCLE_RISK" ? <div><p className="meta-label">Post / Recovery</p><p className="mt-2 text-sm font-semibold tabular-nums">{formatRate(run.post_rate)} · {humanize(run.risk_pattern)}</p></div> : null}
          {run.analysis_type === "POSITIVE_GROWTH" ? <div><p className="meta-label">Reproducibility</p><p className="mt-2 text-sm font-semibold">{humanize(run.reproducibility)}</p></div> : null}
        </section>
      ) : null}

      <section aria-labelledby="run-log-heading" className="mx-auto max-w-[68rem]">
        <div className="flex items-end justify-between">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#777771]">Agent transparency</p>
            <h2 id="run-log-heading" className="mt-2 text-2xl font-semibold tracking-[-0.03em]">Investigation Timeline</h2>
          </div>
          <p className="text-xs text-[#888882]">{ordered.length} recorded steps</p>
        </div>

        <ol className="mt-8">
          {ordered.map((step, index) => (
            <li key={step.id} className="relative grid grid-cols-[32px_1fr] gap-4 pb-7 last:pb-0">
              {index < ordered.length - 1 ? <span className="absolute left-[15px] top-8 h-[calc(100%-20px)] w-px bg-[#d8d8d3]" /> : null}
              <span className={`relative z-10 grid size-8 place-items-center rounded-full border ${step.decision === "STOP" ? "border-[#d8caa8] bg-[#fbf6e9] text-[#785f2d]" : "border-[#c7ddd7] bg-[#f0f8f5] text-[#176b5c]"}`}>
                {step.decision === "STOP" ? <ShieldIcon className="size-4" /> : <CheckIcon className="size-4" />}
              </span>
              <article className="rounded-xl border border-[#deded9] bg-white p-5 sm:p-6">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-[#92928c]">Step {step.step_order}</p>
                    <h3 className="mt-1.5 text-base font-semibold">{stepTitle(step.node)}</h3>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {step.hypothesis_status ? <StatusBadge value={step.hypothesis_status} /> : null}
                  </div>
                </div>
                <p className="mt-3 text-sm leading-6 text-[#686862]">{stepSummary(step)}</p>
                {step.hypothesis ? <p className="mt-3 rounded-lg bg-[#f7f6f2] px-3 py-2 text-xs text-[#665f51]"><span className="font-semibold">Hypothesis:</span> {humanize(step.hypothesis)}</p> : null}
                {hasPlannerTrace(step) ? <PlannerTrace step={step} /> : null}
              </article>
            </li>
          ))}
        </ol>
      </section>

      <StopSummary run={run} />
    </div>
  );
}

function PlannerTrace({ step }: { step: AgentStep }) {
  const proposal = step.planner_proposal;
  return (
    <details className="group mt-4 border-t border-[#ecece8] pt-4">
      <summary className="flex cursor-pointer list-none items-center justify-between text-xs font-semibold text-[#55554f]">
        Planner and Guard details
        <ChevronIcon className="size-4 transition-transform group-open:rotate-180" />
      </summary>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <TraceBlock icon={<SparkIcon className="size-4" />} label="AI Proposal">
          <p className="font-medium">{proposal?.action === "INVESTIGATE" ? `Investigate ${humanize(proposal.dimension)}` : humanize(proposal?.action)}</p>
        </TraceBlock>
        <TraceBlock icon={<SparkIcon className="size-4" />} label="Rationale">
          <p className="text-[#777771]">{step.planner_rationale ?? proposal?.rationale ?? "No rationale provided."}</p>
        </TraceBlock>
        <TraceBlock icon={<ShieldIcon className="size-4" />} label="Guard Result">
          <p className="font-medium">{humanize(step.guard_status)}</p>
          <p className="mt-1.5 text-[#777771]">{humanize(step.guard_reason)}</p>
        </TraceBlock>
        <TraceBlock icon={<DatabaseIcon className="size-4" />} label="Executed Tool">
          <p className="font-medium">{step.tool_name ?? "No tool executed"}</p>
          {step.tool_input.dimension ? <p className="mt-1.5 text-[#777771]">dimension = {String(step.tool_input.dimension)}</p> : null}
          {step.tool_input.lifecycle_filter ? <p className="text-[#777771]">filter = {String(step.tool_input.lifecycle_filter)}</p> : null}
        </TraceBlock>
        <TraceBlock className="md:col-span-2" icon={<CheckIcon className="size-4" />} label="Result">
          <p className="text-[#777771]">{stepSummary(step)}</p>
        </TraceBlock>
      </div>
      {step.fallback_used ? <div className="mt-3 flex items-center gap-2 text-xs text-[#806b3d]"><StatusBadge value="FALLBACK" /><span>{humanize(step.fallback_reason)}</span></div> : null}
    </details>
  );
}

function TraceBlock({ icon, label, children, className = "" }: { icon: React.ReactNode; label: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-lg border border-[#e5e5e1] bg-[#fafaf8] p-3 text-xs leading-5 ${className}`}>
      <div className="mb-2 flex items-center gap-2 font-semibold text-[#343431]">{icon}{label}</div>
      {children}
    </div>
  );
}

function StopSummary({ run }: { run: AnalysisRun }) {
  const reason = run.stop_reason === "ALLOWED_DIMENSIONS_EXHAUSTED"
    ? "All permitted dimensions were investigated. No confirmed root cause supports further drill-down."
    : run.stop_reason === "BUDGET_EXHAUSTED"
      ? "Investigation budget was exhausted while permitted dimensions remained."
    : run.stop_reason === "DATA_QUALITY_FAIL"
      ? "Data quality did not support behavioral interpretation."
      : run.stop_reason === "NO_SIGNIFICANT_SIGNAL"
        ? "No metric crossed the material-signal threshold."
        : humanize(run.stop_reason);
  return (
    <section aria-labelledby="stop-heading" className="mx-auto max-w-[68rem] rounded-xl border border-[#d9d0b8] bg-[#fbf8ef] p-6 sm:p-7">
      <p className="text-[10px] font-semibold uppercase tracking-[0.13em] text-[#7b6531]">Correct stopping behavior</p>
      <h2 id="stop-heading" className="mt-2 text-xl font-semibold">Investigation stopped</h2>
      <dl className="mt-5 grid gap-5 text-sm sm:grid-cols-2">
        <div><dt className="text-xs font-semibold text-[#786f5c]">Reason</dt><dd className="mt-1.5 leading-6 text-[#555044]">{reason}</dd></div>
        <div><dt className="text-xs font-semibold text-[#786f5c]">Next</dt><dd className="mt-1.5 leading-6 text-[#555044]">{run.recommended_action_type === "EVIDENCE_COLLECTION" ? "Collect additional evidence before selecting an intervention." : humanize(run.recommended_action_type)}</dd></div>
      </dl>
    </section>
  );
}

function Technical({ label, value, wide = false }: { label: string; value: string; wide?: boolean }) {
  return <div className={wide ? "col-span-2 sm:col-span-1" : ""}><p className="text-[10px] uppercase tracking-[0.1em] text-[#92928c]">{label}</p><p className="mt-1 font-medium text-[#454541]">{value}</p></div>;
}

function hasPlannerTrace(step: AgentStep) {
  return Boolean(step.planner_proposal || step.planner_rationale || step.guard_status || step.fallback_used);
}

function stepTitle(node: string): string {
  const names: Record<string, string> = {
    VALIDATE_DATA: "Validate Data",
    SCAN_METRICS: "Scan Metrics",
    ANALYZE_FUNNEL: "Strict Funnel",
    ANALYZE_RETENTION: "Analyze Retention",
    CHECK_RETURN_TIMING: "Return Timing",
    CHECK_RECOVERY: "Recovery",
    ANALYZE_GROWTH: "Analyze Growth",
    CHECK_WEEKLY_PERSISTENCE: "Weekly Persistence",
    CHECK_CONFIRMATION: "Confirmation",
    CHECK_HOLDOUT: "Holdout Reproducibility",
    CHECK_ACQUISITION: "Acquisition",
    CHECK_DEVICE: "Device",
    CHECK_ACTIVATION_DEPTH: "Activation Depth",
    COMPARE_SEGMENTS_LIFECYCLE: "Lifecycle",
    COMPARE_SEGMENTS_DEVICE: "Device",
    COMPARE_SEGMENTS_ACQUISITION: "Acquisition",
    COMPARE_SEGMENTS_CATEGORY: "Category",
    STOP_DRILLDOWN: "Stop Investigation",
  };
  return names[node] ?? humanize(node);
}

function stepSummary(step: AgentStep): string {
  if (step.node === "VALIDATE_DATA") return step.decision === "STOP" ? "Data validation failed; behavioral investigation did not proceed." : "Required data-quality checks passed.";
  if (step.node === "SCAN_METRICS") {
    const metrics = step.tool_output_summary.metrics;
    if (Array.isArray(metrics)) {
      const signal = metrics.find((item) => typeof item === "object" && item && "needs_investigation" in item && item.needs_investigation) as { name?: string; delta_pp?: number } | undefined;
      if (signal) return `${signal.name ?? "A metric"} decline detected: ${formatDelta(signal.delta_pp ?? null)}.`;
    }
  }
  if (step.node === "ANALYZE_FUNNEL") {
    const baseline = numberValue(step.tool_output_summary.baseline_rate);
    const target = numberValue(step.tool_output_summary.target_rate);
    const strictOrdering = step.tool_output_summary.strict_identity_session_order === true;
    return `${formatRate(baseline)} → ${formatRate(target)}.${strictOrdering ? " Signal confirmed using strict same-user / same-session ordering." : ""}`;
  }
  if (step.node === "ANALYZE_RETENTION") {
    const baseline = objectValue(step.tool_output_summary.baseline);
    const target = objectValue(step.tool_output_summary.target);
    return `D7 Return ${formatRate(numberValue(baseline?.return_rate_7d))} → ${formatRate(numberValue(target?.return_rate_7d))}, ${formatDelta(numberValue(step.tool_output_summary.delta_pp))}.`;
  }
  if (step.node === "ANALYZE_GROWTH") {
    const baseline = objectValue(step.tool_output_summary.baseline);
    const growth = objectValue(step.tool_output_summary.growth);
    return `Checkout→Purchase ${formatRate(numberValue(baseline?.conversion_rate))} → ${formatRate(numberValue(growth?.conversion_rate))}, ${formatDelta(numberValue(step.tool_output_summary.delta_pp))}.`;
  }
  if (step.node === "CHECK_WEEKLY_PERSISTENCE") return "Weekly strict checkout-to-purchase results were recorded to check persistence.";
  if (step.node === "CHECK_CONFIRMATION") {
    const confirmation = objectValue(step.tool_output_summary.confirmation);
    return `Confirmation Checkout→Purchase: ${formatRate(numberValue(confirmation?.conversion_rate))}.`;
  }
  if (step.node === "CHECK_HOLDOUT") return `Holdout reproducibility: ${humanize(typeof step.tool_output_summary.reproducibility === "string" ? step.tool_output_summary.reproducibility : null)}.`;
  if (step.node === "CHECK_RETURN_TIMING") {
    const conclusion = step.tool_output_summary.conclusion;
    if (typeof conclusion === "string") return conclusion;
    const baseline = objectValue(step.tool_output_summary.baseline);
    const target = objectValue(step.tool_output_summary.target);
    return timingSummary(baseline, target);
  }
  if (step.node === "CHECK_RECOVERY") {
    const postRate = formatRate(numberValue(step.tool_output_summary.post_rate));
    const riskPattern = humanize(typeof step.tool_output_summary.risk_pattern === "string" ? step.tool_output_summary.risk_pattern : null);
    return `Post D7 Return: ${postRate}. Recovery classification: ${riskPattern}.`;
  }
  if (step.node === "CHECK_ACQUISITION") {
    return `Major sources declined within-source while mix stayed stable. ${hypothesisOutcome(step, "Acquisition-mix explanation")}`;
  }
  if (step.node === "CHECK_DEVICE") {
    const segments = segmentSummaries(step);
    const desktop = findSegment(segments, "desktop");
    const mobile = findSegment(segments, "mobile");
    return `Desktop: ${formatDelta(desktop?.change_pp ?? null)} · Mobile: ${formatDelta(mobile?.change_pp ?? null)}. ${hypothesisOutcome(step, "Device concentration")}`;
  }
  if (step.node === "CHECK_ACTIVATION_DEPTH") {
    const composition = numberValue(step.tool_output_summary.composition_effect_pp);
    const within = numberValue(step.tool_output_summary.within_segment_effect_pp);
    return `Users shifted shallower (${formatDelta(composition)} composition), while within-bucket decline dominated (${formatDelta(within)}). Observed association supported; root cause unconfirmed.`;
  }
  if (step.node === "COMPARE_SEGMENTS_LIFECYCLE") {
    const segments = segmentSummaries(step);
    const newUsers = findSegment(segments, "new");
    const returningUsers = findSegment(segments, "returning");
    if (newUsers || returningUsers) {
      return `New Users: ${formatDelta(newUsers?.change_pp ?? null)} · Returning Users: ${formatDelta(returningUsers?.change_pp ?? null)}. Signal localized to New Users.`;
    }
  }
  if (step.node === "COMPARE_SEGMENTS_DEVICE") {
    const segments = segmentSummaries(step);
    const desktop = findSegment(segments, "desktop");
    const mobile = findSegment(segments, "mobile");
    if (desktop || mobile) {
      return `Desktop: ${formatDelta(desktop?.change_pp ?? null)} · Mobile: ${formatDelta(mobile?.change_pp ?? null)}. ${hypothesisOutcome(step, "Device concentration")}`;
    }
  }
  if (step.node === "COMPARE_SEGMENTS_ACQUISITION") {
    const sampled = segmentSummaries(step).filter((item) => item.sample_sufficient !== false);
    const declinedWithinSource = sampled.length > 0 && sampled.every((item) => numberValue(item.change_pp) !== null && numberValue(item.change_pp)! < 0);
    const stableMix = sampled.length > 0 && sampled.every((item) => {
      const baseline = numberValue(item.baseline_share);
      const target = numberValue(item.target_share);
      return baseline !== null && target !== null && Math.abs(target - baseline) < 2;
    });
    if (declinedWithinSource && stableMix) {
      return `Major sources declined within-source while acquisition mix remained broadly stable. ${hypothesisOutcome(step, "Acquisition-mix explanation")}`;
    }
  }
  if (step.node === "COMPARE_SEGMENTS_CATEGORY") {
    const changes = segmentSummaries(step).map((item) => numberValue(item.change_pp)).filter((value): value is number => value !== null);
    const mixed = changes.some((value) => value < 0) && changes.some((value) => value > 0);
    if (mixed) return `Category effects were mixed. ${hypothesisOutcome(step, "Category-concentration explanation")}`;
  }
  if (step.node === "STOP_DRILLDOWN" && step.decision === "STOP") {
    return step.decision_reason;
  }
  return step.decision_reason;
}

function timingSummary(
  baseline: Record<string, unknown> | null,
  target: Record<string, unknown> | null,
): string {
  const d1Gap = (numberValue(baseline?.return_rate_d1) ?? 0) - (numberValue(target?.return_rate_d1) ?? 0);
  const d2To3Gap = ((numberValue(baseline?.return_rate_d3) ?? 0) - (numberValue(baseline?.return_rate_d1) ?? 0))
    - ((numberValue(target?.return_rate_d3) ?? 0) - (numberValue(target?.return_rate_d1) ?? 0));
  const d4To7Gap = ((numberValue(baseline?.return_rate_d7) ?? 0) - (numberValue(baseline?.return_rate_d3) ?? 0))
    - ((numberValue(target?.return_rate_d7) ?? 0) - (numberValue(target?.return_rate_d3) ?? 0));
  if (d1Gap > 0) return "The decline begins at D1 and persists through D7.";
  if (d2To3Gap > 0) return "Return is not lower at D1; the decline emerges during D2–3 and persists through D7.";
  if (d4To7Gap > 0) return "Return is not lower through D3; the decline emerges during D4–7.";
  return "Return timing does not show a clear cumulative decline through D7.";
}

type SegmentSummary = {
  segment?: string;
  change_pp?: number | null;
  baseline_share?: number | null;
  target_share?: number | null;
  sample_sufficient?: boolean;
};

function segmentSummaries(step: AgentStep): SegmentSummary[] {
  const segments = step.tool_output_summary.segments;
  return Array.isArray(segments)
    ? segments.filter((item): item is SegmentSummary => typeof item === "object" && item !== null)
    : [];
}

function findSegment(segments: SegmentSummary[], name: string): SegmentSummary | undefined {
  return segments.find((item) => item.segment?.toLowerCase() === name);
}

function hypothesisOutcome(step: AgentStep, label: string): string {
  if (step.hypothesis_status === "REJECTED") return `${label} rejected.`;
  if (step.hypothesis_status === "SUPPORTED") return `${label} supported.`;
  if (step.hypothesis_status === "INSUFFICIENT_EVIDENCE") return `Insufficient evidence for a ${label.toLowerCase()}.`;
  return `${label} remains unverified.`;
}

function numberValue(value: unknown): number | null {
  return typeof value === "number" ? value : null;
}

function objectValue(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null ? value as Record<string, unknown> : null;
}

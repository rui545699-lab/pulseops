"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ArrowRightIcon, CheckIcon, ShieldIcon } from "@/components/icons";
import { MetricScope } from "@/components/metric-scope";
import { ErrorState, PageLoading } from "@/components/states";
import { StatusBadge } from "@/components/status-badge";
import { loadOpportunityDetail } from "@/lib/api";
import { formatDelta, humanize, opportunityTitle, segmentLabel } from "@/lib/format";
import type { AnalysisRun, Opportunity } from "@/lib/types";

export interface OpportunityDetailData {
  opportunity: Opportunity;
  run: AnalysisRun;
}

export function OpportunityDetailClient({
  opportunityId,
  loader = loadOpportunityDetail,
}: {
  opportunityId: string;
  loader?: (id: string) => Promise<OpportunityDetailData>;
}) {
  const [data, setData] = useState<OpportunityDetailData | null>(null);
  const [error, setError] = useState<string | null>(null);
  async function retry() {
    setError(null);
    try {
      setData(await loader(opportunityId));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The opportunity could not be loaded.");
    }
  }

  useEffect(() => {
    let active = true;
    void loader(opportunityId).then(
      (value) => active && setData(value),
      (reason: unknown) => active && setError(reason instanceof Error ? reason.message : "The opportunity could not be loaded."),
    );
    return () => {
      active = false;
    };
  }, [loader, opportunityId]);

  if (error) return <ErrorState message={error} retry={() => void retry()} />;
  if (!data) return <PageLoading label="Loading opportunity detail" />;
  return <OpportunityDetailView {...data} />;
}

export function OpportunityDetailView({ opportunity, run }: OpportunityDetailData) {
  const lifecycle = opportunity.opportunity_type === "LIFECYCLE_RISK";
  const positiveGrowth = opportunity.opportunity_type === "POSITIVE_GROWTH";
  return (
    <div className="space-y-10">
      <nav aria-label="Breadcrumb" className="text-xs text-[#85857f]">
        <Link href="/" className="hover:text-[#222220]">Overview</Link>
        <span className="mx-2">/</span>
        <span>Opportunity</span>
      </nav>

      <header className="grid gap-8 border-b border-[#dfdfda] pb-10 lg:grid-cols-[1fr_auto] lg:items-end">
        <div>
          <div className="flex flex-wrap items-center gap-2.5">
            <StatusBadge value={opportunity.status} />
            <StatusBadge value={opportunity.opportunity_type} label={opportunityTypeLabel(opportunity.opportunity_type)} />
            <span className="text-xs text-[#7e7e78]">Affected segment · {segmentLabel(opportunity.affected_segment)}</span>
          </div>
          <h1 className="mt-5 max-w-3xl text-3xl font-semibold tracking-[-0.04em] sm:text-5xl">
            {lifecycle || positiveGrowth ? opportunity.title : opportunityTitle(opportunity.metric, opportunity.affected_segment)}
          </h1>
          <p className="mt-4 max-w-2xl text-sm leading-6 text-[#6c6c66]">
            {lifecycle
              ? "A material new-user return risk partially recovered in the Post period. The signal is strong; the causal mechanism remains unconfirmed."
              : positiveGrowth
                ? "A statistically supported Checkout→Purchase lift persisted through confirmation and holdouts. The lift is validated; its mechanism remains unproven."
              : "A material conversion decline is localized to this segment. The behavioral signal is strong; the causal mechanism remains unconfirmed."}
          </p>
        </div>
        <Link href={`/runs/${run.id}`} className="inline-flex items-center gap-2 text-sm font-semibold text-[#2f655a] hover:text-[#194d43]">
          View investigation run <ArrowRightIcon className="size-4" />
        </Link>
      </header>

      <section aria-label="Metric scope comparison" className="grid gap-4 lg:grid-cols-[1.25fr_0.75fr]">
        <MetricScope eyebrow={`${positiveGrowth ? "Validated growth signal" : lifecycle ? "Metric summary" : "Localized opportunity"} · ${segmentLabel(opportunity.affected_segment)}`} baseline={opportunity.baseline_rate} target={opportunity.target_rate} delta={opportunity.delta_pp} emphasized />
        {lifecycle ? (
          <div className="rounded-xl border border-[#e1e1dc] bg-[#f1f1ee] p-5 sm:p-6">
            <p className="meta-label">Affected Population</p>
            <p className="mt-3 text-xl font-semibold">New users</p>
            <p className="mt-2 text-sm text-[#686862]">{run.target_start} – {run.target_end}</p>
            <p className="mt-4 border-t border-[#deded8] pt-4 text-xs leading-5 text-[#777771]">
              {opportunity.return_timing?.target.eligible_new_users.toLocaleString() ?? "—"} eligible users with a complete seven-day observation window.
            </p>
          </div>
        ) : positiveGrowth ? (
          <div className="rounded-xl border border-[#d7e2de] bg-[#f4f8f7] p-5 sm:p-6">
            <p className="meta-label">Replication Boundary</p>
            <p className="mt-3 text-xl font-semibold">Validated lift ≠ proven growth mechanism</p>
            <p className="mt-2 text-sm text-[#686862]">Run a bounded replication test before any broad rollout.</p>
            <p className="mt-4 border-t border-[#d8e4e0] pt-4 text-xs leading-5 text-[#61716d]">Localization · {opportunity.growth_localization ? humanize(opportunity.growth_localization) : "Unknown"}</p>
          </div>
        ) : (
          <div className="rounded-xl border border-[#e1e1dc] bg-[#f1f1ee] p-5 sm:p-6">
            <MetricScope eyebrow={`Overall detected signal · ${run.detected_signal ?? opportunity.metric}`} baseline={run.overall_baseline_rate} target={run.overall_target_rate} delta={run.overall_delta_pp} />
            <p className="mt-4 border-t border-[#deded8] pt-4 text-xs leading-5 text-[#777771]">Overall strict-session movement triggered the investigation. Localized rates describe the affected segment above.</p>
          </div>
        )}
      </section>

      {lifecycle ? <LifecycleRecovery opportunity={opportunity} /> : null}
      {lifecycle && opportunity.return_timing ? <ReturnTiming timing={opportunity.return_timing} /> : null}
      {positiveGrowth ? <GrowthPersistence opportunity={opportunity} run={run} /> : null}

      <section aria-labelledby="confidence-heading" className={`grid gap-5 rounded-xl border border-[#deded9] bg-white p-5 sm:items-center sm:p-6 ${positiveGrowth ? "sm:grid-cols-[1fr_auto_auto_auto]" : "sm:grid-cols-[1fr_auto_auto]"}`}>
        <div>
          <h2 id="confidence-heading" className="text-sm font-semibold">Confidence</h2>
          <p className="mt-1.5 text-sm leading-6 text-[#70706a]">{positiveGrowth ? "Growth and reproducibility are measured deterministically. Specific mechanism is not established." : "Signal is well supported by behavior data. Specific cause is not yet established."}</p>
        </div>
        <Confidence label={positiveGrowth ? "Growth Signal Confidence" : "Signal Confidence"} value={positiveGrowth ? (opportunity.growth_signal_confidence ?? opportunity.signal_confidence) : opportunity.signal_confidence} />
        {positiveGrowth ? <Confidence label="Reproducibility Confidence" value={opportunity.reproducibility_confidence ?? "LOW"} /> : null}
        <Confidence label="Root-cause Confidence" value={opportunity.root_cause_confidence} />
      </section>

      <section className="grid gap-5 lg:grid-cols-12" aria-label="Evidence discipline">
        <EvidencePanel items={opportunity.evidence} />
        <HypothesisPanel items={opportunity.hypotheses} />
        <UnknownPanel items={opportunity.unknowns} />
      </section>

      <section aria-labelledby="recommended-action-heading" className="overflow-hidden rounded-2xl border border-[#d8d8d2] bg-white">
        <div className="grid lg:grid-cols-[1.25fr_0.75fr]">
          <div className="p-6 sm:p-8">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#2c7668]">Recommended Action</p>
            <h2 id="recommended-action-heading" className="mt-3 text-2xl font-semibold tracking-[-0.03em]">{humanize(opportunity.recommended_action_type)}</h2>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-[#5f5f59]">{opportunity.recommended_next_action}</p>
          </div>
          <div className="border-t border-[#e4e4df] bg-[#f6f3ee] p-6 sm:p-8 lg:border-l lg:border-t-0">
            <div className="flex items-center gap-2">
              <ShieldIcon className="size-4 text-[#755f3a]" />
              <h3 className="text-sm font-semibold">Do not recommend yet</h3>
            </div>
            <ul className="mt-4 space-y-3 text-sm leading-6 text-[#69635a]">
              {opportunity.do_not_recommend_yet.map((item) => <li key={item} className="border-l-2 border-[#d8caaa] pl-3">{item}</li>)}
            </ul>
          </div>
        </div>
      </section>
    </div>
  );
}

function opportunityTypeLabel(type: string): string {
  if (type === "LIFECYCLE_RISK") return "Lifecycle Risk";
  if (type === "POSITIVE_GROWTH") return "Positive Growth";
  return "Conversion / Activation";
}

function LifecycleRecovery({ opportunity }: { opportunity: Opportunity }) {
  const recoveryLabel = humanize(opportunity.risk_pattern ?? "RECOVERY_ANALYSIS");
  return (
    <section aria-labelledby="recovery-heading" className="rounded-xl border border-[#d7e2de] bg-[#f4f8f7] p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><p className="meta-label">Recovery</p><h2 id="recovery-heading" className="mt-2 text-xl font-semibold">{recoveryLabel} relative to Baseline</h2></div>
        {opportunity.risk_pattern ? <StatusBadge value={opportunity.risk_pattern} /> : null}
      </div>
      <dl className="mt-6 grid gap-5 sm:grid-cols-3">
        <div><dt className="meta-label">Target</dt><dd className="mt-2 text-2xl font-semibold tabular-nums">{opportunity.target_rate.toFixed(2)}%</dd></div>
        <div><dt className="meta-label">Post</dt><dd className="mt-2 text-2xl font-semibold tabular-nums">{opportunity.post_rate?.toFixed(2)}%</dd></div>
        <div><dt className="meta-label">Lost rate recovered</dt><dd className="mt-2 text-2xl font-semibold tabular-nums">{opportunity.recovery_ratio?.toFixed(2)}%</dd></div>
      </dl>
      <p className="mt-5 text-xs leading-5 text-[#61716d]">Target → Post {formatDelta(opportunity.target_to_post_delta_pp ?? null)} · Baseline → Post {formatDelta(opportunity.baseline_to_post_delta_pp ?? null)}. Calendar timing remains a hypothesis, not a proven cause.</p>
    </section>
  );
}

function GrowthPersistence({ opportunity, run }: { opportunity: Opportunity; run: AnalysisRun }) {
  const periods = [
    ["Baseline", opportunity.baseline_period ?? run.growth_analysis?.baseline ?? null],
    ["Growth", opportunity.growth_period],
    ["Confirmation", opportunity.confirmation_period],
    ["Holdout 1", opportunity.holdout_results?.holdout_1],
    ["Holdout 2", opportunity.holdout_results?.holdout_2],
  ] as const;
  return (
    <section aria-labelledby="growth-persistence-heading" className="rounded-xl border border-[#d7e2de] bg-[#f4f8f7] p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><p className="meta-label">Persistence evidence</p><h2 id="growth-persistence-heading" className="mt-2 text-xl font-semibold">Growth confirmation and holdouts</h2></div>
        {opportunity.reproducibility ? <StatusBadge value={opportunity.reproducibility} /> : null}
      </div>
      <dl className="mt-6 grid gap-4 sm:grid-cols-5">
        {periods.map(([label, period]) => <div key={label} className="rounded-lg border border-[#dce7e3] bg-white p-4"><dt className="meta-label">{label}</dt><dd className="mt-2 text-xl font-semibold tabular-nums">{period ? `${period.conversion_rate.toFixed(2)}%` : "—"}</dd><p className="mt-1 text-xs text-[#71716b]">{period ? `${period.purchase_after_checkout_sessions.toLocaleString()} / ${period.checkout_sessions.toLocaleString()} sessions` : "Unavailable"}</p></div>)}
      </dl>
      <p className="mt-5 text-xs leading-5 text-[#61716d]">Reproducibility is deterministic evidence of persistence, not causal proof. {opportunity.order_value_context ? `AOV context: ${opportunity.order_value_context.baseline_average_order_value_usd.toFixed(2)} → ${opportunity.order_value_context.growth_average_order_value_usd.toFixed(2)} USD.` : ""}</p>
    </section>
  );
}

function ReturnTiming({ timing }: { timing: NonNullable<Opportunity["return_timing"]> }) {
  const periods = [
    ["Baseline", timing.baseline],
    ["Target", timing.target],
    ["Post", timing.post],
  ] as const;
  return (
    <section aria-labelledby="return-timing-heading" className="rounded-xl border border-[#deded9] bg-white p-5 sm:p-6">
      <p className="meta-label">Timing evidence</p>
      <h2 id="return-timing-heading" className="mt-2 text-xl font-semibold">Return Timing</h2>
      <div className="mt-5 overflow-x-auto">
        <table className="w-full min-w-[34rem] text-left text-sm">
          <thead className="text-xs text-[#777771]"><tr><th className="pb-3">Period</th><th className="pb-3">D1</th><th className="pb-3">D1–3</th><th className="pb-3">D1–7</th></tr></thead>
          <tbody className="divide-y divide-[#ecece8]">
            {periods.map(([label, period]) => <tr key={label}><th className="py-3 font-medium">{label}</th><td className="py-3 tabular-nums">{period.return_rate_d1.toFixed(2)}%</td><td className="py-3 tabular-nums">{period.return_rate_d3.toFixed(2)}%</td><td className="py-3 tabular-nums">{period.return_rate_d7.toFixed(2)}%</td></tr>)}
          </tbody>
        </table>
      </div>
      <p className="mt-5 text-xs leading-5 text-[#777771]">Observed decline contribution: D1 {timing.d1_decline_contribution_pct.toFixed(2)}% · D2–3 {timing.d2_3_decline_contribution_pct.toFixed(2)}% · D4–7 {timing.d4_7_decline_contribution_pct.toFixed(2)}%. Timing is evidence, not causal proof.</p>
    </section>
  );
}

function Confidence({ label, value }: { label: string; value: string }) {
  return (
    <div className="sm:border-l sm:border-[#e8e8e4] sm:pl-6">
      <p className="text-[10px] font-medium uppercase tracking-[0.1em] text-[#888882]">{label}</p>
      <div className="mt-2"><StatusBadge value={value} /></div>
    </div>
  );
}

function EvidencePanel({ items }: { items: string[] }) {
  return (
    <article className="rounded-xl border border-[#cbded8] bg-[#f2f8f6] p-5 sm:p-6 lg:col-span-5">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold tracking-[-0.02em]">Evidence</h2>
        <StatusBadge value="ACCEPTED" label="Confirmed" />
      </div>
      <p className="mt-2 text-xs text-[#59736d]">Observed directly in bounded analytics.</p>
      <ul className="mt-5 space-y-3">
        {items.map((item) => <li key={item} className="flex gap-3 text-sm leading-6 text-[#38564f]"><span className="mt-1 grid size-4 shrink-0 place-items-center rounded-full bg-[#d2e9e3]"><CheckIcon className="size-2.5" /></span>{item}</li>)}
      </ul>
    </article>
  );
}

function HypothesisPanel({ items }: { items: string[] }) {
  return (
    <article className="rounded-xl border border-dashed border-[#d8cba9] bg-[#fcfaf4] p-5 sm:p-6 lg:col-span-4">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold tracking-[-0.02em]">Hypotheses</h2>
        <span className="rounded-full border border-[#e1d6ba] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.08em] text-[#7b6738]">Unverified</span>
      </div>
      <p className="mt-2 text-xs text-[#7b735f]">Plausible explanations—not established facts.</p>
      <ul className="mt-5 space-y-3 text-sm leading-6 text-[#5e594d]">
        {items.map((item) => <li key={item} className="border-l border-[#d8cba9] pl-3">{item}</li>)}
      </ul>
    </article>
  );
}

function UnknownPanel({ items }: { items: string[] }) {
  return (
    <article className="rounded-xl border border-[#ddddda] bg-white p-5 sm:p-6 lg:col-span-3">
      <h2 className="text-lg font-semibold tracking-[-0.02em]">Unknowns</h2>
      <p className="mt-2 text-xs leading-5 text-[#777771]">The agent knows what it does not know.</p>
      <ul className="mt-5 space-y-3 text-sm leading-5 text-[#64645e]">
        {items.map((item) => <li key={item} className="flex gap-2"><span className="mt-2 size-1 shrink-0 rounded-full bg-[#aaa9a3]" />{item}</li>)}
      </ul>
    </article>
  );
}

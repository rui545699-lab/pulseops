"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ArrowRightIcon, CheckIcon, ShieldIcon } from "@/components/icons";
import { MetricScope } from "@/components/metric-scope";
import { ErrorState, PageLoading } from "@/components/states";
import { StatusBadge } from "@/components/status-badge";
import { loadOpportunityDetail } from "@/lib/api";
import { humanize, opportunityTitle, segmentLabel } from "@/lib/format";
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
            <span className="text-xs text-[#7e7e78]">Affected segment · {segmentLabel(opportunity.affected_segment)}</span>
          </div>
          <h1 className="mt-5 max-w-3xl text-3xl font-semibold tracking-[-0.04em] sm:text-5xl">
            {opportunityTitle(opportunity.metric, opportunity.affected_segment)}
          </h1>
          <p className="mt-4 max-w-2xl text-sm leading-6 text-[#6c6c66]">
            A material conversion decline is localized to this segment. The behavioral signal is strong; the causal mechanism remains unconfirmed.
          </p>
        </div>
        <Link href={`/runs/${run.id}`} className="inline-flex items-center gap-2 text-sm font-semibold text-[#2f655a] hover:text-[#194d43]">
          View investigation run <ArrowRightIcon className="size-4" />
        </Link>
      </header>

      <section aria-label="Metric scope comparison" className="grid gap-4 lg:grid-cols-[1.25fr_0.75fr]">
        <MetricScope eyebrow={`Localized opportunity · ${segmentLabel(opportunity.affected_segment)}`} baseline={opportunity.baseline_rate} target={opportunity.target_rate} delta={opportunity.delta_pp} emphasized />
        <div className="rounded-xl border border-[#e1e1dc] bg-[#f1f1ee] p-5 sm:p-6">
          <MetricScope eyebrow={`Overall detected signal · ${run.detected_signal ?? opportunity.metric}`} baseline={run.overall_baseline_rate} target={run.overall_target_rate} delta={run.overall_delta_pp} />
          <p className="mt-4 border-t border-[#deded8] pt-4 text-xs leading-5 text-[#777771]">
            Overall strict-session movement triggered the investigation. Localized rates describe the affected segment above.
          </p>
        </div>
      </section>

      <section aria-labelledby="confidence-heading" className="grid gap-5 rounded-xl border border-[#deded9] bg-white p-5 sm:grid-cols-[1fr_auto_auto] sm:items-center sm:p-6">
        <div>
          <h2 id="confidence-heading" className="text-sm font-semibold">Confidence</h2>
          <p className="mt-1.5 text-sm leading-6 text-[#70706a]">Signal is well supported by behavior data. Specific cause is not yet established.</p>
        </div>
        <Confidence label="Signal Confidence" value={opportunity.signal_confidence} />
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

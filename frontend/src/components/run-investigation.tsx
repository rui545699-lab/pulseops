"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { AlertIcon, PlusIcon, SparkIcon } from "@/components/icons";
import { api } from "@/lib/api";
import { humanize } from "@/lib/format";
import type { AnalysisRun, Opportunity, RunRequest } from "@/lib/types";

type ResultState =
  | { kind: "idle" }
  | { kind: "data-quality"; run: AnalysisRun }
  | { kind: "no-signal"; run: AnalysisRun }
  | { kind: "error"; message: string };

export function RunInvestigation({
  createRun = api.createRun,
  listOpportunities = api.listOpportunities,
  onNavigate,
}: {
  createRun?: (payload: RunRequest) => Promise<AnalysisRun>;
  listOpportunities?: () => Promise<Opportunity[]>;
  onNavigate?: (path: string) => void;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [running, setRunning] = useState(false);
  const [analysisType, setAnalysisType] = useState<RunRequest["analysis_type"]>("CONVERSION");
  const [result, setResult] = useState<ResultState>({ kind: "idle" });

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setRunning(true);
    setResult({ kind: "idle" });
    const form = new FormData(event.currentTarget);
    const payload: RunRequest = {
      analysis_type: String(form.get("analysis_type")) as RunRequest["analysis_type"],
      baseline_start: String(form.get("baseline_start")),
      baseline_end: String(form.get("baseline_end")),
      target_start: String(form.get("target_start")),
      target_end: String(form.get("target_end")),
      planner_mode: String(form.get("planner_mode")) as RunRequest["planner_mode"],
      ...(analysisType === "LIFECYCLE_RISK"
        ? {
            post_start: String(form.get("post_start")),
            post_end: String(form.get("post_end")),
          }
        : {}),
    };

    try {
      const run = await createRun(payload);
      if (run.recommended_status === "DATA_QUALITY_ALERT") {
        setResult({ kind: "data-quality", run });
        return;
      }
      if (run.recommended_status === "NO_OPPORTUNITY") {
        setResult({ kind: "no-signal", run });
        return;
      }
      const opportunities = await listOpportunities();
      const opportunity = opportunities.find((item) => item.run_id === run.id);
      const destination = opportunity
        ? `/opportunities/${opportunity.id}`
        : `/runs/${run.id}`;
      (onNavigate ?? router.push)(destination);
    } catch (error) {
      setResult({
        kind: "error",
        message: error instanceof Error ? error.message : "The investigation could not be started.",
      });
    } finally {
      setRunning(false);
    }
  }

  return (
    <section aria-labelledby="run-investigation-heading" className="rounded-2xl border border-[#deded9] bg-[#1d1d1b] text-white shadow-[0_18px_60px_rgba(0,0,0,0.08)]">
      <div className="flex flex-col gap-5 px-6 py-5 sm:flex-row sm:items-center sm:justify-between sm:px-7">
        <div>
          <div className="flex items-center gap-2 text-[#a9d8cf]">
            <SparkIcon className="size-4" />
            <span className="text-[10px] font-semibold uppercase tracking-[0.14em]">Bounded analysis</span>
          </div>
          <h2 id="run-investigation-heading" className="mt-2 text-xl font-semibold tracking-[-0.025em]">Run Investigation</h2>
          <p className="mt-1 max-w-xl text-sm leading-5 text-[#b9b9b3]">
            Compare two periods and let the agent identify, localize, and safely stop on a material signal.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          className="inline-flex shrink-0 items-center justify-center gap-2 rounded-lg bg-white px-4 py-2.5 text-sm font-semibold text-[#1d1d1b] transition-colors hover:bg-[#efefec]"
          aria-expanded={open}
        >
          <PlusIcon className={`size-4 transition-transform ${open ? "rotate-45" : ""}`} />
          {open ? "Close" : "New investigation"}
        </button>
      </div>

      {open ? (
        <form onSubmit={handleSubmit} className="border-t border-white/10 px-6 py-5 sm:px-7">
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <label className="space-y-2 text-xs font-medium text-[#d2d2cc]">
              <span>Analysis Type</span>
              <select
                name="analysis_type"
                value={analysisType}
                onChange={(event) => setAnalysisType(event.target.value as RunRequest["analysis_type"])}
                className="h-11 w-full rounded-lg border border-white/15 bg-[#292927] px-3 text-sm text-white outline-none focus:border-[#68ad9f]"
              >
                <option value="CONVERSION">Conversion / Activation</option>
                <option value="LIFECYCLE_RISK">Lifecycle Risk</option>
              </select>
            </label>
            <DateField name="baseline_start" label="Baseline Start" />
            <DateField name="baseline_end" label="Baseline End" />
            <DateField name="target_start" label="Target Start" />
            <DateField name="target_end" label="Target End" />
            {analysisType === "LIFECYCLE_RISK" ? (
              <>
                <DateField name="post_start" label="Post Start" />
                <DateField name="post_end" label="Post End" />
              </>
            ) : null}
            <label className="space-y-2 text-xs font-medium text-[#d2d2cc]">
              <span>Planner Mode</span>
              <select name="planner_mode" defaultValue="deterministic" className="h-11 w-full rounded-lg border border-white/15 bg-[#292927] px-3 text-sm text-white outline-none focus:border-[#68ad9f]">
                <option value="deterministic">Deterministic</option>
                <option value="deepseek">AI Planner</option>
              </select>
            </label>
          </div>
          <div className="mt-5 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-xs text-[#92928d]">AI proposals remain subject to the same policy guard and analytics tools.</p>
            <button disabled={running} type="submit" className="inline-flex min-w-40 items-center justify-center rounded-lg bg-[#47a18e] px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-[#398a79] disabled:cursor-wait disabled:opacity-70">
              {running ? "Running investigation…" : "Run investigation"}
            </button>
          </div>
          {result.kind !== "idle" ? <InvestigationResult result={result} /> : null}
        </form>
      ) : null}
    </section>
  );
}

function DateField({ name, label }: { name: string; label: string }) {
  return (
    <label className="space-y-2 text-xs font-medium text-[#d2d2cc]">
      <span>{label}</span>
      <input required type="date" name={name} className="h-11 w-full rounded-lg border border-white/15 bg-[#292927] px-3 text-sm text-white outline-none [color-scheme:dark] focus:border-[#68ad9f]" />
    </label>
  );
}

function InvestigationResult({ result }: { result: Exclude<ResultState, { kind: "idle" }> }) {
  const error = result.kind === "error";
  const title = error
    ? "Investigation failed"
    : result.kind === "data-quality"
      ? "Data Quality Alert"
      : "No material opportunity detected.";
  const body = error
    ? result.message
    : result.kind === "data-quality"
      ? "Resolve data-quality warnings before interpreting user behavior. No opportunity was created."
      : "No metric crossed the investigation threshold. Continue routine monitoring.";

  return (
    <div role={error ? "alert" : "status"} className={`mt-5 flex items-start gap-3 rounded-lg border p-4 ${error ? "border-[#8e4b43] bg-[#3a2623]" : "border-white/10 bg-white/[0.05]"}`}>
      <AlertIcon className={`mt-0.5 size-4 shrink-0 ${error ? "text-[#f0a89e]" : "text-[#a9d8cf]"}`} />
      <div>
        <p className="text-sm font-semibold">{title}</p>
        <p className="mt-1 text-xs leading-5 text-[#b9b9b3]">{body}</p>
        {!error ? <p className="mt-2 text-[11px] text-[#858580]">Run status: {humanize(result.run.status)}</p> : null}
      </div>
    </div>
  );
}

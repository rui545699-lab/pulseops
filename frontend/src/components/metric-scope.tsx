import { ArrowRightIcon } from "@/components/icons";
import { formatDelta, formatRate } from "@/lib/format";

export function MetricScope({
  eyebrow,
  baseline,
  target,
  delta,
  emphasized = false,
}: {
  eyebrow: string;
  baseline: number | null;
  target: number | null;
  delta: number | null;
  emphasized?: boolean;
}) {
  return (
    <div className={emphasized ? "rounded-xl border border-[#d9d9d3] bg-white p-5 sm:p-6" : ""}>
      <p className="text-[10px] font-semibold uppercase tracking-[0.13em] text-[#777771]">{eyebrow}</p>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <span className={`${emphasized ? "text-3xl sm:text-4xl" : "text-xl"} font-semibold tracking-[-0.04em]`}>
          {formatRate(baseline)}
        </span>
        <ArrowRightIcon className="size-5 text-[#aaa9a3]" />
        <span className={`${emphasized ? "text-3xl sm:text-4xl" : "text-xl"} font-semibold tracking-[-0.04em]`}>
          {formatRate(target)}
        </span>
        <span className={`${emphasized ? "ml-0 sm:ml-3" : "ml-1"} rounded-md bg-[#f4ecea] px-2.5 py-1 text-sm font-semibold text-[#a1493d]`}>
          {formatDelta(delta)}
        </span>
      </div>
    </div>
  );
}

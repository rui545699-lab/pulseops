import { humanize } from "@/lib/format";

const styles: Record<string, string> = {
  HIGH: "border-[#b9ddd5] bg-[#edf7f4] text-[#116b5c]",
  LOW: "border-[#e2ddd0] bg-[#f8f5ed] text-[#76633b]",
  MEDIUM: "border-[#d9d9d4] bg-[#f4f4f1] text-[#55554f]",
  NEEDS_EVIDENCE: "border-[#e2d8be] bg-[#faf6e9] text-[#735f27]",
  OPEN: "border-[#cbded9] bg-[#f0f7f5] text-[#176b5c]",
  READY_FOR_REVIEW: "border-[#bed4e9] bg-[#eff6fc] text-[#315f87]",
  CLOSED: "border-[#ddddda] bg-[#f3f3f1] text-[#6a6a65]",
  COMPLETED: "border-[#cbded9] bg-[#f0f7f5] text-[#176b5c]",
  FAILED: "border-[#ebc9c4] bg-[#fcf1ef] text-[#9a4438]",
  REJECTED: "border-[#e4cbc6] bg-[#fcf2f0] text-[#984a3e]",
  ACCEPTED: "border-[#c5ddd7] bg-[#eff8f5] text-[#176b5c]",
  INSUFFICIENT_EVIDENCE: "border-[#e2d8be] bg-[#faf6e9] text-[#735f27]",
  DATA_QUALITY_ALERT: "border-[#ebc9c4] bg-[#fcf1ef] text-[#9a4438]",
  READY_FOR_REPLICATION_TEST: "border-[#b9ddd5] bg-[#edf7f4] text-[#116b5c]",
  REPRODUCED: "border-[#b9ddd5] bg-[#edf7f4] text-[#116b5c]",
  POSITIVE_GROWTH: "border-[#b9ddd5] bg-[#edf7f4] text-[#116b5c]",
};

export function StatusBadge({ value, label }: { value: string; label?: string }) {
  const display = ["HIGH", "MEDIUM", "LOW"].includes(value) ? value : humanize(value);
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.08em] ${styles[value] ?? "border-[#deded9] bg-white text-[#5f5f59]"}`}
    >
      {label ?? display}
    </span>
  );
}

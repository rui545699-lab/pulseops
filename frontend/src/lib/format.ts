export function formatRate(value: number | null): string {
  return value === null ? "—" : `${value.toFixed(2)}%`;
}

export function formatDelta(value: number | null): string {
  if (value === null) return "—";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}pp`;
}

export function humanize(value: string | null | undefined): string {
  if (!value) return "—";
  return value
    .toLowerCase()
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function segmentLabel(value: string | null): string {
  if (!value) return "All users";
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(" ");
}

export function opportunityTitle(metric: string, segment: string | null): string {
  const scope = segment ? segmentLabel(segment).replace(/ users$/i, "-user") : "Overall";
  return `${scope} ${metric} decline`;
}

export function plannerLabel(mode: string): string {
  return mode === "deepseek" || mode === "llm" ? "AI Planner" : "Deterministic";
}

export function providerLabel(provider: string | null): string {
  if (!provider) return "Not configured";
  return provider.toLowerCase() === "deepseek" ? "DeepSeek" : humanize(provider);
}

export function dateTimeLabel(value: string): string {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

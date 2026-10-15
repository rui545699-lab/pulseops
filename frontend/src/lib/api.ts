import type {
  AgentStep,
  AnalysisRun,
  Opportunity,
  OverviewData,
  RunRequest,
} from "@/lib/types";

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string };
      detail = body.detail ?? detail;
    } catch {
      // Keep the safe status-based message when the backend body is not JSON.
    }
    throw new ApiError(detail, response.status);
  }
  return (await response.json()) as T;
}

export const api = {
  listRuns: () => request<AnalysisRun[]>("/api/runs"),
  getRun: (runId: string) => request<AnalysisRun>(`/api/runs/${runId}`),
  getRunSteps: (runId: string) =>
    request<AgentStep[]>(`/api/runs/${runId}/steps`),
  listOpportunities: () => request<Opportunity[]>("/api/opportunities"),
  getOpportunity: (opportunityId: string) =>
    request<Opportunity>(`/api/opportunities/${opportunityId}`),
  createRun: (payload: RunRequest) =>
    request<AnalysisRun>("/api/runs", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};

export async function loadOverview(): Promise<OverviewData> {
  const [opportunities, runs] = await Promise.all([
    api.listOpportunities(),
    api.listRuns(),
  ]);
  const runsById = new Map(runs.map((run) => [run.id, run]));
  return {
    runs,
    opportunities: opportunities.map((opportunity) => ({
      opportunity,
      run: runsById.get(opportunity.run_id) ?? null,
    })),
  };
}

export async function loadOpportunityDetail(opportunityId: string) {
  const opportunity = await api.getOpportunity(opportunityId);
  const run = await api.getRun(opportunity.run_id);
  return { opportunity, run };
}

export async function loadRunDetail(runId: string) {
  const [run, steps] = await Promise.all([
    api.getRun(runId),
    api.getRunSteps(runId),
  ]);
  return { run, steps: [...steps].sort((a, b) => a.step_order - b.step_order) };
}

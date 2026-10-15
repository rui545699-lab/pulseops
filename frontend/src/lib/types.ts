export type PlannerMode = "deterministic" | "deepseek";

export interface AnalysisRun {
  id: string;
  baseline_start: string;
  baseline_end: string;
  target_start: string;
  target_end: string;
  planner_mode: PlannerMode;
  provider: string | null;
  model_identifier: string | null;
  detected_signal: string | null;
  overall_baseline_rate: number | null;
  overall_target_rate: number | null;
  overall_delta_pp: number | null;
  affected_segment: string | null;
  signal_confidence: string;
  root_cause_confidence: string;
  stop_reason: string | null;
  recommended_status: string | null;
  recommended_action_type: string;
  status: "COMPLETED" | "FAILED" | string;
  started_at: string;
  completed_at: string | null;
  created_at: string;
}

export interface AgentStep {
  id: string;
  run_id: string;
  step_order: number;
  node: string;
  tool_name: string | null;
  planner_proposal: {
    action?: string;
    dimension?: string | null;
    lifecycle_filter?: string | null;
    rationale?: string;
    hypothesis_code?: string | null;
  } | null;
  planner_rationale: string | null;
  guard_status: string | null;
  guard_reason: string | null;
  tool_input: Record<string, unknown>;
  tool_output_summary: Record<string, unknown>;
  decision: string;
  decision_reason: string;
  hypothesis: string | null;
  hypothesis_status: string | null;
  remaining_budget: number;
  fallback_used: boolean;
  fallback_reason: string | null;
  created_at: string;
}

export interface Opportunity {
  id: string;
  run_id: string;
  title: string;
  opportunity_type: string;
  affected_segment: string | null;
  metric: string;
  baseline_rate: number;
  target_rate: number;
  delta_pp: number;
  signal_confidence: string;
  root_cause_confidence: string;
  evidence: string[];
  hypotheses: string[];
  unknowns: string[];
  recommended_status: string;
  recommended_action_type: string;
  recommended_next_action: string | null;
  do_not_recommend_yet: string[];
  status: "OPEN" | "NEEDS_EVIDENCE" | "READY_FOR_REVIEW" | "CLOSED" | string;
  created_at: string;
  updated_at: string;
}

export interface RunRequest {
  baseline_start: string;
  baseline_end: string;
  target_start: string;
  target_end: string;
  planner_mode: PlannerMode;
}

export interface OpportunityWithRun {
  opportunity: Opportunity;
  run: AnalysisRun | null;
}

export interface OverviewData {
  opportunities: OpportunityWithRun[];
  runs: AnalysisRun[];
}

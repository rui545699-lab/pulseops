export type PlannerMode = "deterministic" | "deepseek";

export interface AnalysisRun {
  id: string;
  analysis_type: "CONVERSION" | "LIFECYCLE_RISK" | "POSITIVE_GROWTH" | string;
  baseline_start: string;
  baseline_end: string;
  target_start: string;
  target_end: string;
  post_start: string | null;
  post_end: string | null;
  confirmation_start: string | null;
  confirmation_end: string | null;
  holdout_1_start: string | null;
  holdout_1_end: string | null;
  holdout_2_start: string | null;
  holdout_2_end: string | null;
  planner_mode: PlannerMode;
  provider: string | null;
  model_identifier: string | null;
  detected_signal: string | null;
  overall_baseline_rate: number | null;
  overall_target_rate: number | null;
  overall_delta_pp: number | null;
  post_rate: number | null;
  target_to_post_delta_pp: number | null;
  baseline_to_post_delta_pp: number | null;
  recovery_ratio: number | null;
  risk_pattern: string | null;
  return_timing: ReturnTiming | null;
  growth_analysis: GrowthAnalysis | null;
  reproducibility: string | null;
  growth_signal_confidence: string | null;
  reproducibility_confidence: string | null;
  growth_localization: string | null;
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
  post_rate: number | null;
  target_to_post_delta_pp: number | null;
  baseline_to_post_delta_pp: number | null;
  recovery_ratio: number | null;
  risk_pattern: string | null;
  return_timing: ReturnTiming | null;
  growth_period: GrowthPeriod | null;
  confirmation_period: GrowthPeriod | null;
  holdout_results: { holdout_1: GrowthPeriod; holdout_2: GrowthPeriod } | null;
  reproducibility: string | null;
  growth_signal_confidence: string | null;
  reproducibility_confidence: string | null;
  growth_localization: string | null;
  order_value_context: OrderValueContext | null;
  segment_analysis: Record<string, unknown> | null;
  hypothesis_records: Array<{ code: string; reason: string; status: string }> | null;
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
  analysis_type: "CONVERSION" | "LIFECYCLE_RISK" | "POSITIVE_GROWTH";
  baseline_start: string;
  baseline_end: string;
  target_start: string;
  target_end: string;
  post_start?: string;
  post_end?: string;
  confirmation_start?: string;
  confirmation_end?: string;
  holdout_1_start?: string;
  holdout_1_end?: string;
  holdout_2_start?: string;
  holdout_2_end?: string;
  planner_mode: PlannerMode;
}

export interface ReturnTimingPeriod {
  eligible_new_users: number;
  returned_users_d1: number;
  return_rate_d1: number;
  returned_users_d3: number;
  return_rate_d3: number;
  returned_users_d7: number;
  return_rate_d7: number;
}

export interface ReturnTiming {
  baseline: ReturnTimingPeriod;
  target: ReturnTimingPeriod;
  post: ReturnTimingPeriod;
  d1_decline_contribution_pct: number;
  d2_3_decline_contribution_pct: number;
  d4_7_decline_contribution_pct: number;
}

export interface GrowthPeriod {
  checkout_sessions: number;
  purchase_after_checkout_sessions: number;
  conversion_rate: number;
}

export interface StatisticalResult {
  delta_pp: number;
  z_score: number;
  p_value: number;
  statistically_significant: boolean;
}

export interface GrowthAnalysis {
  metric_name: string;
  baseline: GrowthPeriod;
  growth: GrowthPeriod;
  confirmation: GrowthPeriod;
  holdout_1: GrowthPeriod;
  holdout_2: GrowthPeriod;
  delta_pp: number;
  growth_statistical_result: StatisticalResult;
  confirmation_statistical_result: StatisticalResult;
  holdout_1_statistical_result: StatisticalResult;
  holdout_2_statistical_result: StatisticalResult;
}

export interface OrderValueContext {
  baseline_revenue_usd: number;
  baseline_average_order_value_usd: number;
  growth_revenue_usd: number;
  growth_average_order_value_usd: number;
  confirmation_revenue_usd: number;
  confirmation_average_order_value_usd: number;
}

export interface OpportunityWithRun {
  opportunity: Opportunity;
  run: AnalysisRun | null;
}

export interface OverviewData {
  opportunities: OpportunityWithRun[];
  runs: AnalysisRun[];
}

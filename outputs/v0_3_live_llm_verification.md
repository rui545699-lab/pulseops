# V0.3 Positive Growth Live DeepSeek Planner Verification

- Provider: `deepseek`
- Model: `deepseek-flash`
- Analytics input: Case 03 verified Golden Fixture; live provider used only for bounded planning.
- Overall result: **PASS**

## Aggregate

- Runs: 3
- Proposals / accepted / rejected: 9 / 9 / 0
- Fallbacks: 0 ({})
- Illegal / filter / duplicate / premature STOP: 0 / 0 / 0 / 0
- Unsupported causal / broad-scale / intervention boundary: 0 / 0 / 0

## Runs

| Run | Planner sequence | Accepted | Rejected | Fallbacks | Stop | Passed |
|---|---|---:|---:|---:|---|---|
| case-03-live-1 | lifecycle → device → acquisition | 3 | 0 | 0 | ALLOWED_DIMENSIONS_EXHAUSTED | True |
| case-03-live-2 | lifecycle → device → acquisition | 3 | 0 | 0 | ALLOWED_DIMENSIONS_EXHAUSTED | True |
| case-03-live-3 | lifecycle → device → acquisition | 3 | 0 | 0 | ALLOWED_DIMENSIONS_EXHAUSTED | True |

## Complete Planner → Guard → Executed Tool Log: Run 1

```json
[
  {
    "step_order": 6,
    "proposed_action": "INVESTIGATE",
    "proposed_dimension": "lifecycle",
    "proposed_lifecycle_filter": null,
    "proposed_hypothesis_code": null,
    "rationale": "Investigate whether the validated Checkout→Purchase lift is concentrated in particular lifecycle stages, since a validated lift is not a proven mechanism and composition changes across lifecycle stages may be associated with the observed pattern.",
    "guard_status": "ACCEPTED",
    "guard_reason": "ACCEPTED",
    "executed_tool": "compare_growth_segments",
    "executed_dimension": "lifecycle",
    "executed_lifecycle_filter": null,
    "fallback_used": false,
    "fallback_reason": null,
    "state_before": {
      "investigated_dimensions": [],
      "remaining_dimensions": [
        "lifecycle",
        "device",
        "acquisition"
      ],
      "remaining_budget": 4,
      "stop_allowed": false,
      "growth_signal_confidence": "HIGH",
      "reproducibility": "REPRODUCED",
      "localization": null
    },
    "state_after": {
      "investigated_dimensions": [
        "lifecycle"
      ],
      "remaining_dimensions": [
        "device",
        "acquisition"
      ],
      "remaining_budget": 3,
      "stop_allowed": false,
      "growth_signal_confidence": "HIGH",
      "reproducibility": "REPRODUCED",
      "localization": null
    }
  },
  {
    "step_order": 7,
    "proposed_action": "INVESTIGATE",
    "proposed_dimension": "device",
    "proposed_lifecycle_filter": null,
    "proposed_hypothesis_code": null,
    "rationale": "Investigate whether the validated Checkout→Purchase lift is concentrated by device, since lifecycle was already investigated and the lift was broad across lifecycle segments; evidence is insufficient to establish causality.",
    "guard_status": "ACCEPTED",
    "guard_reason": "ACCEPTED",
    "executed_tool": "compare_growth_segments",
    "executed_dimension": "device",
    "executed_lifecycle_filter": null,
    "fallback_used": false,
    "fallback_reason": null,
    "state_before": {
      "investigated_dimensions": [
        "lifecycle"
      ],
      "remaining_dimensions": [
        "device",
        "acquisition"
      ],
      "remaining_budget": 3,
      "stop_allowed": false,
      "growth_signal_confidence": "HIGH",
      "reproducibility": "REPRODUCED",
      "localization": null
    },
    "state_after": {
      "investigated_dimensions": [
        "lifecycle",
        "device"
      ],
      "remaining_dimensions": [
        "acquisition"
      ],
      "remaining_budget": 2,
      "stop_allowed": false,
      "growth_signal_confidence": "HIGH",
      "reproducibility": "REPRODUCED",
      "localization": null
    }
  },
  {
    "step_order": 8,
    "proposed_action": "INVESTIGATE",
    "proposed_dimension": "acquisition",
    "proposed_lifecycle_filter": null,
    "proposed_hypothesis_code": null,
    "rationale": "Investigate whether the observed Checkout→Purchase lift is concentrated in or associated with particular acquisition segments, since lifecycle and device patterns were broad and acquisition composition remains unexamined; evidence is insufficient to establish causality.",
    "guard_status": "ACCEPTED",
    "guard_reason": "ACCEPTED",
    "executed_tool": "compare_growth_segments",
    "executed_dimension": "acquisition",
    "executed_lifecycle_filter": null,
    "fallback_used": false,
    "fallback_reason": null,
    "state_before": {
      "investigated_dimensions": [
        "lifecycle",
        "device"
      ],
      "remaining_dimensions": [
        "acquisition"
      ],
      "remaining_budget": 2,
      "stop_allowed": false,
      "growth_signal_confidence": "HIGH",
      "reproducibility": "REPRODUCED",
      "localization": null
    },
    "state_after": {
      "investigated_dimensions": [
        "lifecycle",
        "device",
        "acquisition"
      ],
      "remaining_dimensions": [],
      "remaining_budget": 1,
      "stop_allowed": true,
      "growth_signal_confidence": "HIGH",
      "reproducibility": "REPRODUCED",
      "localization": "BROAD"
    }
  }
]
```

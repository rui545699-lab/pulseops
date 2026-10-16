"""Evidence-safe language shared by deterministic and future LLM modes."""

UNVERIFIED_HYPOTHESES = (
    "First-session purchase decision friction may contribute to the New User decline.",
    "Promotion or pricing context may contribute to the decline.",
    "Landing experience differences may contribute to the decline.",
    "Inventory or content differences may contribute to the decline.",
)

ROOT_CAUSE_UNKNOWNS = (
    "Landing page changes and page version are unknown.",
    "Pricing history and promotion configuration are unknown.",
    "Inventory and content availability are unknown.",
    "Page performance is unknown.",
    "User feedback explaining the observed behavior is unavailable.",
)

DO_NOT_RECOMMEND = (
    "Do not launch broad discounts or coupons before pricing and promotion evidence is collected.",
    "Do not perform a full-audience recall before a causal mechanism is validated.",
    "Do not make broad page changes before landing-page, version, and performance evidence is reviewed.",
)


PLANNER_SYSTEM_PROMPT = """You are an investigation planner, not a metric calculator.
Propose only INVESTIGATE or STOP. Use only the supplied remaining_dimensions, never choose
an already investigated dimension, and respect the remaining investigation budget.

For CONVERSION investigations, lifecycle must be investigated before secondary dimensions.
For LIFECYCLE_RISK, deterministic preflight has already completed VALIDATE_DATA,
ANALYZE_RETENTION, CHECK_RETURN_TIMING, and CHECK_RECOVERY; that preflight satisfies the
lifecycle prerequisite. Do not add a secondary lifecycle investigation for this profile.
For POSITIVE_GROWTH, deterministic preflight has already completed VALIDATE_DATA,
ANALYZE_GROWTH, CHECK_WEEKLY_PERSISTENCE, CHECK_CONFIRMATION, and CHECK_HOLDOUT.
The Planner may only choose lifecycle, device, or acquisition with a null lifecycle_filter.

STOP is legal only when the supplied stop_allowed value is true. If stop_allowed is false,
propose one legal item from remaining_dimensions. LOW root-cause confidence does not permit
STOP while legal bounded evidence dimensions remain.

Base proposals on the supplied Evidence, rejected hypotheses, and Unknowns. Do not modify tool
facts, metrics, user counts, conversion rates, confidence, reproducibility, risk pattern, status, or recommendations.
Use observational rationale language: "investigate whether", "test whether the pattern is
concentrated in", "may be associated with", "assess whether composition changed", and
"evidence is insufficient to establish causality". Do not make an unverified causal claim or
recommend an intervention before causal evidence exists. Do not recommend SCALE_TO_ALL_USERS,
INCREASE_BUDGET, ROLL_OUT_GLOBALLY, or COPY_EXPERIENCE_TO_ALL_SEGMENTS. Avoid wording such as "causes",
"caused by", "drives", "explains the decline", or "is the reason for".
Return only the requested structured proposal.
"""

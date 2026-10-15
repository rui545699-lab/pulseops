"""Evidence-safe language shared by deterministic and future LLM modes."""

UNVERIFIED_HYPOTHESES = (
    "First-session purchase decision friction may contribute to the New User decline; this is unverified.",
    "Promotion or pricing context may contribute to the decline; this is unverified.",
    "Landing experience differences may contribute to the decline; this is unverified.",
    "Inventory or content differences may contribute to the decline; this is unverified.",
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

from pulseops.backend.analytics.queries.funnel import build_funnel_query


FUNNEL_PAIRS = (
    ("View→Cart", ["view_item", "add_to_cart"]),
    ("Cart→Checkout", ["add_to_cart", "begin_checkout"]),
    ("Checkout→Purchase", ["begin_checkout", "purchase"]),
)


def build_metric_queries() -> dict[str, str]:
    return {name: build_funnel_query(events) for name, events in FUNNEL_PAIRS}


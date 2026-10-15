from __future__ import annotations

from pulseops.backend.analytics.queries.funnel import DATASET

SUPPORTED_DIMENSIONS = {"lifecycle", "device", "acquisition", "category"}


def build_segment_query(
    dimension: str, lifecycle_filter: str | None = None
) -> str:
    if dimension not in SUPPORTED_DIMENSIONS:
        raise ValueError(f"unsupported dimension: {dimension}")
    if lifecycle_filter not in {None, "new", "returning"}:
        raise ValueError("lifecycle_filter must be 'new', 'returning', or None")
    if dimension == "lifecycle" and lifecycle_filter is not None:
        raise ValueError("lifecycle_filter cannot be applied to lifecycle dimension")

    if dimension == "lifecycle":
        expression = (
            "IF(DATE(TIMESTAMP_MICROS(user_first_touch_timestamp)) "
            "BETWEEN @start_date AND @end_date, 'new', 'returning')"
        )
        item_join = ""
    elif dimension == "device":
        expression = "COALESCE(device.category, '(unknown)')"
        item_join = ""
    elif dimension == "acquisition":
        expression = (
            "CONCAT(COALESCE(traffic_source.source, '(not set)'), ' / ', "
            "COALESCE(traffic_source.medium, '(not set)'))"
        )
        item_join = ""
    else:
        expression = "COALESCE(item.item_category, '(not set)')"
        item_join = "LEFT JOIN UNNEST(items) AS item"

    lifecycle_clause = ""
    if lifecycle_filter == "new":
        lifecycle_clause = (
            "AND DATE(TIMESTAMP_MICROS(user_first_touch_timestamp)) "
            "BETWEEN @start_date AND @end_date"
        )
    elif lifecycle_filter == "returning":
        lifecycle_clause = (
            "AND NOT (DATE(TIMESTAMP_MICROS(user_first_touch_timestamp)) "
            "BETWEEN @start_date AND @end_date)"
        )

    return f"""
WITH entry_events AS (
  SELECT
    user_pseudo_id,
    (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id') AS session_id,
    event_timestamp AS entry_ts,
    {expression} AS segment
  FROM {DATASET}
  {item_join}
  WHERE _TABLE_SUFFIX BETWEEN FORMAT_DATE('%Y%m%d', @start_date)
                          AND FORMAT_DATE('%Y%m%d', @end_date)
    AND event_name = 'view_item'
    {lifecycle_clause}
),
entries AS (
  SELECT user_pseudo_id, session_id, segment, MIN(entry_ts) AS entry_ts
  FROM entry_events
  WHERE session_id IS NOT NULL
  GROUP BY user_pseudo_id, session_id, segment
),
conversions AS (
  SELECT DISTINCT e.user_pseudo_id, e.session_id, e.segment
  FROM entries e
  JOIN {DATASET} c
    ON c.user_pseudo_id = e.user_pseudo_id
   AND (SELECT value.int_value FROM UNNEST(c.event_params) WHERE key = 'ga_session_id') = e.session_id
   AND c.event_name = 'add_to_cart'
   AND c.event_timestamp > e.entry_ts
   AND c._TABLE_SUFFIX BETWEEN FORMAT_DATE('%Y%m%d', @start_date)
                           AND FORMAT_DATE('%Y%m%d', @end_date)
)
SELECT
  e.segment,
  COUNT(DISTINCT e.user_pseudo_id) AS view_users,
  COUNT(DISTINCT c.user_pseudo_id) AS converted_users
FROM entries e
LEFT JOIN conversions c USING (user_pseudo_id, session_id, segment)
GROUP BY e.segment
ORDER BY view_users DESC
""".strip()


from __future__ import annotations

from pulseops.backend.analytics.queries.funnel import DATASET


def build_growth_validation_query() -> str:
    return f"""
WITH calendar AS (
  SELECT day FROM UNNEST(GENERATE_DATE_ARRAY(@baseline_start, @holdout_2_end)) AS day
), daily AS (
  SELECT PARSE_DATE('%Y%m%d', event_date) AS day,
         COUNTIF(event_name = 'begin_checkout') AS checkout_events,
         COUNTIF(event_name = 'purchase') AS purchase_events
  FROM {DATASET}
  WHERE _TABLE_SUFFIX BETWEEN FORMAT_DATE('%Y%m%d', @baseline_start)
                          AND FORMAT_DATE('%Y%m%d', @holdout_2_end)
    AND event_name IN ('begin_checkout', 'purchase')
  GROUP BY day
)
SELECT calendar.day, COALESCE(checkout_events, 0) AS checkout_events,
       COALESCE(purchase_events, 0) AS purchase_events
FROM calendar LEFT JOIN daily USING (day)
ORDER BY day
""".strip()


def build_growth_segment_query(dimension: str) -> str:
    if dimension not in {"lifecycle", "device", "acquisition"}:
        raise ValueError(f"unsupported growth dimension: {dimension}")
    expression = {
        "lifecycle": "IF(first_visit_ts IS NULL, 'returning_users', 'new_users')",
        "device": "device",
        "acquisition": "CONCAT(source, ' / ', medium)",
    }[dimension]
    return f"""
WITH events AS (
  SELECT
    PARSE_DATE('%Y%m%d', event_date) AS event_date,
    event_timestamp,
    user_pseudo_id,
    event_name,
    (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id') AS session_id,
    COALESCE(traffic_source.source, '(not set)') AS source,
    COALESCE(traffic_source.medium, '(not set)') AS medium,
    COALESCE(device.category, '(not set)') AS device
  FROM {DATASET}
  WHERE _TABLE_SUFFIX BETWEEN FORMAT_DATE('%Y%m%d', @baseline_start)
                          AND FORMAT_DATE('%Y%m%d', @target_end)
    AND event_name IN ('first_visit', 'begin_checkout', 'purchase')
    AND user_pseudo_id IS NOT NULL
), sessions AS (
  SELECT
    CASE WHEN event_date BETWEEN @baseline_start AND @baseline_end THEN 'baseline' ELSE 'growth' END AS period,
    user_pseudo_id, session_id, ANY_VALUE(source) AS source, ANY_VALUE(medium) AS medium,
    ANY_VALUE(device) AS device,
    MIN(IF(event_name = 'first_visit', event_timestamp, NULL)) AS first_visit_ts,
    MIN(IF(event_name = 'begin_checkout', event_timestamp, NULL)) AS checkout_ts,
    MIN(IF(event_name = 'purchase', event_timestamp, NULL)) AS purchase_ts
  FROM events
  WHERE event_date BETWEEN @baseline_start AND @baseline_end
     OR event_date BETWEEN @target_start AND @target_end
  GROUP BY period, user_pseudo_id, session_id
), labeled AS (
  SELECT period, {expression} AS segment, checkout_ts,
         purchase_ts IS NOT NULL AND purchase_ts > checkout_ts AS purchased_after_checkout
  FROM sessions
  WHERE session_id IS NOT NULL AND checkout_ts IS NOT NULL
)
SELECT period, segment, COUNT(*) AS checkout_sessions,
       COUNTIF(purchased_after_checkout) AS purchase_after_checkout_sessions
FROM labeled
GROUP BY period, segment
ORDER BY period, segment
""".strip()


def build_growth_weekly_query() -> str:
    return f"""
WITH events AS (
  SELECT PARSE_DATE('%Y%m%d', event_date) AS event_date, event_timestamp,
         user_pseudo_id, event_name,
         (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id') AS session_id
  FROM {DATASET}
  WHERE _TABLE_SUFFIX BETWEEN FORMAT_DATE('%Y%m%d', @baseline_start)
                          AND FORMAT_DATE('%Y%m%d', @confirmation_end)
    AND event_name IN ('begin_checkout', 'purchase') AND user_pseudo_id IS NOT NULL
), sessions AS (
  SELECT event_date, user_pseudo_id, session_id,
         MIN(IF(event_name='begin_checkout', event_timestamp, NULL)) AS checkout_ts,
         MIN(IF(event_name='purchase', event_timestamp, NULL)) AS purchase_ts
  FROM events GROUP BY event_date, user_pseudo_id, session_id
)
SELECT FORMAT_DATE('%F', DATE_TRUNC(event_date, WEEK(MONDAY))) AS cohort_week,
       CASE WHEN event_date BETWEEN @baseline_start AND @baseline_end THEN 'BASELINE'
            WHEN event_date BETWEEN @target_start AND @target_end THEN 'GROWTH'
            ELSE 'CONFIRMATION' END AS period,
       COUNTIF(checkout_ts IS NOT NULL) AS checkout_sessions,
       COUNTIF(checkout_ts IS NOT NULL AND purchase_ts > checkout_ts) AS purchase_after_checkout_sessions
FROM sessions
WHERE event_date BETWEEN @baseline_start AND @baseline_end
   OR event_date BETWEEN @target_start AND @target_end
   OR event_date BETWEEN @confirmation_start AND @confirmation_end
GROUP BY cohort_week, period ORDER BY cohort_week
""".strip()

from __future__ import annotations

from pulseops.backend.analytics.queries.funnel import DATASET


def _events_cte() -> str:
    return f"""
events AS (
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
                          AND FORMAT_DATE('%Y%m%d', @observation_end)
    AND user_pseudo_id IS NOT NULL
    AND event_name IN (
      'first_visit', 'session_start', 'view_item', 'add_to_cart',
      'begin_checkout', 'purchase'
    )
),
first_visits AS (
  SELECT
    user_pseudo_id,
    event_date AS first_visit_date,
    session_id AS first_session_id,
    source,
    medium,
    device
  FROM events
  WHERE event_name = 'first_visit'
  QUALIFY ROW_NUMBER() OVER (PARTITION BY user_pseudo_id ORDER BY event_timestamp) = 1
),
cohorts AS (
  SELECT *,
    CASE
      WHEN first_visit_date BETWEEN @baseline_start AND @baseline_end THEN 'baseline'
      WHEN first_visit_date BETWEEN @target_start AND @target_end THEN 'target'
      WHEN first_visit_date BETWEEN @post_start AND @post_end THEN 'post'
    END AS period
  FROM first_visits
  WHERE first_visit_date BETWEEN @baseline_start AND @baseline_end
     OR first_visit_date BETWEEN @target_start AND @target_end
     OR first_visit_date BETWEEN @post_start AND @post_end
)
"""


def build_lifecycle_timing_query() -> str:
    return f"""
WITH {_events_cte()},
outcomes AS (
  SELECT
    c.user_pseudo_id,
    c.period,
    COUNTIF(e.event_name = 'session_start'
            AND e.event_date = DATE_ADD(c.first_visit_date, INTERVAL 1 DAY)) > 0 AS returned_d1,
    COUNTIF(e.event_name = 'session_start'
            AND e.event_date > c.first_visit_date
            AND e.event_date <= DATE_ADD(c.first_visit_date, INTERVAL 3 DAY)) > 0 AS returned_d3,
    COUNTIF(e.event_name = 'session_start'
            AND e.event_date > c.first_visit_date
            AND e.event_date <= DATE_ADD(c.first_visit_date, INTERVAL 7 DAY)) > 0 AS returned_d7
  FROM cohorts c
  LEFT JOIN events e
    ON e.user_pseudo_id = c.user_pseudo_id
   AND e.event_date BETWEEN c.first_visit_date AND DATE_ADD(c.first_visit_date, INTERVAL 7 DAY)
  GROUP BY c.user_pseudo_id, c.period
)
SELECT
  period,
  COUNT(*) AS eligible_new_users,
  COUNTIF(returned_d1) AS returned_users_d1,
  COUNTIF(returned_d3) AS returned_users_d3,
  COUNTIF(returned_d7) AS returned_users_d7
FROM outcomes
GROUP BY period
""".strip()


def build_lifecycle_validation_query() -> str:
    return f"""
WITH calendar AS (
  SELECT day FROM UNNEST(GENERATE_DATE_ARRAY(@baseline_start, @observation_end)) AS day
), counts AS (
  SELECT
    PARSE_DATE('%Y%m%d', event_date) AS day,
    COUNTIF(event_name = 'first_visit') AS first_visit_events,
    COUNTIF(event_name = 'session_start') AS session_start_events,
    COUNTIF(event_name = 'add_to_cart') AS add_to_cart_events
  FROM {DATASET}
  WHERE _TABLE_SUFFIX BETWEEN FORMAT_DATE('%Y%m%d', @baseline_start)
                          AND FORMAT_DATE('%Y%m%d', @observation_end)
    AND event_name IN ('first_visit', 'session_start', 'add_to_cart')
  GROUP BY day
)
SELECT
  calendar.day,
  COALESCE(first_visit_events, 0) AS first_visit_events,
  COALESCE(session_start_events, 0) AS session_start_events,
  COALESCE(add_to_cart_events, 0) AS add_to_cart_events
FROM calendar LEFT JOIN counts USING (day)
ORDER BY day
""".strip()


def build_lifecycle_segment_query(dimension: str) -> str:
    if dimension not in {"acquisition", "device", "activation_depth"}:
        raise ValueError(f"unsupported lifecycle dimension: {dimension}")
    segment_expression = {
        "acquisition": "CONCAT(c.source, ' / ', c.medium)",
        "device": "c.device",
        "activation_depth": "CASE WHEN first_session_carted THEN 'INTENT' WHEN first_session_viewed THEN 'BROWSE' WHEN first_session_started THEN 'SHALLOW' ELSE 'UNCLASSIFIED' END",
    }[dimension]
    return f"""
WITH {_events_cte()},
outcomes AS (
  SELECT
    c.user_pseudo_id,
    c.period,
    c.source,
    c.medium,
    c.device,
    COUNTIF(e.event_name = 'session_start'
            AND e.event_date > c.first_visit_date
            AND e.event_date <= DATE_ADD(c.first_visit_date, INTERVAL 7 DAY)) > 0 AS returned_d7,
    COUNTIF(s.event_name = 'session_start') > 0 AS first_session_started,
    COUNTIF(s.event_name = 'view_item') > 0 AS first_session_viewed,
    COUNTIF(s.event_name IN ('add_to_cart', 'begin_checkout', 'purchase')) > 0 AS first_session_carted
  FROM cohorts c
  LEFT JOIN events e
    ON e.user_pseudo_id = c.user_pseudo_id
   AND e.event_date BETWEEN c.first_visit_date AND DATE_ADD(c.first_visit_date, INTERVAL 7 DAY)
  LEFT JOIN events s
    ON s.user_pseudo_id = c.user_pseudo_id
   AND s.session_id = c.first_session_id
   AND s.event_date = c.first_visit_date
  WHERE c.period IN ('baseline', 'target')
  GROUP BY c.user_pseudo_id, c.period, c.source, c.medium, c.device
), labeled AS (
  SELECT period, returned_d7, {segment_expression} AS segment
  FROM outcomes c
)
SELECT
  period,
  segment,
  COUNT(*) AS eligible_users,
  COUNTIF(returned_d7) AS returned_users
FROM labeled
GROUP BY period, segment
ORDER BY segment, period
""".strip()

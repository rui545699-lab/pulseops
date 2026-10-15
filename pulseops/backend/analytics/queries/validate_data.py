from pulseops.backend.analytics.queries.funnel import DATASET


def build_validation_query() -> str:
    return f"""
SELECT
  PARSE_DATE('%Y%m%d', event_date) AS event_date,
  event_name,
  COUNT(*) AS event_count,
  COUNT(DISTINCT user_pseudo_id) AS users,
  COUNT(DISTINCT CONCAT(user_pseudo_id, ':', CAST(
    (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id') AS STRING
  ))) AS sessions
FROM {DATASET}
WHERE _TABLE_SUFFIX BETWEEN FORMAT_DATE('%Y%m%d', @start_date)
                        AND FORMAT_DATE('%Y%m%d', @end_date)
  AND event_name IN ('view_item', 'add_to_cart', 'begin_checkout', 'purchase')
GROUP BY event_date, event_name
ORDER BY event_date, event_name
""".strip()


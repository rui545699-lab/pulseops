from __future__ import annotations

import re

DATASET = "`bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`"
_EVENT_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def build_funnel_query(events: list[str]) -> str:
    """Build a strict same-user, same-session, ordered funnel query."""
    if len(events) < 2 or any(not _EVENT_RE.fullmatch(e) for e in events):
        raise ValueError("events must contain at least two safe GA4 event names")

    ctes = [
        f"""event_stream AS (
  SELECT
    user_pseudo_id,
    (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id') AS session_id,
    event_name,
    event_timestamp
  FROM {DATASET}
  WHERE _TABLE_SUFFIX BETWEEN FORMAT_DATE('%Y%m%d', @start_date)
                          AND FORMAT_DATE('%Y%m%d', @end_date)
    AND event_name IN ({', '.join(repr(e) for e in events)})
),
step_1 AS (
  SELECT user_pseudo_id, session_id, MIN(event_timestamp) AS step_1_ts
  FROM event_stream
  WHERE event_name = '{events[0]}' AND session_id IS NOT NULL
  GROUP BY user_pseudo_id, session_id
)"""
    ]
    for index, event in enumerate(events[1:], start=2):
        previous = index - 1
        ctes.append(
            f"""step_{index} AS (
  SELECT p.user_pseudo_id, p.session_id, p.step_{previous}_ts,
         MIN(e.event_timestamp) AS step_{index}_ts
  FROM step_{previous} p
  JOIN event_stream e
    ON e.user_pseudo_id = p.user_pseudo_id
   AND e.session_id = p.session_id
   AND e.event_name = '{event}'
   AND e.event_timestamp > p.step_{previous}_ts
  GROUP BY p.user_pseudo_id, p.session_id, p.step_{previous}_ts
)"""
        )
    last = len(events)
    return f"""
WITH
{',\n'.join(ctes)},
converted_users AS (
  SELECT DISTINCT user_pseudo_id FROM step_{last}
)
SELECT
  (SELECT COUNT(*) FROM step_1) AS view_sessions,
  (SELECT COUNT(*) FROM step_{last}) AS converted_sessions,
  (SELECT COUNT(DISTINCT user_pseudo_id) FROM step_1) AS view_users,
  (SELECT COUNT(*) FROM converted_users) AS converted_users
""".strip()


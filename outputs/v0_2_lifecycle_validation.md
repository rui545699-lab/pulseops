# V0.2 Lifecycle Risk — Phase B Validation & Investigation Design

## Scope and metric

This validation uses real data from `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`. The Case 02 windows remain unchanged.

**New-user 7-day Return Rate** counts an eligible user as returned when at least one `session_start` occurs on day 1 through day 7 after the user’s `first_visit`. Day 0 is excluded, and every included cohort has a complete seven-day observation window.

## Baseline, Target, and Post

| Period | Cohort dates | Eligible new users | Returned users D7 | Return rate D7 |
|---|---|---:|---:|---:|
| Baseline | 2020-11-30–2020-12-13 | 48,753 | 4,060 | 8.33% |
| Target | 2020-12-21–2021-01-03 | 33,313 | 1,703 | 5.11% |
| Post | 2021-01-04–2021-01-24 | 63,686 | 4,397 | 6.90% |

- Baseline → Target: **-3.22pp**
- Target → Post: **+1.79pp**
- Baseline → Post: **-1.42pp**

### Recovery classification

The classification rule is data-driven:

- `NO_RECOVERY`: Post is not materially and statistically above Target.
- `FULL_RECOVERY`: Post reaches/exceeds Baseline or is not statistically below it.
- `PARTIAL_RECOVERY`: Post is statistically above Target and statistically below Baseline.

Post recovered 55.73% of the Baseline-to-Target loss. It is significantly above Target (two-proportion z = 10.92) and significantly below Baseline (z = -8.97).

**Recovery classification: PARTIAL_RECOVERY**

## Return timing curve

| Period | D1 returned | D1 rate | D1–3 returned | D1–3 cumulative | D1–7 returned | D1–7 cumulative |
|---|---:|---:|---:|---:|---:|---:|
| Baseline | 2,243 | 4.60% | 3,221 | 6.61% | 4,060 | 8.33% |
| Target | 966 | 2.90% | 1,371 | 4.12% | 1,703 | 5.11% |
| Post | 2,424 | 3.81% | 3,495 | 5.49% | 4,397 | 6.90% |

Baseline-to-Target changes were -1.70pp at D1, -2.49pp cumulatively by D3, and -3.22pp cumulatively by D7. Of the final D7 gap, 52.90% was already present on D1, another 24.58% accumulated on days 2–3, and 22.52% accumulated on days 4–7.

The largest component appears on day 1, but the weakness continues across the full seven-day window. This timing pattern is descriptive and is not a causal explanation.

## Acquisition analysis

| Source / medium | Baseline users | Baseline rate | Baseline share | Target users | Target rate | Target share | Rate change | Share change |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| (direct) / (none) | 11,530 | 8.60% | 23.65% | 7,879 | 5.13% | 23.65% | -3.48pp | +0.00pp |
| `<Other> / <Other>` | 8,771 | 8.37% | 17.99% | 6,046 | 4.75% | 18.15% | -3.62pp | +0.16pp |
| `<Other> / organic` | 1,590 | 8.55% | 3.26% | 1,103 | 5.53% | 3.31% | -3.02pp | +0.05pp |
| `<Other> / referral` | 4,503 | 7.84% | 9.24% | 3,173 | 4.82% | 9.52% | -3.02pp | +0.29pp |
| google / cpc | 2,781 | 8.13% | 5.70% | 1,778 | 5.29% | 5.34% | -2.84pp | -0.37pp |
| google / organic | 17,128 | 8.33% | 35.13% | 11,735 | 5.32% | 35.23% | -3.01pp | +0.09pp |
| shop.googlemerchandisestore.com / referral | 2,445 | 7.81% | 5.02% | 1,595 | 5.02% | 4.79% | -2.80pp | -0.23pp |

These material groups cover 99.99% of both periods. Applying Target source shares to Baseline source rates produces an 8.3272% counterfactual, effectively unchanged from the 8.3277% Baseline. Estimated composition effect is **+0.0007pp**; estimated within-source effect is **-3.2144pp**.

**ACQUISITION_MIX_EXPLANATION = REJECTED.** The main sources declined internally while the mix remained stable. This does not identify acquisition as a root cause.

## Device analysis

| Device | Baseline users | Baseline rate | Baseline share | Target users | Target rate | Target share | Rate change | Share change |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Desktop | 28,484 | 8.42% | 58.43% | 19,434 | 5.11% | 58.34% | -3.30pp | -0.09pp |
| Mobile | 19,178 | 8.15% | 39.34% | 13,099 | 5.08% | 39.32% | -3.07pp | -0.02pp |
| Tablet | 1,091 | 9.17% | 2.24% | 780 | 5.51% | 2.34% | -3.65pp | +0.10pp |

Applying Target device shares to Baseline device rates yields 8.3285%. The estimated composition effect is **+0.0008pp**, while the within-device effect is **-3.2164pp**.

**DEVICE_CONCENTRATION = REJECTED.** Desktop and mobile both declined while their shares were stable. Tablet follows the same direction but is not used as a primary conclusion because its sample is much smaller.

## First-session activation depth

The three primary buckets are mutually exclusive:

- `SHALLOW`: first session contains `session_start` and no `view_item`.
- `BROWSE`: first session contains `view_item` and no `add_to_cart`.
- `INTENT`: first session contains `add_to_cart`; later checkout or purchase may also occur.

No Baseline or Target users were unclassified.

| Bucket | Baseline users | Baseline rate | Baseline share | Target users | Target rate | Target share | Rate change | Share change |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SHALLOW | 38,545 | 6.51% | 79.06% | 28,263 | 4.21% | 84.84% | -2.30pp | +5.78pp |
| BROWSE | 7,025 | 13.91% | 14.41% | 4,151 | 8.94% | 12.46% | -4.97pp | -1.95pp |
| INTENT | 3,183 | 18.06% | 6.53% | 899 | 15.80% | 2.70% | -2.27pp | -3.83pp |

Two distinct effects are present:

1. **Composition effect:** users shifted toward SHALLOW. Holding Baseline bucket rates fixed, the Target mix implies 7.74%, a **-0.59pp** composition effect, or about 18.25% of the aggregate decline.
2. **Within-segment effect:** return rate fell inside every bucket, contributing approximately **-2.63pp**, or 81.75% of the aggregate decline.

**ACTIVATION_DEPTH_SHIFT = SUPPORTED as an observed contributor, not as a causal root cause.** Composition matters, but most of the decline remains within the buckets.

## Calendar context and recovery

The Target covers Christmas and New Year, and the following cohorts partially recover. This is temporally consistent with a temporary calendar-related component, but temporal alignment is not causal evidence.

**Calendar seasonality may contribute, but the current dataset cannot establish causality.**

## Data quality

- `first_visit` and `session_start` were present on every date from Baseline start through the final observation date.
- Minimum daily counts were 1,916 `first_visit` events and 2,289 `session_start` events.
- No right-censored cohort is included.
- The earlier `add_to_cart` anomaly ended before Baseline. There were no zero-volume `add_to_cart` dates in the 63-day validation range; the daily minimum was 229 events.
- Activation-depth comparison therefore uses a stable collection period.

## Evidence

- D7 return declined from 8.33% to 5.11% (-3.22pp) across large, fully observed cohorts.
- Post recovered to 6.90%, significantly above Target and significantly below Baseline.
- The decline begins on D1 and continues accumulating through D7.
- Acquisition and device composition were stable, while rates declined within every material source and both major devices.
- SHALLOW gained 5.78pp of user share and INTENT lost 3.83pp; this mix shift explains about 0.59pp.
- Within-activation-bucket declines explain about 2.63pp, so composition alone is insufficient.

## Hypotheses

- Calendar seasonality may contribute to the temporary component of the decline.
- Lower first-session activation depth may contribute to part of the aggregate risk.
- A broader period-specific factor may have reduced return propensity within acquisition, device, and activation segments.

These are plausible explanations, not established facts.

## Unknowns

- Whether Christmas or New Year timing caused the decline.
- Why return rates declined within every activation bucket.
- Whether obfuscated acquisition values conceal narrower source changes.
- Whether campaign, pricing, inventory, merchandising, UX, performance, consent, or identity-resolution changes occurred.
- Whether the pattern persists under longer retention windows or year-over-year controls.

## Recommended Agent investigation path

1. `VALIDATE_DATA` — require complete D7 windows and stable primary events.
2. `ANALYZE_RETENTION` — establish signal magnitude and sample size.
3. `CHECK_RETURN_TIMING` — separate D1, days 2–3, and days 4–7 contributions.
4. `CHECK_RECOVERY` — classify the Post behavior using the explicit recovery rule.
5. `CHECK_ACQUISITION` — reject mix explanation when shares are stable and material sources decline; stop further acquisition drill-down.
6. `CHECK_DEVICE` — reject concentration when desktop and mobile both decline; do not over-interpret tablet.
7. `CHECK_ACTIVATION_DEPTH` — quantify composition and within-bucket effects separately.
8. `STOP` — output Evidence, Hypotheses, and Unknowns with `ALLOWED_DIMENSIONS_EXHAUSTED`; do not promote association to causal root cause.

## Final Case 02 candidate

| Field | Value |
|---|---|
| Title | New-user 7-day return risk with partial recovery |
| Opportunity type | `LIFECYCLE_RISK` |
| Metric | New-user 7-day Return Rate |
| Baseline rate | 8.33% |
| Target rate | 5.11% |
| Delta | -3.22pp |
| Affected population | New users with `first_visit` from 2020-12-21 through 2021-01-03 |
| Risk pattern | `PARTIAL_RECOVERY` |
| Signal confidence | `HIGH` |
| Root-cause confidence | `LOW` |
| Recommended status | `NEEDS_EVIDENCE` |
| Recommended action type | `EVIDENCE_COLLECTION` |

**CASE_02_STATUS = SUITABLE**

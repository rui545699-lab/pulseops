# V0.2 Lifecycle Risk — Phase A Exploration

## 1. Metric definition

**New-user 7-day Return Rate** is the share of eligible new users who start at least one new session on day 1 through day 7 after their `first_visit` date.

- New user: the user’s first `first_visit` date.
- Eligible cohort: `first_visit_date <= 2021-01-24`, leaving a complete seven-day observation window through 2021-01-31.
- Returned within seven days: at least one `session_start` where `session_start_date > first_visit_date` and `session_start_date <= first_visit_date + 7 days`.
- A same-day `session_start` does not count as a return.
- Formula: `returned_users_7d / eligible_new_users`.

`view_item`, `add_to_cart`, and `purchase` counts below are supporting cohort context only; they are not part of the retention definition.

## 2. Data-quality checks

The primary retention metric passed data-quality validation.

- Source: `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
- Scan range: 2020-11-01 through 2021-01-31 (92 dates).
- `first_visit`: present on all 92 dates; minimum 1,520 users/day, median 2,668.
- `session_start`: present on all 92 dates; minimum 1,890 users/day, median 3,363.5.
- No primary-event collection break was detected.
- Cohorts after 2021-01-24 were excluded, so right-censored cohorts do not enter the comparison.
- The week of 2020-10-26 contains only 2020-11-01 in the scan and is marked partial; it is excluded from candidate selection.

Auxiliary-event caveat: `add_to_cart` had 18 zero-volume dates between 2020-11-02 and 2020-11-24. This does not affect the return-rate definition. The recommended baseline starts on 2020-11-30, after this anomaly, so the selected first-session activation comparison uses a clean interval.

## 3. Weekly cohort table

| Cohort week | Eligible new users | Returned users D7 | Return rate D7 | View item users D7 | Add to cart users D7 | Purchase users D7 | Note |
|---|---:|---:|---:|---:|---:|---:|---|
| 2020-10-26 | 1,946 | 119 | 6.12% | 410 | 0 | 9 | Partial week; excluded |
| 2020-11-02 | 16,500 | 1,500 | 9.09% | 3,860 | 0 | 136 | Full week |
| 2020-11-09 | 14,590 | 1,491 | 10.22% | 3,784 | 26 | 192 | Full week |
| 2020-11-16 | 16,906 | 1,747 | 10.33% | 4,636 | 407 | 217 | Full week |
| 2020-11-23 | 18,734 | 1,687 | 9.01% | 4,473 | 967 | 287 | Full week |
| 2020-11-30 | 21,195 | 2,045 | 9.65% | 5,559 | 1,906 | 412 | Baseline |
| 2020-12-07 | 27,558 | 2,015 | 7.31% | 5,503 | 1,816 | 462 | Baseline |
| 2020-12-14 | 24,221 | 1,593 | 6.58% | 4,825 | 1,335 | 341 | Transition week |
| 2020-12-21 | 17,013 | 897 | 5.27% | 2,928 | 604 | 124 | Target |
| 2020-12-28 | 16,300 | 806 | 4.94% | 2,357 | 421 | 68 | Target |
| 2021-01-04 | 22,458 | 1,454 | 6.47% | 3,316 | 662 | 116 | Full week |
| 2021-01-11 | 21,008 | 1,390 | 6.62% | 3,652 | 727 | 143 | Full week |
| 2021-01-18 | 20,220 | 1,553 | 7.68% | 4,899 | 808 | 293 | Full D7 window |

## 4. Candidate decline

A real, material lifecycle-risk signal exists. Weekly return rate moved from 9.65% on the 2020-11-30 cohort to 7.31%, 6.58%, 5.27%, and 4.94% in successive weeks before partially recovering in January. The candidate is therefore not based on a single low day or isolated week.

For the recommended windows, target minus baseline is **-3.22 percentage points**, or a **-38.61% relative change**. An approximate 95% confidence interval for the absolute change is **-3.56 to -2.87 percentage points**. Statistical clarity establishes the signal, not its cause.

## 5. Baseline / target recommendation

| Window | Cohort dates | Eligible users | Returned users D7 | Return rate D7 |
|---|---|---:|---:|---:|
| Baseline | 2020-11-30 through 2020-12-13 | 48,753 | 4,060 | 8.33% |
| Target | 2020-12-21 through 2021-01-03 | 33,313 | 1,703 | 5.11% |

**Delta: -3.22pp.**

Both windows contain two complete natural cohort weeks and have full D7 observation. The baseline begins after the `add_to_cart` anomaly and includes the already-weaker 2020-12-07 cohort, making the comparison conservative rather than selecting only the highest pre-decline weeks. The target uses two consecutive low weeks. The 2020-12-14 cohort remains visible as a transition week rather than being folded into either window.

## 6. Initial segment findings

### Acquisition source / medium

All material acquisition groups declined. Examples include direct from 8.60% to 5.13% (-3.47pp), Google organic from 8.33% to 5.32% (-3.01pp), Google CPC from 8.13% to 5.29% (-2.84pp), and the store referral from 7.81% to 5.02% (-2.79pp). Obfuscated `<Other>` groups also declined, but their hidden composition prevents a more specific interpretation.

### Device

The signal is not localized to one device: desktop declined from 8.42% to 5.11% (-3.31pp), mobile from 8.15% to 5.08% (-3.07pp), and tablet from 9.17% to 5.51% (-3.66pp).

### First-session activation depth

| Activation depth | Baseline users | Baseline rate | Target users | Target rate | Delta |
|---|---:|---:|---:|---:|---:|
| Reached add to cart | 3,192 | 18.08% | 900 | 15.78% | -2.30pp |
| Reached view item | 7,032 | 13.96% | 4,155 | 8.98% | -4.98pp |
| Shallow | 38,529 | 6.49% | 28,258 | 4.20% | -2.29pp |

Deeper first-session activation remains associated with higher return rates in both periods. The reached-view-item group has the largest observed decline. These are descriptive associations, not causal findings.

## 7. Evidence

- The selected target contains 33,313 eligible new users and 1,703 seven-day returners.
- Target return rate was 5.11% versus 8.33% in the conservative baseline, a -3.22pp change.
- Both target weeks were low (5.27% and 4.94%).
- `first_visit` and `session_start` were present on every scanned date, with no detected primary-event collection break.
- Declines appeared across every material acquisition and device segment examined.

## 8. Hypotheses

- Holiday-period intent or seasonality may contribute to lower return behavior.
- A change in new-user engagement quality may be associated with the decline, given weaker return rates among users who reached `view_item` as well as shallow users.
- Broad changes affecting multiple traffic sources and devices may be more plausible than a single-channel or single-device issue.

These are plausible explanations, not established facts.

## 9. Unknowns

- Whether the decline reflects holiday seasonality, campaign mix, merchandising, pricing, UX, or another external factor.
- Whether source values obfuscated as `<Other>` conceal meaningful acquisition changes.
- Whether consent, identity, or tracking changes altered cross-session user recognition without creating a visible event-volume break.
- Whether the pattern persists under longer return windows or year-over-year controls.

## 10. Productization assessment

The case is strong enough to productize as a bounded Lifecycle Risk example: the signal is material, covers two consecutive target cohorts, has large fully observed samples, and survives limited segmentation. Productization must preserve the evidence boundary: this is a detected and segmented risk, not a causal root cause, and holiday seasonality remains an important unknown.

**CASE_02_STATUS = SUITABLE**

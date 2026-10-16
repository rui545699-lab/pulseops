# V0.3 Positive Growth Candidate — Phase B Validation

`CASE_03_VALIDATION_STATUS = VALIDATED`

## Strict metric verification

Primary metric: distinct same-user, same-session checkout sessions with at least one `purchase` timestamp strictly after the first `begin_checkout` timestamp. A purchase before checkout never qualifies. The denominator is distinct qualifying-session keys with `begin_checkout`; the numerator is the subset with a strictly later purchase.

## Data quality

- No day-level zero-volume or <20%-of-median break is used as evidence of a tracking-definition change.
- begin_checkout zero-volume dates: 0; purchase zero-volume dates: 0.
- Auxiliary only: this metric is defined directly on begin_checkout and purchase, neither of which has an observed zero-volume date in the validation range.

## Weekly split

| Period | Dates | Checkout sessions | Purchase-after-checkout sessions | Rate (95% CI) | Before-checkout purchases | Multiple checkout sessions | Multiple purchase sessions |
| --- | --- | ---: | ---: | --- | ---: | ---: | ---: |
| Baseline Week 1 | 2020-11-23 to 2020-11-29 | 1,184 | 460 | 38.85% (36.12%–41.66%) | 0 | 428 | 119 |
| Baseline Week 2 | 2020-11-30 to 2020-12-06 | 1,408 | 586 | 41.62% (39.07%–44.21%) | 0 | 1,383 | 38 |
| Growth Week 1 | 2020-12-07 to 2020-12-13 | 1,549 | 759 | 49.00% (46.52%–51.49%) | 0 | 1,526 | 53 |
| Growth Week 2 | 2020-12-14 to 2020-12-20 | 1,001 | 545 | 54.45% (51.35%–57.51%) | 0 | 989 | 59 |
| Confirmation Week 1 | 2020-12-21 to 2020-12-27 | 411 | 232 | 56.45% (51.62%–61.16%) | 0 | 411 | 16 |
| Confirmation Week 2 | 2020-12-28 to 2021-01-03 | 259 | 137 | 52.90% (46.82%–58.89%) | 0 | 259 | 11 |

## Pooled and holdout results

| Period | Dates | Checkout sessions | Purchase-after-checkout sessions | Rate (95% CI) |
| --- | --- | ---: | ---: | --- |
| Baseline | 2020-11-23 to 2020-12-06 | 2,592 | 1,046 | 40.35% (38.48%–42.26%) |
| Growth | 2020-12-07 to 2020-12-20 | 2,550 | 1,304 | 51.14% (49.20%–53.07%) |
| Confirmation | 2020-12-21 to 2021-01-03 | 670 | 369 | 55.07% (51.29%–58.80%) |
| Holdout 1 | 2021-01-04 to 2021-01-17 | 792 | 386 | 48.74% (45.27%–52.22%) |
| Holdout 2 | 2021-01-18 to 2021-01-31 | 1,208 | 666 | 55.13% (52.32%–57.92%) |

## Expanded statistics

- growth_vs_baseline: Δ 10.78 pp; z=7.76; p=8.48e-15.
- confirmation_vs_baseline: Δ 14.72 pp; z=6.85; p=7.23e-12.
- holdout_1_vs_baseline: Δ 8.38 pp; z=4.18; p=2.93e-05.
- holdout_2_vs_baseline: Δ 14.78 pp; z=8.53; p=1.52e-17.
- holdout_1_vs_growth: Δ -2.40 pp; z=-1.18; p=0.238.
- holdout_2_vs_growth: Δ 4.00 pp; z=2.29; p=0.022.

Reproducibility: **REPRODUCED**. Deterministic status: **VALIDATED**.

## Broad-versus-segmented validation

### lifecycle

- Composition effect: +3.45 pp; within-segment effect: +7.33 pp.
- All lifecycle groups are shown.

| Segment | Baseline n / rate | Growth n / rate | Confirmation n / rate |
| --- | --- | --- | --- |
| new | 1,522 / 27.27% | 1,220 / 36.48% | 305 / 43.28% |
| returning | 1,070 / 58.97% | 1,330 / 64.59% | 365 / 64.93% |

### device

- Composition effect: -0.02 pp; within-segment effect: +10.80 pp.
- Desktop and mobile are shown; tablet is included only if each pooled period has at least 100 checkout sessions.

| Segment | Baseline n / rate | Growth n / rate | Confirmation n / rate |
| --- | --- | --- | --- |
| desktop | 1,511 / 38.91% | 1,482 / 51.82% | 367 / 52.59% |
| mobile | 1,021 / 42.12% | 1,021 / 50.73% | 282 / 57.45% |

### acquisition

- Composition effect: +0.65 pp; within-segment effect: +10.13 pp.
- Major acquisition groups are selected deterministically in descending pooled volume until they cover at least 80% of baseline, growth, and confirmation volume combined (displayed coverage: 84.57%). Small remaining groups are not interpreted individually.

| Segment | Baseline n / rate | Growth n / rate | Confirmation n / rate |
| --- | --- | --- | --- |
| google / organic | 749 / 37.65% | 717 / 47.28% | 177 / 53.11% |
| (direct) / (none) | 570 / 37.37% | 602 / 50.00% | 156 / 53.85% |
| <Other> / <Other> | 357 / 32.77% | 291 / 42.61% | 83 / 48.19% |
| (data deleted) / (data deleted) | 238 / 59.24% | 292 / 65.75% | 97 / 60.82% |
| shop.googlemerchandisestore.com / referral | 258 / 50.00% | 263 / 60.08% | 65 / 63.08% |

## Revenue / order-value context

| Period | Purchase events | Distinct transaction IDs | Repeated IDs | Revenue USD | Average order value USD |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline | 1,261 | 1,088 | 125 | 77425.00 | 71.16 |
| growth | 1,532 | 1,472 | 16 | 104619.00 | 71.07 |
| confirmation | 420 | 389 | 9 | 24618.00 | 63.29 |
| holdout_1 | 420 | 389 | 5 | 22275.00 | 57.26 |
| holdout_2 | 717 | 457 | 6 | 29883.00 | 65.39 |

## Evidence

- The strict pooled conversion rate was 40.35% in baseline, 51.14% in growth, and 55.07% in confirmation.
- Both growth weeks exceeded the pooled baseline rate, and both confirmation weeks exceeded it as well: True / True.
- Holdout 1 was 48.74% and Holdout 2 was 55.13% under the same strict session definition.
- Numerator inflation is bounded by distinct-session counting; repeated purchase events and transaction identifiers are reported separately and do not create extra converting sessions.
- The major device and acquisition tables report observed group rates and a non-causal mix/within decomposition.

## Hypotheses

- Promotion or pricing context may be associated with the observed lift.
- Checkout UX, payment experience, inventory, merchandising, or calendar context may be associated with the observed lift.
- These are plausible explanations only; the public GA4 behavioral data does not establish any one of them as a cause.

## Unknowns

- Promotion configuration, pricing changes, holiday campaigns, inventory changes, checkout UX changes, and payment changes are not available in this dataset.
- GA4 data cannot establish causal attribution or prove that the observed lift will recur under a future intervention.
- The obfuscated acquisition labels and public-sample context limit channel-level interpretation.

## Product interpretation

Conceptual Golden Case: **Positive Growth Opportunity — Broad Checkout→Purchase Lift**. This means a validated behavioral signal with broad observed support, not a proven growth mechanism.

Proposed only: retain separate Growth Signal Confidence (measurement strength and materiality) and Reproducibility Confidence (confirmation and independent-holdout persistence). Do not implement or freeze product enums in Phase B.

Recommended safe next action: **REPLICATION_TEST**.

No application code, agent behavior, persistence, API, or frontend was changed by this validation.

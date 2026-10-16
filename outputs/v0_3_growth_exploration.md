# V0.3 Positive Growth Opportunity — Phase A Exploration

`CASE_03_STATUS = SUITABLE`

## 1. Scope and metric definition

This is a read-only exploration of `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*` from 2020-11-01 through 2021-01-31. It uses full Monday–Sunday weeks only and evaluates the pre-defined metrics below. It does not change product code, infer causal root cause, or recommend an intervention.

- A. Strict same-user, same-session `view_item → add_to_cart`.
- B. Strict same-user, same-session `add_to_cart → begin_checkout`.
- C. Strict same-user, same-session `begin_checkout → purchase`.
- D. `session_start → purchase`.
- E. New-user 7-day Return Rate.
- F. First-session Activation Depth distribution: shallow, browse, and intent shares. Only the intent share is a pre-specified positive-direction candidate component.

Candidate rule: two baseline weeks → two consecutive growth weeks → two confirmation weeks. A candidate requires at least 100 eligible observations in each period, both growth weeks above the aggregate baseline rate, and statistically positive growth and confirmation versus baseline (`p < 0.05`, pooled two-proportion z test). Rate intervals are 95% Wilson intervals.

## 2. Data-quality checks

- Status: **PASS_WITH_AUXILIARY_LIMITATION**.
- Dates checked: 92.
- Zero-volume dates: first_visit=0; session_start=0; view_item=0; begin_checkout=0; purchase=0.
- add_to_cart zero-volume dates: 18. Cart-dependent metrics and activation-depth distribution are excluded before 2020-11-30.
- Primary event coverage is continuous. add_to_cart has an early zero-volume interval; metrics whose denominator or numerator requires add_to_cart exclude weeks before 2020-11-30.
- Only first_visit cohorts through 2021-01-24 are used, so every retained cohort has seven follow-up days through 2021-01-31.
- Partial boundary weeks excluded: 2020-10-26, 2021-01-25.

## 3. Weekly metric scan

| Metric | Week | Eligible | Successes | Rate (95% CI) | Candidate reliable |
| --- | --- | ---: | ---: | --- | --- |
| ACTIVATION_DEPTH_BROWSE | 2020-11-02 | 16,500 | 3,048 | 18.47% (17.89–19.07%) | no |
| ACTIVATION_DEPTH_BROWSE | 2020-11-09 | 14,591 | 2,908 | 19.93% (19.29–20.59%) | no |
| ACTIVATION_DEPTH_BROWSE | 2020-11-16 | 16,906 | 3,546 | 20.97% (20.37–21.60%) | no |
| ACTIVATION_DEPTH_BROWSE | 2020-11-23 | 18,734 | 3,009 | 16.06% (15.54–16.59%) | no |
| ACTIVATION_DEPTH_BROWSE | 2020-11-30 | 21,195 | 3,402 | 16.05% (15.56–16.55%) | yes |
| ACTIVATION_DEPTH_BROWSE | 2020-12-07 | 27,558 | 3,421 | 12.41% (12.03–12.81%) | yes |
| ACTIVATION_DEPTH_BROWSE | 2020-12-14 | 24,221 | 3,273 | 13.51% (13.09–13.95%) | yes |
| ACTIVATION_DEPTH_BROWSE | 2020-12-21 | 17,013 | 2,234 | 13.13% (12.63–13.65%) | yes |
| ACTIVATION_DEPTH_BROWSE | 2020-12-28 | 16,300 | 1,847 | 11.33% (10.85–11.83%) | yes |
| ACTIVATION_DEPTH_BROWSE | 2021-01-04 | 22,458 | 2,462 | 10.96% (10.56–11.38%) | yes |
| ACTIVATION_DEPTH_BROWSE | 2021-01-11 | 21,008 | 2,700 | 12.85% (12.41–13.31%) | yes |
| ACTIVATION_DEPTH_BROWSE | 2021-01-18 | 20,220 | 3,871 | 19.14% (18.61–19.69%) | yes |
| ACTIVATION_DEPTH_INTENT | 2020-11-02 | 16,500 | 568 | 3.44% (3.17–3.73%) | no |
| ACTIVATION_DEPTH_INTENT | 2020-11-09 | 14,591 | 632 | 4.33% (4.01–4.67%) | no |
| ACTIVATION_DEPTH_INTENT | 2020-11-16 | 16,906 | 785 | 4.64% (4.34–4.97%) | no |
| ACTIVATION_DEPTH_INTENT | 2020-11-23 | 18,734 | 1,161 | 6.20% (5.86–6.55%) | no |
| ACTIVATION_DEPTH_INTENT | 2020-11-30 | 21,195 | 1,744 | 8.23% (7.87–8.61%) | yes |
| ACTIVATION_DEPTH_INTENT | 2020-12-07 | 27,558 | 1,672 | 6.07% (5.79–6.36%) | yes |
| ACTIVATION_DEPTH_INTENT | 2020-12-14 | 24,221 | 1,196 | 4.94% (4.67–5.22%) | yes |
| ACTIVATION_DEPTH_INTENT | 2020-12-21 | 17,013 | 576 | 3.39% (3.12–3.67%) | yes |
| ACTIVATION_DEPTH_INTENT | 2020-12-28 | 16,300 | 401 | 2.46% (2.23–2.71%) | yes |
| ACTIVATION_DEPTH_INTENT | 2021-01-04 | 22,458 | 607 | 2.70% (2.50–2.92%) | yes |
| ACTIVATION_DEPTH_INTENT | 2021-01-11 | 21,008 | 667 | 3.17% (2.95–3.42%) | yes |
| ACTIVATION_DEPTH_INTENT | 2021-01-18 | 20,220 | 712 | 3.52% (3.28–3.78%) | yes |
| ACTIVATION_DEPTH_SHALLOW | 2020-11-02 | 16,500 | 12,884 | 78.08% (77.45–78.71%) | no |
| ACTIVATION_DEPTH_SHALLOW | 2020-11-09 | 14,591 | 11,051 | 75.74% (75.04–76.43%) | no |
| ACTIVATION_DEPTH_SHALLOW | 2020-11-16 | 16,906 | 12,575 | 74.38% (73.72–75.03%) | no |
| ACTIVATION_DEPTH_SHALLOW | 2020-11-23 | 18,734 | 14,564 | 77.74% (77.14–78.33%) | no |
| ACTIVATION_DEPTH_SHALLOW | 2020-11-30 | 21,195 | 16,049 | 75.72% (75.14–76.29%) | yes |
| ACTIVATION_DEPTH_SHALLOW | 2020-12-07 | 27,558 | 22,465 | 81.52% (81.06–81.97%) | yes |
| ACTIVATION_DEPTH_SHALLOW | 2020-12-14 | 24,221 | 19,752 | 81.55% (81.06–82.03%) | yes |
| ACTIVATION_DEPTH_SHALLOW | 2020-12-21 | 17,013 | 14,203 | 83.48% (82.92–84.03%) | yes |
| ACTIVATION_DEPTH_SHALLOW | 2020-12-28 | 16,300 | 14,052 | 86.21% (85.67–86.73%) | yes |
| ACTIVATION_DEPTH_SHALLOW | 2021-01-04 | 22,458 | 19,389 | 86.33% (85.88–86.78%) | yes |
| ACTIVATION_DEPTH_SHALLOW | 2021-01-11 | 21,008 | 17,641 | 83.97% (83.47–84.46%) | yes |
| ACTIVATION_DEPTH_SHALLOW | 2021-01-18 | 20,220 | 15,637 | 77.33% (76.75–77.91%) | yes |
| ACTIVATION_SESSION_ID_COVERAGE | 2020-11-02 | 16,500 | 16,500 | 100.00% (99.98–100.00%) | yes |
| ACTIVATION_SESSION_ID_COVERAGE | 2020-11-09 | 14,591 | 14,591 | 100.00% (99.97–100.00%) | yes |
| ACTIVATION_SESSION_ID_COVERAGE | 2020-11-16 | 16,906 | 16,906 | 100.00% (99.98–100.00%) | yes |
| ACTIVATION_SESSION_ID_COVERAGE | 2020-11-23 | 18,734 | 18,734 | 100.00% (99.98–100.00%) | yes |
| ACTIVATION_SESSION_ID_COVERAGE | 2020-11-30 | 21,195 | 21,195 | 100.00% (99.98–100.00%) | yes |
| ACTIVATION_SESSION_ID_COVERAGE | 2020-12-07 | 27,558 | 27,558 | 100.00% (99.99–100.00%) | yes |
| ACTIVATION_SESSION_ID_COVERAGE | 2020-12-14 | 24,221 | 24,221 | 100.00% (99.98–100.00%) | yes |
| ACTIVATION_SESSION_ID_COVERAGE | 2020-12-21 | 17,013 | 17,013 | 100.00% (99.98–100.00%) | yes |
| ACTIVATION_SESSION_ID_COVERAGE | 2020-12-28 | 16,300 | 16,300 | 100.00% (99.98–100.00%) | yes |
| ACTIVATION_SESSION_ID_COVERAGE | 2021-01-04 | 22,458 | 22,458 | 100.00% (99.98–100.00%) | yes |
| ACTIVATION_SESSION_ID_COVERAGE | 2021-01-11 | 21,008 | 21,008 | 100.00% (99.98–100.00%) | yes |
| ACTIVATION_SESSION_ID_COVERAGE | 2021-01-18 | 20,220 | 20,220 | 100.00% (99.98–100.00%) | yes |
| ADD_TO_CART_TO_BEGIN_CHECKOUT | 2020-11-02 | 0 | 0 | n/a (n/a) | no |
| ADD_TO_CART_TO_BEGIN_CHECKOUT | 2020-11-09 | 0 | 0 | n/a (n/a) | no |
| ADD_TO_CART_TO_BEGIN_CHECKOUT | 2020-11-16 | 529 | 201 | 38.00% (33.96–42.20%) | no |
| ADD_TO_CART_TO_BEGIN_CHECKOUT | 2020-11-23 | 1,208 | 456 | 37.75% (35.06–40.52%) | no |
| ADD_TO_CART_TO_BEGIN_CHECKOUT | 2020-11-30 | 2,605 | 962 | 36.93% (35.10–38.80%) | yes |
| ADD_TO_CART_TO_BEGIN_CHECKOUT | 2020-12-07 | 2,657 | 1,020 | 38.39% (36.56–40.25%) | yes |
| ADD_TO_CART_TO_BEGIN_CHECKOUT | 2020-12-14 | 2,071 | 694 | 33.51% (31.51–35.57%) | yes |
| ADD_TO_CART_TO_BEGIN_CHECKOUT | 2020-12-21 | 972 | 288 | 29.63% (26.84–32.58%) | yes |
| ADD_TO_CART_TO_BEGIN_CHECKOUT | 2020-12-28 | 643 | 185 | 28.77% (25.41–32.39%) | yes |
| ADD_TO_CART_TO_BEGIN_CHECKOUT | 2021-01-04 | 943 | 226 | 23.97% (21.35–26.79%) | yes |
| ADD_TO_CART_TO_BEGIN_CHECKOUT | 2021-01-11 | 1,073 | 327 | 30.48% (27.79–33.30%) | yes |
| ADD_TO_CART_TO_BEGIN_CHECKOUT | 2021-01-18 | 1,187 | 474 | 39.93% (37.18–42.75%) | yes |
| BEGIN_CHECKOUT_TO_PURCHASE | 2020-11-02 | 872 | 249 | 28.55% (25.66–31.64%) | yes |
| BEGIN_CHECKOUT_TO_PURCHASE | 2020-11-09 | 1,034 | 337 | 32.59% (29.80–35.51%) | yes |
| BEGIN_CHECKOUT_TO_PURCHASE | 2020-11-16 | 1,041 | 372 | 35.73% (32.88–38.69%) | yes |
| BEGIN_CHECKOUT_TO_PURCHASE | 2020-11-23 | 1,184 | 460 | 38.85% (36.12–41.66%) | yes |
| BEGIN_CHECKOUT_TO_PURCHASE | 2020-11-30 | 1,408 | 586 | 41.62% (39.07–44.21%) | yes |
| BEGIN_CHECKOUT_TO_PURCHASE | 2020-12-07 | 1,549 | 759 | 49.00% (46.52–51.49%) | yes |
| BEGIN_CHECKOUT_TO_PURCHASE | 2020-12-14 | 1,001 | 545 | 54.45% (51.35–57.51%) | yes |
| BEGIN_CHECKOUT_TO_PURCHASE | 2020-12-21 | 411 | 232 | 56.45% (51.62–61.16%) | yes |
| BEGIN_CHECKOUT_TO_PURCHASE | 2020-12-28 | 259 | 137 | 52.90% (46.82–58.89%) | yes |
| BEGIN_CHECKOUT_TO_PURCHASE | 2021-01-04 | 339 | 160 | 47.20% (41.94–52.51%) | yes |
| BEGIN_CHECKOUT_TO_PURCHASE | 2021-01-11 | 453 | 226 | 49.89% (45.31–54.48%) | yes |
| BEGIN_CHECKOUT_TO_PURCHASE | 2021-01-18 | 660 | 372 | 56.36% (52.55–60.10%) | yes |
| NEW_USER_7D_RETURN | 2020-11-02 | 16,500 | 1,500 | 9.09% (8.66–9.54%) | yes |
| NEW_USER_7D_RETURN | 2020-11-09 | 14,591 | 1,492 | 10.23% (9.74–10.73%) | yes |
| NEW_USER_7D_RETURN | 2020-11-16 | 16,906 | 1,747 | 10.33% (9.88–10.80%) | yes |
| NEW_USER_7D_RETURN | 2020-11-23 | 18,734 | 1,687 | 9.01% (8.60–9.42%) | yes |
| NEW_USER_7D_RETURN | 2020-11-30 | 21,195 | 2,045 | 9.65% (9.26–10.05%) | yes |
| NEW_USER_7D_RETURN | 2020-12-07 | 27,558 | 2,015 | 7.31% (7.01–7.63%) | yes |
| NEW_USER_7D_RETURN | 2020-12-14 | 24,221 | 1,593 | 6.58% (6.27–6.90%) | yes |
| NEW_USER_7D_RETURN | 2020-12-21 | 17,013 | 897 | 5.27% (4.95–5.62%) | yes |
| NEW_USER_7D_RETURN | 2020-12-28 | 16,300 | 806 | 4.94% (4.62–5.29%) | yes |
| NEW_USER_7D_RETURN | 2021-01-04 | 22,458 | 1,454 | 6.47% (6.16–6.80%) | yes |
| NEW_USER_7D_RETURN | 2021-01-11 | 21,008 | 1,390 | 6.62% (6.29–6.96%) | yes |
| NEW_USER_7D_RETURN | 2021-01-18 | 20,220 | 1,553 | 7.68% (7.32–8.06%) | yes |
| SESSION_START_TO_PURCHASE | 2020-11-02 | 24,672 | 249 | 1.01% (0.89–1.14%) | yes |
| SESSION_START_TO_PURCHASE | 2020-11-09 | 22,226 | 338 | 1.52% (1.37–1.69%) | yes |
| SESSION_START_TO_PURCHASE | 2020-11-16 | 25,632 | 372 | 1.45% (1.31–1.61%) | yes |
| SESSION_START_TO_PURCHASE | 2020-11-23 | 26,912 | 460 | 1.71% (1.56–1.87%) | yes |
| SESSION_START_TO_PURCHASE | 2020-11-30 | 30,764 | 587 | 1.91% (1.76–2.07%) | yes |
| SESSION_START_TO_PURCHASE | 2020-12-07 | 38,125 | 759 | 1.99% (1.86–2.14%) | yes |
| SESSION_START_TO_PURCHASE | 2020-12-14 | 33,080 | 545 | 1.65% (1.52–1.79%) | yes |
| SESSION_START_TO_PURCHASE | 2020-12-21 | 21,840 | 232 | 1.06% (0.93–1.21%) | yes |
| SESSION_START_TO_PURCHASE | 2020-12-28 | 20,245 | 137 | 0.68% (0.57–0.80%) | yes |
| SESSION_START_TO_PURCHASE | 2021-01-04 | 28,715 | 160 | 0.56% (0.48–0.65%) | yes |
| SESSION_START_TO_PURCHASE | 2021-01-11 | 27,389 | 226 | 0.83% (0.72–0.94%) | yes |
| SESSION_START_TO_PURCHASE | 2021-01-18 | 27,120 | 372 | 1.37% (1.24–1.52%) | yes |
| VIEW_ITEM_TO_ADD_TO_CART | 2020-11-02 | 5,450 | 0 | 0.00% (0.00–0.07%) | no |
| VIEW_ITEM_TO_ADD_TO_CART | 2020-11-09 | 5,471 | 0 | 0.00% (0.00–0.07%) | no |
| VIEW_ITEM_TO_ADD_TO_CART | 2020-11-16 | 6,557 | 457 | 6.97% (6.38–7.61%) | no |
| VIEW_ITEM_TO_ADD_TO_CART | 2020-11-23 | 6,108 | 1,051 | 17.21% (16.28–18.17%) | no |
| VIEW_ITEM_TO_ADD_TO_CART | 2020-11-30 | 7,719 | 2,251 | 29.16% (28.16–30.19%) | yes |
| VIEW_ITEM_TO_ADD_TO_CART | 2020-12-07 | 7,975 | 2,289 | 28.70% (27.72–29.71%) | yes |
| VIEW_ITEM_TO_ADD_TO_CART | 2020-12-14 | 6,974 | 1,705 | 24.45% (23.45–25.47%) | yes |
| VIEW_ITEM_TO_ADD_TO_CART | 2020-12-21 | 4,046 | 816 | 20.17% (18.96–21.43%) | yes |
| VIEW_ITEM_TO_ADD_TO_CART | 2020-12-28 | 3,063 | 535 | 17.47% (16.16–18.85%) | yes |
| VIEW_ITEM_TO_ADD_TO_CART | 2021-01-04 | 4,357 | 784 | 17.99% (16.88–19.16%) | yes |
| VIEW_ITEM_TO_ADD_TO_CART | 2021-01-11 | 4,790 | 914 | 19.08% (17.99–20.22%) | yes |
| VIEW_ITEM_TO_ADD_TO_CART | 2021-01-18 | 6,399 | 1,004 | 15.69% (14.82–16.60%) | yes |

## 4. Candidate ranking

| Rank | Metric | Baseline | Growth | Confirmation | Growth Δ pp / p | Confirmation Δ pp / p | Reproducibility | Main limitation |
| ---: | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | BEGIN_CHECKOUT_TO_PURCHASE | 40.35% (2,592) | 51.14% (2,550) | 55.07% (670) | 10.78 / 8.48e-15 | 14.72 / 7.23e-12 | REPRODUCED | No gate failure; descriptive study only. |
| 2 | BEGIN_CHECKOUT_TO_PURCHASE | 37.39% (2,225) | 45.49% (2,957) | 55.03% (1,412) | 8.09 / 5.16e-09 | 17.64 / 1.7e-25 | REPRODUCED | No gate failure; descriptive study only. |
| 3 | BEGIN_CHECKOUT_TO_PURCHASE | 30.75% (1,906) | 37.39% (2,225) | 45.49% (2,957) | 6.65 / 7.24e-06 | 14.74 / 1.11e-24 | REPRODUCED | No gate failure; descriptive study only. |
| 4 | SESSION_START_TO_PURCHASE | 1.25% (46,898) | 1.58% (52,544) | 1.95% (68,889) | 0.33 / 1.06e-05 | 0.70 / 5.43e-20 | REPRODUCED | No gate failure; descriptive study only. |
| 5 | BEGIN_CHECKOUT_TO_PURCHASE | 34.17% (2,075) | 40.35% (2,592) | 51.14% (2,550) | 6.19 / 1.45e-05 | 16.97 / 5.43e-31 | REPRODUCED | No gate failure; descriptive study only. |
| 6 | SESSION_START_TO_PURCHASE | 1.48% (47,858) | 1.82% (57,676) | 1.83% (71,205) | 0.33 / 2.75e-05 | 0.35 / 5.05e-06 | REPRODUCED | No gate failure; descriptive study only. |

## 5. Baseline / growth / confirmation recommendation

Selected candidate: **Strict same-user, same-session Begin Checkout → Purchase** (rank 1).

| Period | Full weeks | Eligible | Successes | Rate (95% CI) |
| --- | --- | ---: | ---: | --- |
| Baseline | 2020-11-23 to 2020-12-06 | 2,592 | 1,046 | 40.35% (38.48–42.26%) |
| Growth | 2020-12-07 to 2020-12-20 | 2,550 | 1,304 | 51.14% (49.20–53.07%) |
| Confirmation | 2020-12-21 to 2021-01-03 | 670 | 369 | 55.07% (51.29–58.80%) |

Growth vs baseline: **+10.78 pp**, z=7.76, p=8.48e-15.
Confirmation vs baseline: **+14.72 pp**, z=6.85, p=7.23e-12.
Reproducibility: **REPRODUCED**. The confirmation period remains above baseline; it is not a causal replication experiment.

## 6. Initial segment localization

- Classification: **BROAD**.
- Scope: same-session metric; lifecycle is based on whether the investigated session contains first_visit.
- Category: Not evaluated: category is not required to assess this metric's initial localization and would add high-cardinality exploratory noise.
- Composition interpretation: Composition and within-segment effects are reported per dimension; neither is a causal attribution.
- Within-segment interpretation: A positive within-segment comparison indicates an observed rate change after holding that dimension's observed mix fixed; it does not identify a mechanism.

### lifecycle

Observed composition effect: +3.44 pp; observed within-segment effect: +7.35 pp.

| Segment | Baseline n / rate | Growth n / rate | Mix share (growth) | Within Δ pp | p-value |
| --- | --- | --- | ---: | ---: | ---: |
| new | 1,522 / 27.27% | 1,220 / 36.48% | 47.88% | 9.21 | 2.41e-07 |
| returning | 1,070 / 58.97% | 1,328 / 64.68% | 52.12% | 5.71 | 0.00415 |

### device

Observed composition effect: -0.02 pp; observed within-segment effect: +10.80 pp.

| Segment | Baseline n / rate | Growth n / rate | Mix share (growth) | Within Δ pp | p-value |
| --- | --- | --- | ---: | ---: | ---: |
| desktop | 1,511 / 38.91% | 1,481 / 51.86% | 58.12% | 12.94 | 1.16e-12 |
| mobile | 1,021 / 42.12% | 1,020 / 50.78% | 40.03% | 8.67 | 8.63e-05 |
| tablet | 60 / 46.67% | 47 / 38.30% | 1.84% | -8.37 | 0.385 |

### acquisition

Observed composition effect: +0.65 pp; observed within-segment effect: +10.13 pp.

| Segment | Baseline n / rate | Growth n / rate | Mix share (growth) | Within Δ pp | p-value |
| --- | --- | --- | ---: | ---: | ---: |
| (data deleted) / (data deleted) | 238 / 59.24% | 292 / 65.75% | 11.46% | 6.51 | 0.123 |
| (data deleted) / referral | 0 / 40.35% | 0 / n/a | 0.00% | n/a | n/a |
| (direct) / (none) | 570 / 37.37% | 601 / 50.08% | 23.59% | 12.71 | 1.17e-05 |
| <Other> / (data deleted) | 5 / 60.00% | 5 / 40.00% | 0.20% | -20.00 | 0.527 |
| <Other> / <Other> | 357 / 32.77% | 291 / 42.61% | 11.42% | 9.84 | 0.00995 |
| <Other> / cpc | 0 / 40.35% | 0 / n/a | 0.00% | n/a | n/a |
| <Other> / organic | 58 / 32.76% | 50 / 60.00% | 1.96% | 27.24 | 0.00458 |
| <Other> / referral | 256 / 41.80% | 240 / 47.92% | 9.42% | 6.12 | 0.171 |
| google / cpc | 101 / 34.65% | 90 / 47.78% | 3.53% | 13.12 | 0.0655 |
| google / organic | 749 / 37.65% | 716 / 47.35% | 28.10% | 9.70 | 0.000174 |
| shop.googlemerchandisestore.com / referral | 258 / 50.00% | 263 / 60.08% | 10.32% | 10.08 | 0.0208 |

## 7. Evidence

- Strict same-user, same-session Begin Checkout → Purchase increased from 40.35% in the baseline to 51.14% across two consecutive growth weeks.
- The confirmation period was 55.07%, still above the baseline with a two-sided pooled proportion-test p-value of 7.22923e-12.
- The selected comparison uses at least 670 eligible observations in each two-week period and excludes partial boundary weeks.
- The scan used only pre-specified metrics and a deterministic six-week (baseline → growth → confirmation) window rule.

## 8. Hypotheses

- Observed within-segment change or traffic composition may be associated with the increase; the decomposition does not establish why the metric changed.
- The persisted improvement may be compatible with a repeatable opportunity, but only a separate replication or controlled test could distinguish mechanism from temporal coincidence.

## 9. Unknowns

- Whether campaigns, merchandising, pricing, inventory, seasonality, product experience, or measurement conditions caused the observed change.
- Whether the pattern will recur in an independent later period or outside this obfuscated public sample.
- Whether dimensions not evaluated in this bounded Phase A scan would alter the descriptive localization.

## 10. Productization assessment

The candidate is strong enough to retain as a real-data Phase A opportunity candidate because the increase is material, statistically supported, persists across two growth weeks, and remains above baseline in the pre-specified confirmation period.

It is not ready for causal productization: the analysis does not establish a cause, seasonality and commercial context remain unmeasured, and a separate replication or controlled-scale evaluation would be needed before action selection.

## 11. Boundary

This is a descriptive, read-only exploration. No causal root cause, intervention recommendation, production enum, or product logic is asserted or changed.

Suggested future evidence: REPLICATION_TEST: reproduce the observed window on an independent fully observed period before considering a controlled scale test; do not infer an intervention from this descriptive scan.

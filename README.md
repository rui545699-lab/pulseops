# PulseOps — Milestone 1 Analytics Backend

PulseOps is a deterministic analytics layer for investigating user-operations
signals in the public GA4 ecommerce sample. This milestone intentionally contains
no frontend, LLM, LangGraph, RAG, multi-agent, campaign, or experimentation code.

## What is implemented

- `validate_data`: checks event availability, observation-window completeness,
  minimum sample size, and the known cart-vs-checkout collection anomaly.
- `scan_metrics`: scans strict session View→Cart, Cart→Checkout, and
  Checkout→Purchase conversion.
- `analyze_funnel`: enforces the same `user_pseudo_id`, same `ga_session_id`, and
  strictly increasing event timestamps.
- `compare_segments`: compares lifecycle, device, acquisition, and item category,
  suppressing precise rates/deltas when either period is below the sample floor.
- Evidence / Hypothesis / Unknown boundaries and a conservative Case 01 assessment.

## Setup

Requires Python 3.11 or later.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

For live BigQuery calls, set `GOOGLE_CLOUD_PROJECT` and authenticate with Google
Application Default Credentials. Credentials are never stored in this repository.

```powershell
gcloud auth application-default login
uvicorn pulseops.backend.main:app --reload
```

The dataset is
`bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`. Query dates are
passed as BigQuery parameters; event names are validated before SQL generation.

## Offline verification

The default tests do not contact Google Cloud and do not require credentials:

```powershell
python -m pytest
python -m compileall -q pulseops tests
```

The Case 01 fixture reproduces the verified 2020-12-07–13 baseline and
2020-12-21–27 target interpretation. Live BigQuery execution is deliberately an
optional integration concern.

## Manual live integration verification

Live verification is separate from ordinary `pytest`, so missing cloud credentials
never break the offline suite. Configure ADC and a billing project, then run:

```powershell
$env:GOOGLE_CLOUD_PROJECT = "your-gcp-project-id"
python -m scripts.verify_case_01 --output outputs/case_01_live.json
```

Alternatively pass `--project your-gcp-project-id`. The command queries the public
GA4 dataset, applies the New User filter to the Device, Acquisition, and Category
drill-downs, compares live rates with the immutable fixture using a 0.15pp default
tolerance, and exits non-zero on mismatch. Without a project or ADC it prints a
clear setup message without changing the offline test result.


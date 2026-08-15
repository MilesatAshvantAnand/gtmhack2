# Company List Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrich all 40,188 rows of `~/Downloads/ZenABM Lists:Outreach/Raw - Company List - June 26.csv` with LinkedIn Ad Library signals (one API call per company), writing one row per company to `data/enriched/company_list_enriched.csv` that keeps every original raw column plus the derived signals — updating and flushing to disk in real time so partial progress is never lost, resumable across daily runs.

**Architecture:** One new script (`enrich_companies.py`) built on two existing, unmodified Layer-2 modules (`core/client.py`, `core/schema.py`) plus one restored module (`core/linkedin_signals.py`, recovered from git history where it was later repurposed for a different, ZenABM-model-based skill). No SQLite, no checkpoint file — resume works by reading which `_row_index` values already exist in the output CSV.

**Tech Stack:** Python 3.9, `requests`, `pydantic` v2, `pytest`, `tqdm` (new dependency), the project's existing `venv`.

## Global Constraints

- Exactly **one API call per company** — `core/client.py`'s `search()` (single page, `start=0, count=25`), never `iter_ads()`. No pagination.
- Default daily budget: `--max-calls 950` (headroom below the 1,000/day quota — `constraints.md §6`).
- `data/enriched/` output — already covered by the existing `data/**` gitignore rule.
- Every row is written and flushed to disk immediately after processing — never buffered/batched in memory.
- `core/signals.py` (the live, ZenABM-model version powering the shipped `abm-competitor-intel` skill) must not be touched.
- Full spec: `docs/superpowers/specs/2026-07-26-company-list-enrichment-design.md`.

---

### Task 1: Restore the raw-LinkedIn signals engine

**Files:**
- Create: `core/linkedin_signals.py`
- Create: `tests/test_linkedin_signals.py`

**Interfaces:**
- Produces: `core.linkedin_signals.compute_company_signals(ads: Sequence[AdElement], now_ms: int, total_ads: Optional[int] = None) -> Dict[str, object]` and `core.linkedin_signals.linkedin_company_id(ad: AdElement) -> Optional[str]` — both consumed by Task 3.

- [ ] **Step 1: Restore the module from git history**

```bash
git show 31fbbff~1:core/signals.py > core/linkedin_signals.py
```

This is a pure restoration — the file only imports `from core.schema import AdElement`, and `core/schema.py` has not changed since that commit (verified: `git diff 31fbbff~1 HEAD -- core/schema.py` is empty). No edits needed to the module itself.

- [ ] **Step 2: Restore the test file, updating only its import**

```bash
git show 31fbbff~1:tests/test_core_signals.py > tests/test_linkedin_signals.py
```

Then edit `tests/test_linkedin_signals.py`: change the line

```python
from core import signals
```

to

```python
from core import linkedin_signals as signals
```

This is the only change — every other line (`signals.impression_data_coverage(...)`, etc.) stays as-is since the alias keeps the rest of the file working unmodified.

- [ ] **Step 3: Run the restored tests to confirm they pass unmodified**

Run: `venv/bin/python -m pytest tests/test_linkedin_signals.py -v`
Expected: all tests PASS (this file passed before it was retired in commit `d4b27e4`; the only change since is the import alias, so it must still pass against the unchanged `core/schema.py` and the unchanged restored `core/linkedin_signals.py`).

- [ ] **Step 4: Commit**

```bash
git add core/linkedin_signals.py tests/test_linkedin_signals.py
git commit -m "Restore raw-LinkedIn signals engine as core/linkedin_signals.py

Recovers the pre-ZenABM-adaptation core/signals.py (last present at
31fbbff~1) under a new name so it doesn't collide with the live,
ZenABM-model version that powers the abm-competitor-intel skill. Needed
to compute tier-gated signals from raw core/client.py + core/schema.py
data for the 40K-company enrichment pipeline."
```

---

### Task 2: CSV I/O layer — load raw companies, track resume state

**Files:**
- Create: `enrich_companies.py` (column schemas + `load_companies` + `load_done_row_indices` only in this task)
- Test: `tests/test_enrich_companies_io.py`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `RAW_COLS: List[str]`, `ENRICHED_COLS: List[str]`, `OUTPUT_COLS: List[str]` (module-level constants), `load_companies(csv_path: str, limit: Optional[int] = None) -> List[Dict[str, str]]` (each dict has every key in `RAW_COLS` plus `"_row_index": int`), `load_done_row_indices(out_csv: Path) -> Set[int]` — all consumed by Task 4's `main()`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_enrich_companies_io.py`:

```python
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from enrich_companies import load_companies, load_done_row_indices, RAW_COLS, OUTPUT_COLS


def _write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RAW_COLS)
        writer.writeheader()
        for row in rows:
            writer.writerow({**{c: "" for c in RAW_COLS}, **row})


def test_load_companies_tags_row_index_and_keeps_raw_columns(tmp_path):
    csv_path = tmp_path / "companies.csv"
    _write_csv(csv_path, [
        {"Name": "Acme", "Linkedin Company Id": "12345"},
        {"Name": "Beta", "Linkedin Company Id": "-999"},
    ])

    companies = load_companies(str(csv_path))

    assert len(companies) == 2
    assert companies[0]["_row_index"] == 0
    assert companies[0]["Name"] == "Acme"
    assert companies[0]["Linkedin Company Id"] == "12345"
    assert companies[1]["_row_index"] == 1


def test_load_companies_respects_limit(tmp_path):
    csv_path = tmp_path / "companies.csv"
    _write_csv(csv_path, [{"Name": f"Co{i}"} for i in range(5)])

    companies = load_companies(str(csv_path), limit=2)

    assert len(companies) == 2


def test_load_done_row_indices_reads_existing_output(tmp_path):
    out_csv = tmp_path / "out.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLS)
        writer.writeheader()
        writer.writerow({**{c: "" for c in OUTPUT_COLS}, "_row_index": 0})
        writer.writerow({**{c: "" for c in OUTPUT_COLS}, "_row_index": 3})

    assert load_done_row_indices(out_csv) == {0, 3}


def test_load_done_row_indices_empty_when_no_file(tmp_path):
    assert load_done_row_indices(tmp_path / "nonexistent.csv") == set()
```

- [ ] **Step 2: Run to verify it fails**

Run: `venv/bin/python -m pytest tests/test_enrich_companies_io.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'enrich_companies'` (the file doesn't exist yet).

- [ ] **Step 3: Create `enrich_companies.py` with the column schemas and both functions**

```python
"""Enrich the ZenABM outreach company CSV with LinkedIn Ad Library signals.

One API call per company (core/client.py's search(), page 1 only,
count=25 — never iter_ads(), never multi-page). Appends one row per
company to data/enriched/company_list_enriched.csv, flushing after every
row so progress is never lost. Safe to re-run any time: it resumes
automatically by skipping _row_index values already present in the
output file.

Usage:
  python3 enrich_companies.py --limit 20          # test run
  python3 enrich_companies.py                     # full run, budget-capped at 950 calls
  python3 enrich_companies.py --max-calls 500      # custom daily budget
  python3 enrich_companies.py --input /path/to/other.csv
"""
from __future__ import annotations

import csv
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from core.client import LinkedInAdLibraryClient, LinkedInApiError
from core.linkedin_signals import compute_company_signals, linkedin_company_id

DEFAULT_CSV_PATH = "/Users/bilal/Downloads/ZenABM Lists:Outreach/Raw - Company List - June 26.csv"
OUT_DIR = Path(__file__).parent / "data" / "enriched"
OUT_CSV = OUT_DIR / "company_list_enriched.csv"
LOG_PATH = OUT_DIR / "enrich_run.log"

RAW_COLS = [
    "HubSpot B2B Companies", "Annual Revenue", "Linkedin Company Id",
    "Business Stage", "B2B/B2C (Clay)", "Scale Scope", "Pattern Tags",
    "Technographics", "Vendor", "Product", "Name", "Description",
    "Primary Industry", "Size", "Type", "Location", "Country", "Domain",
    "LinkedIn URL", "Technologies Used", "Find technology stack",
    "Update People Search (Demand Generation Marketing Roles) - 2026-05-25T10:01:20.375Z",
]

ENRICHED_COLS = [
    "li_status", "li_id_filter_applied", "li_matched_linkedin_id", "li_collision_risk",
    "li_n_ads", "li_total_ads",
    "li_ad_types_used_json",
    "li_linkedin_maturity_score", "li_outreach_timing_score",
    "li_uses_video", "li_uses_carousel", "li_uses_document", "li_uses_message",
    "li_impression_data_coverage",
    "li_is_currently_advertising", "li_is_new_advertiser", "li_is_ramping_up", "li_is_dark_period",
    "li_active_ads_7d", "li_active_ads_30d", "li_active_ads_90d", "li_active_ads_180d",
    "li_recency_caveat",
    "li_total_impressions_est",
    "li_country_impression_share_pct_json", "li_primary_market_country_json",
    "li_uses_retargeting", "li_targets_job_roles", "li_targets_specific_companies", "li_funnel_stage",
    "li_impressions_midpoint_per_ad_json", "li_impression_range_confidence_per_ad_json",
    "li_campaign_size_tier_per_ad_json", "li_campaign_duration_days_per_ad_json",
    "li_eu_impressions_share_of_total_per_ad_json", "li_eu_disclosed_share_mean",
    "li_api_advertiser_names_seen",
    "li_raw_ads_json",
    "li_notes", "li_fetched_at",
]

OUTPUT_COLS = ["_row_index"] + RAW_COLS + ENRICHED_COLS


def load_companies(csv_path: str, limit: Optional[int] = None) -> List[Dict[str, object]]:
    """Load every row of the raw CSV, tagging each with its position as `_row_index`.

    Keeps ALL rows (no dedup by name) — every original row gets its own
    enriched output row, per the design spec's "complete picture" goal.
    """
    companies: List[Dict[str, object]] = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            entry: Dict[str, object] = {col: row.get(col, "") for col in RAW_COLS}
            entry["_row_index"] = i
            companies.append(entry)
            if limit and len(companies) >= limit:
                break
    return companies


def load_done_row_indices(out_csv: Path) -> Set[int]:
    """Row indices already present in the output CSV — the entire resume mechanism."""
    if not out_csv.exists():
        return set()
    done: Set[int] = set()
    with open(out_csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            idx = row.get("_row_index", "")
            if idx != "":
                done.add(int(idx))
    return done
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `venv/bin/python -m pytest tests/test_enrich_companies_io.py -v`
Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add enrich_companies.py tests/test_enrich_companies_io.py
git commit -m "Add CSV I/O layer for company list enrichment script"
```

---

### Task 3: Per-company enrichment logic

**Files:**
- Modify: `enrich_companies.py` (add `is_valid_csv_id` and `process_company`)
- Test: `tests/test_enrich_companies_process.py`

**Interfaces:**
- Consumes: `core.client.LinkedInAdLibraryClient` (structurally — any object with a `.search(advertiser=, keyword=, start=, count=) -> AdLibraryResponse` method), `core.linkedin_signals.compute_company_signals`, `core.linkedin_signals.linkedin_company_id` (from Task 1), `ENRICHED_COLS` (from Task 2).
- Produces: `process_company(client, name: str, csv_id: str, now_ms: int) -> Dict[str, object]` (keys exactly match `ENRICHED_COLS`) — consumed by Task 4's `main()`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_enrich_companies_process.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.schema import AdLibraryResponse, AdElement, AdDetails, AdvertiserInfo, Paging
from enrich_companies import process_company

NOW_MS = 1_783_080_000_000  # 2026-07-03 12:00:00 UTC — matches the fixed clock in test_linkedin_signals.py


def _ad(advertiser_url, name="Acme Inc"):
    return AdElement(
        adUrl="https://www.linkedin.com/ad-library/detail/111",
        isRestricted=False,
        details=AdDetails(
            advertiser=AdvertiserInfo(advertiserName=name, advertiserUrl=advertiser_url),
            type="SPONSORED_STATUS_UPDATE",
            adTargeting=[],
            adStatistics=None,
        ),
    )


class FakeClient:
    def __init__(self, response):
        self._response = response

    def search(self, advertiser=None, keyword=None, start=0, count=25):
        return self._response


def test_process_company_filters_by_valid_csv_id():
    ads = [
        _ad("https://www.linkedin.com/company/12345", "Acme Inc"),
        _ad("https://www.linkedin.com/company/99999", "Unrelated Co"),
    ]
    response = AdLibraryResponse(elements=ads, paging=Paging(count=25, start=0, total=2, links=None))
    client = FakeClient(response)

    row = process_company(client, "Acme", "12345", NOW_MS)

    assert row["li_status"] == "found_by_id"
    assert row["li_matched_linkedin_id"] == "12345"
    assert row["li_n_ads"] == 1


def test_process_company_flags_collision_when_no_valid_id():
    ads = [
        _ad("https://www.linkedin.com/company/12345", "Acme Inc"),
        _ad("https://www.linkedin.com/company/99999", "Unrelated Co"),
    ]
    response = AdLibraryResponse(elements=ads, paging=Paging(count=25, start=0, total=2, links=None))
    client = FakeClient(response)

    row = process_company(client, "Acme", "-8140982", NOW_MS)

    assert row["li_status"] == "found"
    assert row["li_id_filter_applied"] is False
    assert row["li_collision_risk"] is True


def test_process_company_not_found_returns_empty_ads():
    response = AdLibraryResponse(elements=[], paging=Paging(count=25, start=0, total=0, links=None))
    client = FakeClient(response)

    row = process_company(client, "Nonexistent Xyz", "", NOW_MS)

    assert row["li_status"] == "not_found"
    assert row["li_n_ads"] == 0
```

- [ ] **Step 2: Run to verify it fails**

Run: `venv/bin/python -m pytest tests/test_enrich_companies_process.py -v`
Expected: FAIL with `ImportError: cannot import name 'process_company'`.

- [ ] **Step 3: Add `is_valid_csv_id` and `process_company` to `enrich_companies.py`**

Append to `enrich_companies.py` (after the two functions from Task 2):

```python
def is_valid_csv_id(id_str: object) -> bool:
    try:
        return int(str(id_str).strip()) > 0
    except (ValueError, TypeError):
        return False


def process_company(client, name: str, csv_id: str, now_ms: int) -> Dict[str, object]:
    """One API call, ID-match filter, flatten compute_company_signals() into ENRICHED_COLS."""
    row: Dict[str, object] = {c: "" for c in ENRICHED_COLS}
    row["li_fetched_at"] = datetime.now(tz=timezone.utc).isoformat()
    row["li_id_filter_applied"] = False
    row["li_collision_risk"] = False

    try:
        response = client.search(advertiser=name, start=0, count=25)
    except (LinkedInApiError, ValueError) as e:
        row["li_status"] = "error"
        row["li_notes"] = str(e)
        return row

    all_ads = response.elements
    total_reported = response.paging.total
    valid_id = is_valid_csv_id(csv_id)

    if valid_id:
        matched_id = str(csv_id).strip()
        ads = [a for a in all_ads if linkedin_company_id(a) == matched_id]
        row["li_id_filter_applied"] = True
        row["li_matched_linkedin_id"] = matched_id
        row["li_status"] = "found_by_id" if ads else "not_found_by_id"
    else:
        distinct_ids = {linkedin_company_id(a) for a in all_ads if linkedin_company_id(a)}
        row["li_collision_risk"] = len(distinct_ids) > 1
        row["li_status"] = "found" if all_ads else "not_found"
        ads = all_ads

    names_seen = sorted({
        a.details.advertiser.advertiserName for a in all_ads if a.details.advertiser.advertiserName
    })
    row["li_api_advertiser_names_seen"] = "; ".join(names_seen)
    row["li_raw_ads_json"] = json.dumps([a.model_dump(by_alias=True) for a in ads])

    signals = compute_company_signals(ads, now_ms=now_ms, total_ads=total_reported)
    row["li_n_ads"] = signals["n_ads"]
    row["li_total_ads"] = signals["total_ads"]
    row["li_ad_types_used_json"] = json.dumps(signals["ad_types_used"])
    row["li_linkedin_maturity_score"] = signals["linkedin_maturity_score"]
    row["li_outreach_timing_score"] = signals["outreach_timing_score"]
    row["li_uses_video"] = signals["uses_video"]
    row["li_uses_carousel"] = signals["uses_carousel"]
    row["li_uses_document"] = signals["uses_document"]
    row["li_uses_message"] = signals["uses_message"]
    row["li_impression_data_coverage"] = signals["impression_data_coverage"]
    row["li_is_currently_advertising"] = signals["is_currently_advertising"]
    row["li_is_new_advertiser"] = signals["is_new_advertiser"]
    row["li_is_ramping_up"] = signals["is_ramping_up"]
    row["li_is_dark_period"] = signals["is_dark_period"]
    row["li_active_ads_7d"] = signals["active_ads_7d"]
    row["li_active_ads_30d"] = signals["active_ads_30d"]
    row["li_active_ads_90d"] = signals["active_ads_90d"]
    row["li_active_ads_180d"] = signals["active_ads_180d"]
    row["li_recency_caveat"] = (
        f"sample of {len(ads)}/{total_reported} total ads; "
        "ordering not guaranteed chronological (constraints.md §5)"
        if ads else ""
    )
    row["li_total_impressions_est"] = signals["total_impressions_est"]
    row["li_country_impression_share_pct_json"] = json.dumps(signals["country_impression_share_pct"])
    row["li_primary_market_country_json"] = json.dumps(signals["primary_market_country"])
    row["li_uses_retargeting"] = signals["uses_retargeting"]
    row["li_targets_job_roles"] = signals["targets_job_roles"]
    row["li_targets_specific_companies"] = signals["targets_specific_companies"]
    row["li_funnel_stage"] = signals["funnel_stage"]
    row["li_impressions_midpoint_per_ad_json"] = json.dumps(signals["impressions_midpoint_per_ad"])
    row["li_impression_range_confidence_per_ad_json"] = json.dumps(signals["impression_range_confidence_per_ad"])
    row["li_campaign_size_tier_per_ad_json"] = json.dumps(signals["campaign_size_tier_per_ad"])
    row["li_campaign_duration_days_per_ad_json"] = json.dumps(signals["campaign_duration_days_per_ad"])
    row["li_eu_impressions_share_of_total_per_ad_json"] = json.dumps(signals["eu_impressions_share_of_total_per_ad"])
    row["li_eu_disclosed_share_mean"] = signals["eu_disclosed_share_mean"]

    return row
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `venv/bin/python -m pytest tests/test_enrich_companies_process.py -v`
Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add enrich_companies.py tests/test_enrich_companies_process.py
git commit -m "Add per-company enrichment logic (one API call, ID-match, signal flatten)"
```

---

### Task 4: CLI wiring, live progress, and the real test run

**Files:**
- Modify: `enrich_companies.py` (add `main()` + `if __name__ == "__main__"`)
- Modify: `requirements.txt` (add `tqdm`)

**Interfaces:**
- Consumes: everything from Tasks 2 and 3.
- Produces: the runnable CLI — no further consumers.

- [ ] **Step 1: Add `tqdm` to dependencies and install it**

Edit `requirements.txt`, in the "Foundation + core toolkit" section:

```
requests>=2.31.0
python-dotenv>=1.0.0
pydantic>=2.10
pytest>=7.4.0
tqdm>=4.66.0
```

Run: `venv/bin/pip install tqdm>=4.66.0`
Expected: installs successfully.

- [ ] **Step 2: Add `main()` to `enrich_companies.py`**

Append to `enrich_companies.py`:

```python
import argparse

from tqdm import tqdm


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=str, default=DEFAULT_CSV_PATH)
    parser.add_argument("--limit", type=int, default=None,
                        help="Only load the first N companies from the CSV (test mode)")
    parser.add_argument("--max-calls", type=int, default=950,
                        help="Stop after this many API calls this run (headroom below the 1,000/day quota)")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)s  %(message)s",
        handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler(sys.stderr)],
    )
    log = logging.getLogger(__name__)

    token = os.getenv("LINKEDIN_ACCESS_TOKEN")
    if not token:
        log.error("LINKEDIN_ACCESS_TOKEN not set in .env")
        sys.exit(1)

    client = LinkedInAdLibraryClient(access_token=token)
    companies = load_companies(args.input, limit=args.limit)
    done = load_done_row_indices(OUT_CSV)
    remaining = [c for c in companies if c["_row_index"] not in done]

    log.info(
        f"Loaded {len(companies)} companies "
        f"({len(companies) - len(remaining)} already done, {len(remaining)} remaining)"
    )

    is_new = not OUT_CSV.exists()
    fh = open(OUT_CSV, "a", newline="", encoding="utf-8")
    writer = csv.DictWriter(fh, fieldnames=OUTPUT_COLS, extrasaction="ignore")
    if is_new:
        writer.writeheader()
        fh.flush()

    counts: Dict[str, int] = {}
    calls_made = 0

    bar = tqdm(remaining, desc="enriching", unit="co")
    try:
        for company in bar:
            if calls_made >= args.max_calls:
                log.info(f"Reached --max-calls budget ({args.max_calls}). Stopping for this run.")
                break

            now_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
            row = process_company(
                client, company["Name"], company["Linkedin Company Id"], now_ms
            )
            calls_made += 1
            counts[row["li_status"]] = counts.get(row["li_status"], 0) + 1

            writer.writerow({**company, **row})
            fh.flush()

            bar.set_postfix({
                "today": f"{calls_made}/{args.max_calls}",
                "total": f"{len(done) + calls_made}/{len(companies)}",
                **{k: v for k, v in counts.items() if v},
            })

            if calls_made < args.max_calls:
                time.sleep(4)
    finally:
        fh.close()

    left = len(remaining) - calls_made
    log.info(f"Run complete: {calls_made} API calls made, {max(left, 0)} companies still remaining.")
    log.info(f"Output: {OUT_CSV}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run the full local test suite to confirm nothing broke**

Run: `venv/bin/python -m pytest tests/test_linkedin_signals.py tests/test_enrich_companies_io.py tests/test_enrich_companies_process.py -v`
Expected: all tests PASS.

- [ ] **Step 4: Real test run against 20 live companies**

Run: `venv/bin/python enrich_companies.py --limit 20`
Expected: a live progress bar advances from 0/20 to 20/20 over roughly 80 seconds (4s/company), `data/enriched/company_list_enriched.csv` is created with a header row plus 20 data rows, and `data/enriched/enrich_run.log` has one INFO line per company. Some rows will be `not_found` (most B2B companies don't run LinkedIn ads), some `found`/`found_by_id` — that spread is expected and matches the earlier 72-company manual test (`data/batch/company_summary.csv`: 18 found, 11 found_by_id, 30 not_found out of 72).

- [ ] **Step 5: Inspect the output together**

Open `data/enriched/company_list_enriched.csv` and confirm: all 22 original columns are present and match the source CSV, `li_status` values look right, at least one row has non-empty `li_raw_ads_json` and populated signal columns, and `_row_index` values are 0-19. Report back to Bilal before running anything larger.

- [ ] **Step 6: Commit**

```bash
git add enrich_companies.py requirements.txt
git commit -m "Add CLI wiring: resume, budget stop, live progress bar

python3 enrich_companies.py --limit 20 tested against the live API:
20/20 companies processed, output verified against the 22 raw columns
plus signal columns."
```

Note: `data/enriched/` is not added — it's covered by the existing `data/**` gitignore rule.

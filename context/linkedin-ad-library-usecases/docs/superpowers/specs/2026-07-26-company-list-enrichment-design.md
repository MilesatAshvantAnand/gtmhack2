# Company List Enrichment — Design Spec

**Date:** 2026-07-26
**Status:** Approved, pending implementation plan

## Problem

Bilal has a 40,188-row prospecting CSV (`~/Downloads/ZenABM Lists:Outreach/Raw - Company List - June 26.csv`, 22 columns) and wants it enriched with LinkedIn Ad Library data — for each company: whether they advertise, how much, in what formats, where, and how mature/timely they look as an outreach target — merged into one final CSV alongside every original column, so the output is a single complete picture per company. He wants to see live progress while it runs, and to test on a small batch first.

The LinkedIn Ad Library API has a hard 1,000-requests/day/token quota (`docs/api-knowledge-base/constraints.md §6`) and no server-side date filter (§3) — both are binding constraints on the design, not just implementation details.

## Context found during brainstorming

- `batch_lookup.py` (repo root) already solves the adjacent "search + ID-match + summarize" problem for the paused `01-b2b-outreach` project, but is coupled to its SQLite/contacts machinery and only carries forward 7 of the CSV's 22 raw columns.
- Local `main` was 35 commits behind `origin/main` at the start of this work (now pulled current). The live `abm-competitor-intel` skill repurposed `core/signals.py` to work against ZenABM's own API models — it no longer accepts raw LinkedIn `AdElement` data.
- The **original raw-LinkedIn version of `core/signals.py`** (652 lines, paired with the still-current `core/client.py` + `core/schema.py`) exists in git history at commit `31fbbff~1`, along with its retired 368-line test suite (`tests/test_core_signals.py`, deleted in `d4b27e4`). It implements `compute_company_signals()` — every signal this task needs, with correct tier N/S/T gating (`None` for unknown, never a masked `False`).
- The CSV's `Linkedin Company Id` column is a real positive LinkedIn numeric ID ~84% of the time; the rest are negative Clay-generated placeholders (not real IDs) — this matches the existing `is_valid_csv_id` convention in `batch_lookup.py`.
- LinkedIn's public Ad Library **web UI** (`linkedin.com/ad-library/search?dateOption=...`) supports date-range filtering that the official Marketing Developer Platform API (`api.linkedin.com/rest/adLibrary`, what `core/client.py` calls) does not. Scraping that UI was discussed and explicitly **deferred as a separate, later, smaller experiment** — it's a different system (session-auth consumer site, not the authorized API), carries real ToS/account risk, and doesn't belong embedded in a pipeline that must run unattended across 40K companies for weeks. Out of scope for this spec.

## Architecture

One new standalone script, `enrich_companies.py`, at repo root — a sibling to `batch_lookup.py`, not a resumption of the paused project's SQLite/contacts surface area.

```
enrich_companies.py            (Layer 3-equivalent, one-off operational script)
core/client.py                 (existing, unmodified — raw LinkedIn API client)
core/schema.py                 (existing, unmodified — raw LinkedIn pydantic models)
core/linkedin_signals.py       (NEW — restored from git history 31fbbff~1:core/signals.py)
tests/test_linkedin_signals.py (NEW — restored from git history, deleted in d4b27e4)
```

`core/signals.py` (the live, ZenABM-model version powering `abm-competitor-intel`) is untouched. The restored file gets a new name so there is no collision and no risk to the shipped skill.

## Data flow

1. **Load** all 40,188 rows from the raw CSV verbatim (all 22 original columns, in original order), tagging each with a stable `_row_index` (its position in the file — not `Name`, which isn't unique across 40K rows).
2. **Resume check:** if the output CSV already exists, read the `_row_index` values already present and skip them. This is the entire resume mechanism — no separate checkpoint file. Safe to re-run any time; it always continues where the last run left off.
3. **Per remaining company, one API call:** `core/client.py`'s `LinkedInAdLibraryClient.search(advertiser=name, start=0, count=25)`. This is exactly one HTTP request — no further pagination. Built-in 429 retry (35s wait, up to 3 attempts) is already handled inside `core/client.py`.
4. **ID-match filtering:**
   - If the CSV's `Linkedin Company Id` is a valid positive integer, filter the page's ads to `linkedin_company_id(ad) == csv_id` (from `core/linkedin_signals.py`).
   - If not, keep all ads returned on the page. If more than one distinct advertiser/company-id appears among them, set `li_collision_risk = True` (informational — we don't discard data we already paid a call for).
5. **Compute signals:** `compute_company_signals(filtered_ads, now_ms, total_ads=response.paging.total)` from the restored `core/linkedin_signals.py`. `total_ads` is exact (LinkedIn's own reported count for the query). `active_ads_7d/30d/90d/180d` are computed from whatever's in the ≤25-ad sample — best-effort, not guaranteed-complete, because LinkedIn's ordering is "roughly newer-first but with jitter," never strictly chronological (`constraints.md §5`, `call-patterns.md §8b`). A `li_recency_caveat` column states the sample size this was computed from.
6. **Flatten and append one row:** all 22 raw columns + `li_`-prefixed signal columns (see Output columns below) to the output CSV, immediately (not batched in memory) — so a kill mid-run never loses completed work.
7. **Budget stop:** after `--max-calls` (default 950 — headroom below the 1,000/day cap) API calls, or `--limit N` companies (test mode), whichever comes first, the script exits cleanly with a summary. It does not auto-schedule the next run; Bilal re-runs it manually whenever he's ready for the next batch.

## Output

**File:** `data/enriched/company_list_enriched.csv` (gitignored, under this repo — per CLAUDE.md, `data/` is never committed).

**Columns:**
- All 22 original raw CSV columns, verbatim, original names, original order.
- `_row_index` — stable identifier for resume tracking.
- `li_status` — `found` / `found_by_id` / `not_found` / `not_found_by_id` / `error`.
- `li_id_filter_applied`, `li_matched_linkedin_id`
- `li_collision_risk` — bool, set when no valid CSV ID and page-1 shows multiple distinct advertisers.
- `li_n_ads`, `li_total_ads` (exact, from `paging.total`)
- `li_ad_types_used_json`
- `li_linkedin_maturity_score`, `li_outreach_timing_score`
- `li_uses_video`, `li_uses_carousel`, `li_uses_document`, `li_uses_message`
- `li_impression_data_coverage`
- `li_is_currently_advertising`, `li_is_new_advertiser`, `li_is_ramping_up`, `li_is_dark_period`
- `li_active_ads_7d`, `li_active_ads_30d`, `li_active_ads_90d`, `li_active_ads_180d`
- `li_recency_caveat` — e.g. `"sample of 18/143 total ads; ordering not guaranteed chronological"`
- `li_total_impressions_est`
- `li_country_impression_share_pct_json`, `li_primary_market_country_json`
- `li_uses_retargeting`, `li_targets_job_roles`, `li_targets_specific_companies`, `li_funnel_stage`
- `li_impressions_midpoint_per_ad_json`, `li_impression_range_confidence_per_ad_json`, `li_campaign_size_tier_per_ad_json`, `li_campaign_duration_days_per_ad_json`, `li_eu_impressions_share_of_total_per_ad_json`, `li_eu_disclosed_share_mean`
- `li_api_advertiser_names_seen` — raw advertiser name(s) LinkedIn returned (for QA on fuzzy-match quality)
- `li_raw_ads_json` — the untouched raw response elements for this company, so no field is ever lost even where a derived column doesn't cover it
- `li_notes`, `li_fetched_at`

## Rate limiting & progress

- 4s sleep between company calls (matches the proven safe pacing already validated in `batch_lookup.py` and `constraints.md §6`).
- Live `tqdm` progress bar: `[###-------] 412/950 today | 8,204/40,188 total | found 63, not_found 349 | ETA`.
- A rotating log file captures full request/response detail without cluttering the progress bar.

## Error handling

- Any non-200/429 response from `core/client.py` (surfaced as `LinkedInApiError`) is caught per-company: write a row with `li_status = "error"`, `li_notes` containing the error, and continue to the next company. One bad company never aborts the run.
- Missing `LINKEDIN_ACCESS_TOKEN` fails fast at startup with a clear message.

## Testing

1. Restore `core/linkedin_signals.py` + `tests/test_linkedin_signals.py` from git history; run the restored test suite to confirm it's still green with no modifications needed.
2. `python3 enrich_companies.py --limit 20` — first real test run against 20 companies from the live CSV.
3. Inspect the resulting `company_list_enriched.csv` together (column completeness, plausibility of signals, at least one `found`/`found_by_id`/`not_found`/`not_found_by_id` case) before running against the full 40,188.

## Out of scope

- Scraping LinkedIn's consumer Ad Library web UI for exact date-windowed counts (the "488 ads match your search criteria" number). Explicitly deferred to a separate, smaller, later experiment — not part of this script or this spec.
- Reviving any part of the paused `01-b2b-outreach` project beyond reusing its proven matching logic as a reference (SQLite, contact-matching, London-specific scripts remain untouched and paused).
- Automated daily scheduling of the next batch — reruns are manual.

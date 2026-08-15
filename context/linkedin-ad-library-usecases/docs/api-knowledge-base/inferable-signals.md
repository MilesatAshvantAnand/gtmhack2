# Inferable Signals

Everything the API returns is "native data" (see `response-fields.md`). Everything below is **derived** from that native data — with a formula, prerequisites, corpus-based validation, and known failure cases.

**Prerequisite legend** — every signal depends on a subset of native fields:
- **N** = needs only `details.type` / `details.advertiser` (works for 100% of ads)
- **S** = needs `details.adStatistics` (works for 64.3% of ads, EU-visible only)
- **T** = needs `details.adTargeting` non-empty (also 64.3% coverage)

---

## A. Company-level advertising activity

### A1. `total_ads` — API-reported

**Formula:** `paging.total` from any page-1 response.
**Prereq:** N.
**Validation:** cross-checked against per-company counts — matches. Salesforce=9403, Personio=2755, ZenABM=243.
**Failure case:** for keyword-only searches, `paging.total` is the count of *matching* ads not company-specific — different semantics.

### A2. `is_currently_advertising` (boolean)

**Formula:** `any ad in the returned set has (now - latestImpressionAt) < 30 days`.
**Prereq:** S.
**Validation:** for US-only advertisers with 0 EU-visible ads (e.g. many Salesforce ads), the formula returns false **even if the company is heavily advertising in the US**. This is a false-negative.
**Fix:** gate the signal on `impression_data_coverage != none` before trusting a `false` result. For US-only cases, treat this signal as "unknown" not "false".

### A3. `is_new_advertiser` (boolean)

**Formula:** `all ads' firstImpressionAt within last 90 days`.
**Prereq:** S.
**Failure case:** same as A2 — for US-only advertisers, no visible impression data means the signal is "unknown" not "false".

### A4. `is_dark_period` (boolean)

**Formula (validated pre-audit):** `is_dark_period = latest_impression < now - 30d AND pct_ads_with_impression_data >= 20%`.
**Why the second clause:** without it, US-only companies falsely show `is_dark_period = true` because their impression data is EU-only-visible. The 20% gate rules them out.
**Prereq:** S.
**Corpus check:** Salesforce would falsely fire `is_dark_period` if not for the gate (6/75 ads with stats → 8% coverage, below 20% → correctly excluded). Kept.

### A5. `is_ramping_up` (boolean)

**Formula:** `>= 20% of returned ads have firstImpressionAt within last 30d`.
**Prereq:** S.
**Failure case:** same US-only caveat.

### A6. `outreach_timing_score` (0–8)

**Formula:** `+3 if is_ramping_up, +2 if is_new_advertiser, +2 if is_dark_period, +1 if is_currently_advertising`.
**Prereq:** S.
**Validity:** composite of A2–A5, so it inherits their failure modes. Only meaningful when `impression_data_coverage != none`.

---

## B. Ad format sophistication

### B1. `ad_types_used` (set)

**Formula:** unique values of `details.type` across all fetched ads.
**Prereq:** N. Works for 100% of ads.
**Corpus:** Personio used 2 types (VIDEO, STATUS_UPDATE); HubSpot used 2 (STATUS_UPDATE, NATIVE_DOCUMENT); Salesforce used 5. Diversity correlates with brand size.

### B2. `linkedin_maturity_score` (0–10)

**Formula (existing):** points for using video, carousel, document, message, InMail, spotlight. Cap at 10.
**Prereq:** N.
**Validation:** in-corpus range is 2–6. No company hit 8+ because SPOTLIGHT_V2 wasn't observed in any fixture.

### B3. `funnel_stage` (awareness | consideration | conversion | mixed)

**Formula (existing):** classify ads based on `type` distribution + presence of retargeting facet (Audience).
- awareness: mostly SPONSORED_STATUS_UPDATE / SPONSORED_VIDEO without retargeting
- consideration: mix of formats, some retargeting
- conversion: heavy retargeting + document/message formats

**Prereq:** N + T (retargeting piece requires targeting).
**Failure case:** for US-only advertisers we can't see targeting, so `retargeting` piece is unknown. Downgrade to "unknown" rather than defaulting to awareness.

### B4. `uses_video` / `uses_carousel` / `uses_document` / `uses_message` (bool)

**Formula:** presence of the corresponding `details.type` in any returned ad.
**Prereq:** N.

### B5. `uses_retargeting` (bool)

**Formula:** any ad has `Audience` in `adTargeting[].facetName`.
**Prereq:** T. **Only valid when non-empty targeting is present.**
**Failure case:** for US-only advertisers (empty targeting), signal is unknown, not false.

---

## C. Impressions / campaign scale

### C1. `impressions_midpoint` (int, per-ad)

**Formula:** `(totalImpressions.from + totalImpressions.to) / 2`.
**Prereq:** S.
**Uncertainty:** For a 500k–1M bucket, midpoint is 750k with ±250k uncertainty. For 0–1k, midpoint is 500 with ±500 uncertainty. **Never present a single number without acknowledging the bucket width.**

### C2. `impression_range_confidence` (tight | medium | wide | no_data)

**Formula:**
- `no_data` if `adStatistics` absent
- `tight` if `to - from <= 5000`
- `medium` if `to - from <= 50000`
- `wide` otherwise (100k+ buckets)

Meta-signal on how much to trust `impressions_midpoint`.

### C3. `total_impressions_est_lower` / `_upper` / `_midpoint` (company-level)

**Formula:** sum of per-ad bounds across all EU-visible ads.
**Prereq:** S.
**Never present midpoint alone.** Bounds tell the reader what's real vs estimated.

### C4. `campaign_size_tier` (micro | small | medium | large | enterprise)

**Formula:** based on `impressions_midpoint`. Thresholds tuned to bucket boundaries: micro < 5k, small < 30k, medium < 150k, large < 500k, enterprise ≥ 500k.
**Prereq:** S.

### C5. `active_ads_7d` / `_30d` / `_90d` / `_180d`

**Formula:** count of ads with `latestImpressionAt >= now - N days`.
**Prereq:** S.

---

## D. Geographic / target market

### D1. `impression_data_coverage` (full | partial | none)

**Formula (validated pre-audit):**
- `full` if `pct_ads_with_impression_data >= 80%`
- `partial` if `20% <= pct < 80%`
- `none` if `< 20%`

**Prereq:** N (the ratio itself). Result classifies whether S-dependent signals are trustworthy.
**Corpus validation:**

| Company | pct_with_stats | Coverage |
|---|---|---|
| Personio | 95% | full |
| HubSpot | 96% | full |
| Alibaba | 100% | full |
| Novartis | 83% | full |
| Meta | 59% | partial |
| Notion | 36% | partial |
| Miro | 31% | partial |
| BAE Systems | 28% | partial |
| WeWork | 17% | none |
| Peloton | 12% | none |
| HSBC | 9% | none |
| Salesforce | 8% | none |

**Meta-signal: gate every S-prereq signal on this.**

### D2. `country_impression_share_pct` — per-country breakdown ⭐

**Formula:** for each country `c`, `share(c) = sum_over_ads(impressionPercentage_for_c_in_ad × impressions_midpoint_ad) / sum_over_ads(impressions_midpoint_ad)`.
Weighting by impression volume, not naive ad-count average.
**Prereq:** S.
**Failure case:** describes the EU-visible portion only. For US-headquartered companies, this misses their US ad activity entirely. **Do not equate this with "true target market" — see D3.**

### D3. `primary_market_country` ⭐

**Formula (recommended, with caveats):**
- If `impression_data_coverage == full`: primary market ≈ `argmax(country_impression_share_pct)`. Reliable.
- If `partial`: primary market of the EU-visible subset. Real primary market may be different. Report as "primary EU-visible market: X" not "primary market: X".
- If `none`: **no inference possible.** Signal is undefined.

**Corpus examples:**

| Company | Coverage | Reported primary | Real primary |
|---|---|---|---|
| Personio | full | DE (41%) | DE ✓ |
| Alibaba | full | IN (36.5%) | China — **wrong**, Alibaba's CN ads aren't visible via LinkedIn DSA either (LinkedIn largely blocked in China) |
| Rappi | full | FR (38%) | LATAM — **wrong**, Rappi's LATAM ads have `coverage=none` and aren't in the visible subset |
| Salesforce | none | N/A | US (undefined signal correctly) |

Only trust for EU-headquartered advertisers (Personio, HubSpot, Novartis in our corpus). For non-EU-headquartered, primary market is unknowable from this signal alone.

### D4. `eu_impression_share_pct` / `us_impression_share_pct` / `uk_impression_share_pct`

**Formula:** subset-sum of D2.
**Prereq:** S.
**Meaningful case:** any company. **Report as "share of EU-visible impressions", not "share of total impressions"** — for non-EU-only companies these numbers are inflated because non-EU impressions are missing from the denominator.

### D7. `eu_impressions_share_of_total` ⭐ new — corrects the DSA disclosure gap

**Formula:** per ad, `sum_over_countries(impressionPercentage)` — the API-provided percentages describe only the EU/EEA-disclosed subset of the ad's total impressions.

**Prereq:** S (only ads with `adStatistics`).

**Discovery:** in Phase A analysis, 361/610 ads (59%) had impressionPercentage sums well below 100 (some as low as 14.78%). The API does not force sums to normalize to 100. The under-100 sum means the rest of the ad's impressions were NON-EU/EEA and therefore not disclosed per DSA rules.

**Derived interpretation:**
```python
per_ad = sum(entry.impressionPercentage for entry in ad.impressionsDistributionByCountry)

if per_ad >= 99:   ad's traffic was ~100% EU/EEA
elif per_ad >= 50: majority-EU ad, meaningful non-EU tail
elif per_ad >= 10: minority-EU ad, mostly US/other
else:              near-total non-EU ad (should have been in the "no stats" bucket usually)
```

**Company-level rollup:**
```python
eu_disclosed_share = mean_across_ads(per_ad)  # weighted or unweighted
```

**Skill implication:** when comparing user's ads (from ZenABM MCP — full-fidelity, not DSA-gated) against a competitor's Ad Library data, adjust for this. A competitor's "10,000 impressions in Germany" (from Ad Library) is only their EU-visible portion. Their true campaign is bigger.

---

### D5. `is_global` (bool)

**Formula:** number of distinct countries in impression distribution >= threshold (e.g. 10).
**Prereq:** S.
**Failure case:** underestimates for US-heavy companies (US ads hidden). Better: `is_global_within_eu_visible` — rename for clarity.

### D6. `impressed_countries_count`

**Formula:** count of distinct countries with `impressionPercentage > 0` across all ads.
**Corpus max:** 155 countries in a single ad (Alibaba). Company-level max: 198 distinct across all corpus.

---

## E. Targeting sophistication

### E1. `targets_job_roles` (bool)

**Formula:** any ad's `adTargeting` includes an entry with `facetName == "Job"` and `isIncluded == true`.
**Prereq:** T.
**Corpus:** 539 occurrences across 1,075 ads → prevalent when targeting is visible.
**Note:** we know Job facet was used but NOT which jobs (see `constraints.md § 9`).

### E2. `targets_specific_companies` (bool) — ABM signal

**Formula:** any ad has `facetName == "Company"` with `isIncluded == true`.
**Prereq:** T.
**Corpus:** 569 occurrences.
**Big signal for ABM sub-project:** an advertiser using the Company facet is doing account-based marketing. Cannot see which companies — but existence of the facet is informative.

### E3. `uses_audience_targeting` (bool) — retargeting proxy

**Formula:** any ad has `facetName == "Audience"` with `isIncluded == true`.
**Prereq:** T.
**Corpus:** 419 occurrences.
**Interpretation:** the Audience facet is typically used for custom / lookalike / retargeting audiences.

### E4. `uses_exclusions` (bool) — new inference

**Formula:** any ad has any `excludedSegments` non-empty OR any `isExcluded == true`.
**Prereq:** T.
**Meaning:** advertiser is sophisticated enough to exclude segments (typically customers, competitors, geos they don't ship to). Correlates with mature campaign design.

### E5. `targeting_dimensions_count`

**Formula:** count of distinct `facetName` values used across an advertiser's ads.
**Prereq:** T.
**Meaning:** breadth of targeting sophistication. Corpus range: 0–8 (all 8 known facets used).

---

## F. Advertiser identity

### F1. `ad_payer_differs` (bool) — RAW form

**Formula:** `details.advertiser.adPayer != details.advertiser.advertiserName`.
**Prereq:** N.
**Meaning:** legal payer differs from displayed brand.
**Corpus reality (Phase A analysis):** raw comparison fires 89-100% of the time for large advertisers — it's almost always different because of legal-entity suffixes like `Inc.`, `LLC`, `SE & Co. KG`, `B.V.`, `AG`, `GmbH`. So the raw signal is nearly meaningless.

**Use `F1b` instead** — the normalized version below.

### F1b. `ad_payer_differs_normalized` (bool) — the useful form ⭐

**Formula:** strip common legal-entity suffixes from both names, then compare.

**Suffix regex (validated on our corpus):**
```
r"[,\s]+(Inc\.?|LLC|Ltd\.?|Corp\.?|GmbH|SE(\s*&\s*Co\.?\s*KG)?|Limited|B\.V\.|Pty\.?\s*Ltd\.?|S\.A\.|N\.V\.|PLC|AG|A/S|Sp\.\s*z\s*o\.o\.|Group|Holdings?)\s*$"
```

**Prereq:** N.
**Corpus validation (Phase A):**
- **Personio, Rappi, Userpilot:** raw differs 75/75, normalized differs **0/75** → payer is just the legal entity form. Same company.
- **Peloton:** raw differs 51/75, normalized differs **12/75** → 39 ads were legal-entity variations; 12 are actual parent/subsidiary or agency situations (Peloton Interactive vs Peloton Consulting Group).
- **WeWork, ZenABM, Alibaba, HSBC, Miro:** normalized still differs 75/75 → payer is genuinely a different entity than the advertiser.

**Interpretation of normalized-differs = true:**
1. Parent company pays for subsidiary (WeWork → parent LLC)
2. Agency runs campaigns for a brand
3. Sister-company arrangement
4. Fuzzy-search collision where the returned advertiser isn't the target (see F3)

### F2. `linkedin_company_id`

**Formula:** parse the numeric segment of `details.advertiser.advertiserUrl` (regex `/company/(\d+)`).
**Prereq:** N.
**Use:** canonical ID for de-duping and joining with external company data. **The safest identifier LinkedIn exposes**, more reliable than the fuzzy `advertiserName`.

### F4. `advertiser_type` (company | individual) ⭐ new — critical for Skill 1

**Formula:**
```python
url = ad.details.advertiser.advertiserUrl
if "/company/" in url:
    advertiser_type = "company"
elif "/in/" in url:
    advertiser_type = "individual"
else:
    advertiser_type = "unknown"
```

**Prereq:** N.
**Why it matters:** keyword-based search returns both companies AND individual people running sponsored posts (thought leaders / influencers). For competitor-discovery skills (Skill 1), you almost always want to filter to `company`; for content-marketing analysis you might want both. See fixture `phase-b/skill1_kw__product_analytics.json` — 25 first-page results included 19 distinct advertisers, several of which are individuals (Sougata Mandal, Emelia Hanson, Catherine Palacios Pharm.D, MDRA).

### F5. `distinct_advertisers_in_result_set` (int) — Skill 1 helper

**Formula:** count distinct `linkedin_company_id`s across a result set.
**Use:** measures fuzzy-search collision rate for company queries, or competitor breadth for keyword queries.

**Corpus finding (Phase A A8):** collision rate for common company names is severe:
- Personio, Rappi, Userpilot, Alibaba, ZenABM → 1 distinct advertiser in 75 ads (clean)
- HubSpot → 3 distinct, but only 3/75 ads are actually HubSpot; 69/75 are "Systony - HubSpot Elite Partner" (a partner!)
- Meta → 28 distinct in 75 ads (`Metalcolour`, `Metasteps`, `Lenovo Partners – Europe & META`, etc.)
- Salesforce → 7 distinct
- HSBC → 9 distinct

### F3. `id_match_status` (found_by_id | found_by_name | not_found_by_id | not_found | skipped)

**Formula (existing in `batch_lookup.py`):** after fuzzy-search returns, filter to the target company ID; classify based on whether the ID was found in results.
**Prereq:** requires an external target ID for the search query.
**Use:** protects against fuzzy-search collisions (see `constraints.md § 12`). **Skill 1 must implement this** or its "competitors" list will be polluted.

### F2. `linkedin_company_id`

**Formula:** parse the numeric segment of `details.advertiser.advertiserUrl` (regex `/company/(\d+)`).
**Prereq:** N.
**Use:** canonical ID for de-duping and joining with external company data. **The safest identifier LinkedIn exposes**, more reliable than the fuzzy `advertiserName`.

### F3. `id_match_status` (found_by_id | found_by_name | not_found_by_id | not_found | skipped)

**Formula (existing in `batch_lookup.py`):** after fuzzy-search returns, filter to the target company ID; classify based on whether the ID was found in results.
**Prereq:** requires an external target ID for the search query.
**Use:** protects against fuzzy-search collisions (see `constraints.md § 12`).

---

## G. Restricted ads

### G1. `restricted_ads_count`

**Formula:** count of ads with `isRestricted == true`.
**Prereq:** N.
**Status:** **theoretical**. Zero restricted ads observed in our 1,075-ad corpus (see `constraints.md § 11`). Whether this counter can ever be non-zero depends on token scope; leave the code path in place but treat the signal as unproven.

---

## H. Time-based patterns (new inferences worth adding)

### H1. `campaign_duration_days` (per-ad)

**Formula:** `(latestImpressionAt - firstImpressionAt) / (1000 * 86400)`.
**Prereq:** S.
**Interpretation:** short (< 7d) = flighted / burst campaigns; long (> 90d) = always-on.

### H2. `earliest_advertiser_activity` / `latest_advertiser_activity` (company-level)

**Formula:** min/max across ads. Anchors the advertiser's LinkedIn history.

### H3. `cadence_shape` (steady | bursty | one-off)

**Formula:** compute new-ad count per week bucket; classify by variance.
**Prereq:** S.
**Use:** distinguishes always-on campaigns from event-driven bursts. Useful for outreach timing.

### H4. `geo_expansion_pattern` (expanding | contracting | stable)

**Formula:** compare distinct countries in the first-90-day cohort vs. last-90-day cohort of ads.
**Prereq:** S.
**Interpretation:** advertiser adding countries over time → market expansion. Losing countries → retrenchment.

---

## I. Composite scores worth publishing (skill-consumer-facing)

Wrap the raw signals into 3–4 headline metrics for skill outputs — easier for non-technical consumers to reason about:

- **`outreach_timing_score`** (existing 0–8) — when to reach out. Only trust with `impression_data_coverage != none`.
- **`ad_maturity_score`** (existing 0–10) — how sophisticated is their LinkedIn advertising practice.
- **`abm_intensity_score`** (new) — 0–5: +2 if `targets_specific_companies`, +1 if `uses_exclusions`, +1 if `targeting_dimensions_count >= 5`, +1 if `is_ramping_up`.
- **`brand_scale_tier`** (new) — micro / small / medium / large / enterprise from `total_ads` × `campaign_size_tier`.

---

## What we cannot infer from this API alone

- **True target market for US/non-EU-headquartered advertisers** — DSA-hidden ads make the signal unreliable. Need a supplementary data source (LinkedIn Company API, market intel).
- **Specific targeting values for Job/Company/Audience/Demographic/Interests/Education** — the API is deliberately opaque here (see `constraints.md § 9`). Cannot be recovered.
- **Ad creative content, CTA, landing URL** — must scrape `adUrl` (out of API scope).
- **Click, engagement, or conversion metrics** — never exposed.
- **Actual spend** — impressions are the only volumetric; spend is not exposed.

---

---

## Worked example derivations

Every formula above is compact. This section walks each core inference **step-by-step from raw response fields to final value**, using real snippets from our fixtures. If you're implementing a signal, use this as the reference.

### WE1. `country_impression_share_pct` and `primary_market_country`

**Goal:** given an advertiser's ads, compute the impression-weighted share per country and pick the primary market.

**Input:** N ads with `details.adStatistics` (the rest are skipped — see D1). Each ad has:
- `totalImpressions.from`, `totalImpressions.to` — bucket bounds
- `impressionsDistributionByCountry[]` — list of `{country: "urn:li:country:XX", impressionPercentage: float}`

**Step 1 — per-ad midpoint impressions.** For each ad:
```
mid_ad = (totalImpressions.from + totalImpressions.to) / 2
```

**Step 2 — per-country contribution from each ad.** For each ad's country entry:
```
country_code    = country.replace("urn:li:country:", "").upper()
contribution    = mid_ad × (impressionPercentage / 100)
```

**Step 3 — sum across all ads.**
```
weighted[country_code] += contribution
```

**Step 4 — normalize.**
```
share_pct[country_code] = weighted[country_code] / sum(weighted.values()) × 100
```

**Step 5 — primary market.**
```
primary_market_country = argmax(share_pct)
```

**Concrete run against `fixtures/companies/personio/page_1.json`:**

Ad 0 (first element of that fixture):
- `totalImpressions`: `{from: 0, to: 1000}` → midpoint = 500
- `impressionsDistributionByCountry`: `[{"country":"urn:li:country:DE","impressionPercentage":91.54}, {"country":"urn:li:country:AT","impressionPercentage":8.46}]`
- Contributions: DE += 500 × 0.9154 = 457.7, AT += 500 × 0.0846 = 42.3

Iterate over all 71 ads-with-stats for Personio → the sum-then-normalize (computed live in the analysis Bash of round 2) gave:
```
Personio country shares: DE=41.2%, GB=22.7%, NL=22.1%, AT=9.0%, ES=3.1%, rest≈1.9%
primary_market_country = DE (41.2%)
```

**Failure case:** Rappi (LATAM company) → same procedure gives FR=38%, NL=37%, DE=23% (primary = FR). But Rappi's *actual* primary market is LATAM — those ads are DSA-hidden. So the derivation is technically correct but the label "primary_market_country = FR" is misleading. **Guard: only report this as a definitive primary market when `impression_data_coverage == "full"` AND the company's country of incorporation is in EU/UK/USA/similar-DSA-covered geography.**

---

### WE2. `impression_data_coverage`

**Goal:** classify how much of an advertiser's LinkedIn activity is EU-visible (and thus how much we can infer).

**Input:** all ads returned for an advertiser.

**Step 1 — count ads with statistics.**
```
n_total = len(ads)
n_with_stats = sum(1 for ad in ads if ad.get("details", {}).get("adStatistics"))
```

**Step 2 — ratio.**
```
pct_ads_with_impression_data = n_with_stats / n_total × 100
```

**Step 3 — classify.**
```
if pct >= 80:  coverage = "full"
elif pct >= 20: coverage = "partial"
else:          coverage = "none"
```

**Real numbers from our corpus (2026-07-03):**

| Company | n_with_stats | n_total | pct | coverage |
|---|---|---|---|---|
| Personio | 71 | 75 | 94.7% | full |
| Salesforce | 6 | 75 | 8.0% | none |
| Meta | 44 | 75 | 58.7% | partial |
| HSBC | 7 | 75 | 9.3% | none |

**Meta-role:** every downstream Tier S/T signal must check this first. If `none`, they degrade to "unknown" not "false".

---

### WE3. `outreach_timing_score`

**Goal:** composite 0–8 score of "how good is this moment to reach out."

**Input:** ads with `adStatistics`.

**Step 1 — compute the 4 component booleans** (using ~2026-07-03 as `now`, epoch ms `= 1751500000000`):

```
is_currently_advertising = any(ad.latestImpressionAt >= now - 30d for ad in ads)
is_new_advertiser        = min(ad.firstImpressionAt for ad in ads) >= now - 90d
is_ramping_up            = fraction_of_ads_with_firstImpressionAt >= now - 30d >= 20%
is_dark_period           = max(ad.latestImpressionAt) < now - 30d AND coverage != "none"
```

**Step 2 — additive score.**
```
score = 0
score += 3 if is_ramping_up
score += 2 if is_new_advertiser
score += 2 if is_dark_period
score += 1 if is_currently_advertising
```

**Failure case walk-through:** For Salesforce, `coverage = "none"` (only 6 ads have stats). Even if some Salesforce ads have `latestImpressionAt > now - 30d`, the `is_currently_advertising` flag would only tell us about the tiny EU-visible slice, NOT Salesforce's actual US activity. Any skill consumer should read `outreach_timing_score` alongside `impression_data_coverage`; treat it as "unknown" when coverage is `none`.

---

### WE4. `ad_payer_differs` and payer analysis

**Goal:** identify when the legal payer ≠ displayed brand (agency-run campaigns, parent-subsidiary, holding companies).

**Input:** any ad — Tier N, works 100% of the time.

**Step 1 — per-ad comparison.**
```
name  = ad.details.advertiser.advertiserName
payer = ad.details.advertiser.adPayer
differs = (name.strip().lower() != payer.strip().lower())
```

**Step 2 — company-level rollup.**
```
n_differ = sum(1 for ad in ads if differs)
pct_differ = n_differ / n_total × 100
```

**Concrete examples from fixtures:**

- Personio: `advertiserName = "Personio"`, `adPayer = "Personio SE & Co. KG"` → differs (legal entity form)
- Peloton (fitness): `advertiserName = "Peloton"`, `adPayer = "Peloton Interactive, Inc."` → differs (Inc.)
- Peloton Consulting (fuzzy collision): `advertiserName = "Peloton Consulting Group"`, `adPayer = "Peloton Group, LLC"` → differs (parent LLC)
- Salesforce: `advertiserName = "Salesforce"`, `adPayer = "Salesforce, Inc."` → differs

**Interpretation:** in practice `ad_payer_differs = true` at high rates for almost every large advertiser (legal-entity suffix). To be more informative:
- **Normalize** by stripping common legal suffixes (Inc, LLC, GmbH, SE & Co. KG, Ltd, Corp) before comparing.
- If still differs → **potential agency or parent company involvement**, worth flagging.

---

### WE5. `linkedin_maturity_score`

**Goal:** 0–10 score of how sophisticated an advertiser's LinkedIn format usage is.

**Input:** all ads — Tier N.

**Step 1 — the set of distinct types used.**
```
types_used = { ad.details.type for ad in ads }
```

**Step 2 — weighted scoring.**
```
score = 0
score += 1 if "SPONSORED_STATUS_UPDATE" in types_used       # baseline
score += 2 if "SPONSORED_VIDEO" in types_used               # richer format
score += 2 if "SPONSORED_UPDATE_CAROUSEL" in types_used
score += 2 if "SPONSORED_UPDATE_NATIVE_DOCUMENT" in types_used
score += 1 if "SPONSORED_INMAILS" in types_used or "SPONSORED_MESSAGE" in types_used
score += 3 if "SPOTLIGHT_V2" in types_used                  # highest-effort format
score = min(score, 10)
```

**Concrete numbers from corpus:**

| Company | Types used | Score |
|---|---|---|
| HubSpot | STATUS_UPDATE, NATIVE_DOCUMENT | 3 |
| Personio | STATUS_UPDATE, VIDEO | 3 |
| Salesforce | STATUS_UPDATE, VIDEO, NATIVE_DOCUMENT, INMAILS, $UNKNOWN | 6 |
| Peloton | STATUS_UPDATE, VIDEO, MESSAGE, JOBS_V2, FOLLOW_COMPANY_V2 | 4 |
| ZenABM | STATUS_UPDATE, TEXT_AD | 1 |

None of our 15 hit 8+ because SPOTLIGHT_V2 was not observed. The scoring rubric is opinionated — feel free to adjust weights per sub-project.

---

### WE6b. `advertiser_type` — filter individuals from company competitors (Skill 1)

**Goal:** distinguish company advertisers from individual thought leaders in keyword-search results.

**Input:** any ad — Tier N.

**Step 1 — regex on advertiser URL.**
```python
import re
def classify(ad):
    url = ad["details"]["advertiser"]["advertiserUrl"]
    if re.search(r"/company/\d+", url):
        return "company"
    elif re.search(r"/in/", url):
        return "individual"
    return "unknown"
```

**Step 2 — filter or split the result set.**
```python
company_results   = [ad for ad in results if classify(ad) == "company"]
individual_results = [ad for ad in results if classify(ad) == "individual"]
```

**Concrete example (fixture `phase-b/skill1_kw__product_analytics.json`):**
- 25 first-page results
- 19 distinct advertisers
- Several individuals: Sougata Mandal, Emelia Hanson, Catherine Palacios Pharm.D, MDRA
- The rest are companies: Heretto, ClickHouse, IQVIA, Definitive Healthcare, etc.

**Skill 1 default behavior:** filter to `type == "company"` before de-duping distinct advertisers. Skill 1 UI could offer a toggle "include individual/influencer ads" for content research modes.

---

### WE7. `eu_impressions_share_of_total` — the DSA-disclosure gap ⭐ NEW

**Goal:** estimate what fraction of an ad's true impressions were EU/EEA (and thus disclosed) vs. non-EU (hidden by DSA rules).

**Input:** ad with `adStatistics` — Tier S.

**Step 1 — per-ad sum of country percentages.**
```python
disclosed_pct = sum(
    entry["impressionPercentage"]
    for entry in ad["details"]["adStatistics"]["impressionsDistributionByCountry"]
)
```

**Step 2 — classify.**
```
disclosed_pct >= 99   →  ad is ~100% EU/EEA — full disclosure trustable
disclosed_pct 50–99   →  majority EU, meaningful US/other tail hidden
disclosed_pct 10–50   →  mostly non-EU; disclosed share is a slice
disclosed_pct < 10    →  near-total non-EU (rare — usually these end up with no adStatistics at all)
```

**Concrete example — a Personio ad with high EU concentration:**
Fixture `companies/personio/page_1.json`, element 0:
```
countries = [
  {country: "urn:li:country:DE", impressionPercentage: 91.54},
  {country: "urn:li:country:AT", impressionPercentage: 8.46}
]
sum = 100.0 → 100% EU disclosure
```

**Concrete example — a Salesforce ad with mixed disclosure:**
Fixture `companies/salesforce/page_1.json`, some ads have sums between 14-99. Those ads had US (or other non-EU) impressions that DSA didn't require disclosing.

**Skill 2 use:** when computing competitor's true campaign scale, divide the reported impressions midpoint by `disclosed_pct/100` for a rough total-scale estimate. E.g., an ad with midpoint 15,000 impressions and `disclosed_pct=50%` had ~30,000 true impressions.

**Skill 2 caveat:** this correction is per-ad only. Aggregating across an advertiser's ads (some fully disclosed, some partially) means the "true scale" estimate has compounding uncertainty. Always report the range, not a single number.

---

### WE6. `targets_specific_companies` — ABM detection ⭐ (for the ABM skill)

**Goal:** detect whether an advertiser is doing account-based marketing (targeting specific companies).

**Input:** ads with non-empty `adTargeting` — Tier T.

**Step 1 — check each ad's targeting.**
```
for ad in ads:
    for facet in ad.details.adTargeting:
        if facet.facetName == "Company" and facet.isIncluded:
            → this ad targets specific companies
```

**Step 2 — company-level rollup.**
```
n_abm_ads = count of ads matching above
is_abm    = n_abm_ads >= 1                # or higher threshold
abm_share = n_abm_ads / n_ads_with_targeting
```

**Corpus finding:** `Company` facet occurred 569 times across 1,606 targeting entries → very prevalent. HubSpot, Personio, and Salesforce all show heavy Company-facet usage.

**Big caveat:** the API tells us the facet was used but NOT which companies. Cannot recover specific target accounts. Any ABM skill can only say "advertiser X is doing ABM" — not "advertiser X targets Google, Meta, and Amazon."

**Skill-facing composite: `abm_intensity_score`**
```
score = 0
score += 2 if is_abm
score += 1 if abm_share >= 0.5           # majority of ads use Company targeting
score += 1 if any(facet.facetName == "Job" for ad, facet ...)   # combined with Job → tight ICP
score += 1 if any(excludedSegments for facet in Company facets) # excluding accounts too
```

---

---

### WE8. Timing signals bundle — `is_currently_advertising`, `is_new_advertiser`, `is_dark_period`, `is_ramping_up`

**Shared input:** all ads returned for an advertiser + `now` as epoch millis. Filter to those with `adStatistics` (rest are unusable for these signals — Tier S).

**Shared step 0:** convert timestamps.
```python
DAY_MS = 86_400_000
now_ms = int(time.time() * 1000)
ads_with_stats = [a for a in ads if a.get("details", {}).get("adStatistics")]
firsts  = [a["details"]["adStatistics"]["firstImpressionAt"]  for a in ads_with_stats]
latests = [a["details"]["adStatistics"]["latestImpressionAt"] for a in ads_with_stats]
```

**`is_currently_advertising`** — any ad had impressions in the last 30 days.
```python
is_currently_advertising = any(l >= now_ms - 30 * DAY_MS for l in latests)
```
Corpus check on Personio: latest impression = 2026-07-03; today = 2026-07-03 → true. On WeWork (data through late 2025): false.

**`is_new_advertiser`** — the advertiser's earliest ad is < 90 days old.
```python
is_new_advertiser = firsts and min(firsts) >= now_ms - 90 * DAY_MS
```
Corpus check: Personio's earliest firstImpressionAt (from page 1's 75 ads) is ~2025-10-01 — older than 90d → false. Would return true only for a truly new advertiser or when we've captured only their recent ads.

**`is_ramping_up`** — 20%+ of returned ads started in the last 30 days (accelerating cadence).
```python
new_ads = sum(1 for f in firsts if f >= now_ms - 30 * DAY_MS)
is_ramping_up = new_ads / len(firsts) >= 0.20
```
**Skill 2 use:** if competitor is ramping and user isn't, that's an alarm bell.

**`is_dark_period`** — was active, went quiet 30+ days ago; gated on non-`none` coverage.
```python
gone_quiet = latests and max(latests) < now_ms - 30 * DAY_MS
is_dark_period = gone_quiet and impression_data_coverage != "none"
```
The `coverage != "none"` gate prevents false positives on US-only advertisers whose EU-visible ads are stale but who are actually still very active in the US.

---

### WE9. `campaign_duration_days` (per-ad) + `cadence_shape` (advertiser-level)

**Per-ad:**
```python
duration_days = (latestImpressionAt - firstImpressionAt) / DAY_MS
```

**Interpretation:**
- `< 7 days` → flighted / short burst campaign
- `7–30 days` → typical short campaign
- `30–90 days` → mid-length
- `> 90 days` → always-on evergreen

**Advertiser-level `cadence_shape`:**
```python
# Bucket the ads' firstImpressionAt into weekly buckets
weekly_starts = Counter(f // (7 * DAY_MS) for f in firsts)
mean = statistics.mean(weekly_starts.values())
stdev = statistics.stdev(weekly_starts.values()) if len(weekly_starts) > 1 else 0
cv = stdev / mean if mean else 0

if cv < 0.5:      cadence_shape = "steady"      # weekly new-ad count is stable
elif cv < 1.5:    cadence_shape = "bursty"      # spikes + quiet stretches
else:             cadence_shape = "one-off"     # dominated by a single burst
```

**Skill 2 use:** side-by-side plot of user's cadence vs competitor's over 12 months. Steady always-on is a different competitor threat than bursty event-driven.

---

### WE10. `active_ads_[7|30|90|180]d` — recency counters

**Formula:**
```python
active_ads_7d   = sum(1 for l in latests if l >= now_ms - 7   * DAY_MS)
active_ads_30d  = sum(1 for l in latests if l >= now_ms - 30  * DAY_MS)
active_ads_90d  = sum(1 for l in latests if l >= now_ms - 90  * DAY_MS)
active_ads_180d = sum(1 for l in latests if l >= now_ms - 180 * DAY_MS)
```

**Skill 1 use:** for a keyword, count advertisers with `active_ads_30d >= 1` — those are the *live* competitors currently running on that keyword.

**Corpus check on Personio (all 75 captured page-1 ads):** most `latestImpressionAt` are within the last few months → active_ads_30d likely 40+, active_ads_90d likely 70+. Very active advertiser.

---

### WE11. `funnel_stage` — awareness / consideration / conversion / mixed

**Rule set:**
```python
video_share    = share_of_type("SPONSORED_VIDEO")
carousel_share = share_of_type("SPONSORED_UPDATE_CAROUSEL")
document_share = share_of_type("SPONSORED_UPDATE_NATIVE_DOCUMENT")
message_share  = share_of_type("SPONSORED_MESSAGE") + share_of_type("SPONSORED_INMAILS")
retargeting    = any(facet.facetName == "Audience" for ad, facet ...)   # Tier T

if video_share > 0.5 and not retargeting:          funnel_stage = "awareness"
elif document_share > 0.3 or message_share > 0.2:  funnel_stage = "conversion"
elif retargeting or carousel_share > 0.3:          funnel_stage = "consideration"
else:                                              funnel_stage = "mixed"
```

**Corpus examples:**
- Personio: 46 VIDEO + 29 STATUS_UPDATE, no retargeting visible → **awareness**
- HubSpot: 72 STATUS_UPDATE + 3 NATIVE_DOCUMENT → **mixed** (bordering awareness)
- Salesforce: 45 STATUS_UPDATE + 12 VIDEO + 13 NATIVE_DOCUMENT + 4 INMAILS → **mixed with conversion tilt**
- Peloton: 26 STATUS + 31 VIDEO + 16 MESSAGE → **awareness with conversion** — MESSAGE share pulls to conversion

**Failure case:** Tier T dependency — for US-only advertisers we can't see `retargeting`. Downgrade to "awareness or mixed" rather than defaulting either way.

---

### WE12. `impressions_midpoint`, `total_impressions_est_[lower|upper|midpoint]`, `campaign_size_tier`

**Per-ad midpoint:**
```python
mid = (totalImpressions["from"] + totalImpressions["to"]) / 2
```

**Company-level rollup (across only ads with adStatistics):**
```python
total_lower    = sum(ti["from"] for ti in ads_stats)
total_upper    = sum(ti["to"] for ti in ads_stats)
total_midpoint = (total_lower + total_upper) / 2
```

**`campaign_size_tier` (per-ad):**
```python
if mid < 5_000:     tier = "micro"
elif mid < 30_000:  tier = "small"
elif mid < 150_000: tier = "medium"
elif mid < 500_000: tier = "large"
else:               tier = "enterprise"
```

**Corpus check on Personio, page 1 element 0:** `totalImpressions = {from: 0, to: 1000}` → mid = 500 → tier = "micro". This is a small campaign inside a large advertiser — typical for a targeted A/B test creative.

**Skill 2 use:** side-by-side, "you ran N ads at avg midpoint M. Competitor ran N' ads at avg midpoint M'. Their reach is roughly M'/M × more" (with all the DSA-visible caveats).

---

### WE13. `linkedin_company_id` extraction

**Formula:**
```python
import re
m = re.search(r"/company/(\d+)", ad["details"]["advertiser"]["advertiserUrl"])
company_id = m.group(1) if m else None
```

**Corpus validation:** matches 100% of 1,075 ads. Ad ID from adUrl similarly:
```python
ad_id = re.search(r"/detail/(\d+)", ad["adUrl"]).group(1)
```
Also 100% match rate.

**Use:** these are your canonical identifiers for storage and de-duping. `linkedin_company_id` is comparable to what ZenABM stores; that's how you join user's own data (via ZenABM MCP) against Ad Library data (via LinkedIn API) in Skill 1 and Skill 2.

---

## Signal dependency graph (summary for skill authors)

Every signal falls into one of three tiers depending on prerequisites:

- **Tier N (works always, 100% coverage):** total_ads, ad_types_used, uses_video/carousel/document/message, ad_payer_differs, linkedin_company_id, restricted_ads_count.
- **Tier S (requires EU-visible impression data, 64.3% coverage; gate on impression_data_coverage != none):** is_currently_advertising, is_new_advertiser, is_dark_period, is_ramping_up, outreach_timing_score, impressions_midpoint, campaign_size_tier, active_ads_[N]d, country_impression_share, primary_market_country, campaign_duration_days.
- **Tier T (requires non-empty targeting, 64.3% coverage; same subset as S):** targets_job_roles, targets_specific_companies, uses_audience_targeting, uses_exclusions, targeting_dimensions_count, funnel_stage's retargeting piece.

**A skill that consumes signals must check `impression_data_coverage` and either use Tier N only OR degrade gracefully for Tier S/T when coverage is `none`.**

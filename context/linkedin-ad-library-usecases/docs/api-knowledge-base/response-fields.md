# Response Fields — Native Data

Complete field reference for the ad object returned by `GET /rest/adLibrary?q=criteria`. Every field below was observed in the 2026-07-03 corpus of 1,075 ads across 15 companies. Coverage percentages are calculated over that corpus.

**Field path notation:** dot for object access, `[]` for list-element access (e.g. `details.adStatistics.impressionsDistributionByCountry[].country`).

---

## Top-level ad object (100% present)

| Path | Type | Coverage | Example | Notes |
|---|---|---|---|---|
| `adUrl` | string | 100% | `https://www.linkedin.com/ad-library/detail/1470155666` | Pointer to LinkedIn's public preview page for this ad. Not part of the API response body itself — you'd have to scrape the URL to get the creative content, CTA, and landing URL. |
| `isRestricted` | bool | 100% | `false` | See `constraints.md § 11` — no `true` case observed in our corpus. Restricted-ad shape is theoretical. |
| `details` | object | 100% | (see below) | Container for everything meaningful. |

Fixtures: any `companies/*/page_1.json`.

---

## `details.advertiser` (100% present)

The advertiser identity. Three sub-fields, all always present.

| Path | Type | Coverage | Example | Notes |
|---|---|---|---|---|
| `details.advertiser.advertiserName` | string | 100% | `Personio` | Display name. What LinkedIn shows publicly. |
| `details.advertiser.advertiserUrl` | string | 100% | `https://www.linkedin.com/company/10180448` for company advertisers OR `https://www.linkedin.com/in/<slug>` for individual thought leaders | The numeric segment for `/company/<id>` is the canonical LinkedIn company ID — the safest identifier for de-duping. See `call-patterns.md § 9` for company-vs-individual disambiguation. |
| `details.advertiser.adPayer` | string | **99.8%** (3/1,563 ads had it missing) | `Personio SE & Co. KG` | Legal entity that paid for the ad. Often differs from `advertiserName` when an agency runs campaigns for a brand, or when the parent company pays. See `inferable-signals.md § F1b` for normalized comparison. **Handle as Optional in schema.** |

Fixture example: `companies/personio/page_1.json` → `.response.body.elements[0].details.advertiser`.

---

## `details.type` (100% present)

The ad format enum.

| Value | Corpus count | Notes / where to see |
|---|---|---|
| `SPONSORED_STATUS_UPDATE` | 601 | Dominant format — single image / text posts |
| `SPONSORED_VIDEO` | 316 | Video ads. Personio uses these heavily. |
| `SPONSORED_UPDATE_NATIVE_DOCUMENT` | 65 | Document/PDF ads. HubSpot, Salesforce use these. |
| `SPONSORED_UPDATE_CAROUSEL` | 48 | Multi-image carousel. BAE Systems, WeWork have examples. |
| `SPONSORED_MESSAGE` | 16 | Message ads (conversation format). Peloton has 16. |
| `TEXT_AD` | 12 | Text-only sidebar ads. ZenABM, Userpilot. |
| `SPONSORED_INMAILS` | 8 | Direct message (InMail) ads. Salesforce, Userpilot. |
| `$UNKNOWN` | 7 | LinkedIn's own classifier failed. Two subvariants — see below. |
| `JOBS_V2` | 2+ | Job promotion ad. `companies/bae-systems`, `phase-b/spotlight_hunt__zendesk.json`. |
| `FOLLOW_COMPANY_V2` | 1 | Dynamic "follow company" ad. `companies/peloton` — bare, no stats. |
| `SPONSORED_UPDATE_EVENT` | 1 | Event promotion ad. `phase-b/restricted_hunt__draftkings.json`. |
| `SPONSORED_UPDATE_JOB_POSTING` | 1 | Native job-posting ad (distinct from `JOBS_V2`). `phase-b/restricted_hunt__draftkings.json`. |

**Not observed** despite targeted hunting on 5 additional heavy-B2B advertisers (Adobe, Oracle, SAP, Workday, Zendesk — total ~125 additional ads inspected in `phase-b/spotlight_hunt__*.json`):
- `SPOTLIGHT_V2` — very rare or deprecated. Treat as theoretical.

**Advertiser URL format** matters for classifying the advertiser:
- `details.advertiser.advertiserUrl` starts with `.../company/<id>` → **company account** (dominant case)
- `details.advertiser.advertiserUrl` starts with `.../in/<slug>` → **individual person's account** (thought leaders running sponsored posts). See `call-patterns.md § 9`.

### `$UNKNOWN` subvariants

1. **Rich-with-stats** (`companies/alibaba/page_1.json` — 4 examples, `companies/meta/page_2.json` — 1 example). Ad has full `adStatistics` + `impressionsDistributionByCountry`. Likely a new/rare ad format LinkedIn's response schema hasn't been updated for.
2. **Bare-no-stats** (`companies/meta/page_1.json` — Metalforms case, `companies/salesforce/page_2.json`). Ad has `adTargeting: []`, no `adStatistics`. Correlates with fuzzy-search collision cases where the advertiser returned isn't the one searched for.

---

## `details.adTargeting` (100% container present, 64.3% non-empty)

List of targeting facets used in the campaign.

- **Container:** `details.adTargeting` — always present as a list.
- **Empty list `[]`:** 35.7% of ads — corresponds exactly to the same subset that has no `adStatistics` (i.e. non-EU targeting; DSA does not require disclosure).
- **Non-empty:** 64.3% of ads (692 ads with 1,606 targeting entries total).

### Per-entry shape

Each entry in `adTargeting` is an object:

| Path | Type | Coverage | Example |
|---|---|---|---|
| `details.adTargeting[].facetName` | string | 100% of non-empty entries | `Language`, `Location`, `Job`, ... |
| `details.adTargeting[].isIncluded` | bool | 100% | `true` |
| `details.adTargeting[].isExcluded` | bool | 100% | `false` |
| `details.adTargeting[].includedSegments` | list[string] | 100% (may be empty) | `["English"]` for Language, `[]` for Job |
| `details.adTargeting[].excludedSegments` | list[string] | 100% (may be empty) | `["Poland", "France"]` for Location |

### Facet name universe (all observed values)

| Facet name | Corpus count | Reveals segment values? |
|---|---|---|
| `Location` | 610 | **Yes — 100%** |
| `Language` | 609 | **Yes — 100%** |
| `Company` | 569 | No — 0% |
| `Job` | 539 | No — 0% |
| `Audience` | 419 | No — 0% |
| `Demographic` | 50 | No — 0% |
| `Member Interests and Traits` | 22 | No — 0% |
| `Education` | 7 | No — 0% |

**Hard rule:** for facets other than `Location` and `Language`, the API tells us the facet was used but always returns `includedSegments: []` and `excludedSegments: []`. No API call will ever give you the specific `Job` roles, `Company` accounts, or `Audience` segments that an advertiser targeted. See `constraints.md § 9`.

### Location segment values

The `Location` facet returns display-format strings (not URNs) — corpus examples: `"United States"`, `"United Kingdom"`, `"Poland"`, `"Ireland"`, `"Netherlands"`, `"Sweden"`, `"Cannes"`, `"Texas, United States"`. Note the mix of country, city, and country+region granularities.

### Language segment values

Also display-format strings — corpus examples: `"English"`, `"Español"`, `"Français"`, `"Deutsch"`. No language codes.

---

## `details.adStatistics` (64.3% present)

Present only when the ad had EU/EEA impressions. Absent for pure US/non-EU campaigns. See `constraints.md § 10` for the exhaustive DSA rule and per-company coverage table.

### Sub-fields

| Path | Type | Coverage (of ads with adStatistics) | Example | Notes |
|---|---|---|---|---|
| `details.adStatistics.firstImpressionAt` | int (epoch ms) | 100% | `1781795275387` | Unix milliseconds. Sample = ~2026-06. Historical range: ads from up to ~10 years back. |
| `details.adStatistics.latestImpressionAt` | int (epoch ms) | 100% | `1783053369656` | Same format. Difference from `firstImpressionAt` = campaign duration on EU-visible portion. |
| `details.adStatistics.totalImpressions` | object | 100% | `{"from": 0, "to": 1000}` | Bucketed range, never exact. See buckets below. |
| `details.adStatistics.totalImpressions.from` | int | 100% | `0` | Lower bound (inclusive). |
| `details.adStatistics.totalImpressions.to` | int | 100% | `1000` | Upper bound (exclusive). |
| `details.adStatistics.impressionsDistributionByCountry` | list | 100% | (see below) | Per-country % breakdown. |

### Impression buckets observed (12 tiers)

All 12 `(from, to)` pairs across corpus (see `test-matrix.md` for counts):

| from | to | Rough scale |
|---|---|---|
| 0 | 1,000 | Micro |
| 1,000 | 5,000 | Small |
| 5,000 | 10,000 | Small-medium |
| 10,000 | 20,000 | Medium |
| 20,000 | 30,000 | Medium |
| 30,000 | 50,000 | Medium-large |
| 50,000 | 100,000 | Large |
| 100,000 | 150,000 | Large |
| 150,000 | 200,000 | Enterprise |
| 200,000 | 300,000 | Enterprise |
| 300,000 | 500,000 | Enterprise |
| 500,000 | 1,000,000 | Enterprise-plus |

Higher tiers likely exist but weren't observed in our 1,075-ad corpus. Sample midpoint for a bucket = `(from + to) / 2` — best guess when a single number is needed, but propagate the range uncertainty (see `inferable-signals.md § impression-range-confidence`).

### `impressionsDistributionByCountry[]`

Per-country impression share. List length ranges from 1 to 155 in our corpus (globally-broad campaigns can distribute across 155 countries).

| Path | Type | Coverage | Example |
|---|---|---|---|
| `details.adStatistics.impressionsDistributionByCountry[].country` | string (URN) | 100% | `urn:li:country:DE` |
| `details.adStatistics.impressionsDistributionByCountry[].impressionPercentage` | float | 100% | `91.54362416107382` |

- **Country format:** URN with lowercase or uppercase ISO code — corpus consistently uses uppercase, e.g. `urn:li:country:US`, `urn:li:country:DE`. Strip the `urn:li:country:` prefix to get the 2-letter ISO code.
- **Percentage:** float, 0-100 range. **Sum across all countries in a single ad = 100** (verified on multiple ads).
- **198 distinct country codes** observed in the corpus (near-full ISO country list).

---

## Paging envelope

Not per-ad, but always in the response body:

| Path | Type | Notes |
|---|---|---|
| `paging.count` | int | Echoes the request `count` (usually 25). |
| `paging.start` | int | Echoes the request `start`. |
| `paging.total` | int | **True total matching this query.** Useful for scope planning. |
| `paging.links[]` | list | Present when more pages exist. |
| `paging.links[].rel` | string | `"next"` — presence indicates there's another page. |
| `paging.links[].href` | string | Relative URL for the next page. Server-canonicalized. |
| `paging.links[].type` | string | Always `"application/json"`. |

---

## Response headers of note

- `Content-Type: application/json` — always.
- `X-LI-UUID` — LinkedIn request UUID. Useful when opening a support ticket about a specific request.
- **`X-RateLimit-*` headers are NOT returned.** We captured every response header on our fixtures — LinkedIn does not expose remaining quota in headers.

---

## Complete null / absence table (single reference)

| Field | Absent when | Present when |
|---|---|---|
| `details.adStatistics` | Ad had no EU/EEA impressions | Ad had EU/EEA impressions |
| `details.adTargeting[]` (empty list) | Same as above — DSA doesn't require targeting disclosure for non-EU ads | Same — non-empty when EU-visible |
| `details.adTargeting[].includedSegments` / `excludedSegments` (empty lists) | Facet is one of {Job, Company, Audience, Demographic, Member Interests, Education} — LinkedIn hides specific values | Facet is Language or Location |
| `details.adStatistics.impressionsDistributionByCountry` | Only if `adStatistics` itself absent | Otherwise always present with ≥1 entry |
| `paging.links` (empty) | Last page (no next) | More pages exist |
| Every other field above | Never — always present when its parent is present | — |

# Constraints — What the API cannot do

Every constraint below is either backed by a captured fixture or by a specific behavior observed during the 2026-07-03 audit. All fixture paths are relative to `docs/api-knowledge-base/fixtures/`.

---

## 1. Rejected query parameters (400 QUERY_PARAM_NOT_ALLOWED)

The API returns HTTP 400 for these parameters. **The client must not send them** — some SDKs and the pre-audit `linkedin_client.py` sent them silently.

| Param | Fixture | Error code |
|---|---|---|
| `advertiserUrn` | `negative/advertiserUrn.json` | `QUERY_PARAM_NOT_ALLOWED` on `advertiserUrn` |
| `advertiserPageUrl` | `negative/advertiserPageUrl.json` | `QUERY_PARAM_NOT_ALLOWED` on `advertiserPageUrl` |
| `payer` | `negative/payer.json` | `QUERY_PARAM_NOT_ALLOWED` on `payer` |
| `searchStartDate` | `negative/searchStartDate.json` | `QUERY_PARAM_NOT_ALLOWED` on `searchStartDate` |
| `dateRange.start.{day,month,year}` | `negative/dateRange_start.json` | Multiple `QUERY_PARAM_NOT_ALLOWED` on dateRange fields |
| `adType` | `auxiliary/ad_type_filter__video.json` | `QUERY_PARAM_NOT_ALLOWED` on `adType` |

**Implication:** date filtering, ad-type filtering, exact-company (URN) matching are **all client-side operations** — filter the results after fetching.

---

## 2. The `countries` parameter is documented but effectively unusable

LinkedIn's own API docs list `countries` as a supported param. **It is not** with any encoding we could find in this audit.

Encodings tested (all returned 400 `FIELD_INVALID: array type is not backed by a DataList` on version 202601):

- `countries=US` (comma-joined string, what our client sent)
- `countries=List(US)` (Rest.li 2.0 array syntax)
- `countries=List(urn:li:country:US)`, `countries=List(urn:li:country:us)` (URN variants)
- `countries=urn:li:country:US` (single URN)
- `countries=(US)`, `countries=Set(US)`, `countries=List()`
- `countries=US&countries=GB` (multi-value)
- `countries[0]=US` (bracket array — got `QUERY_PARAM_NOT_ALLOWED countries[0]`)

Full probe results: `scripts/probe_countries_encoding.py` and the negative fixtures.

**Conclusion:** `countries` is recognized as a param name (the bracket variant shows the param name is known) but **no value format the audit tried is accepted**. Treat as unsupported. Do country filtering client-side on `details.adStatistics.impressionsDistributionByCountry`.

**Bug flagged in current client code:** `src/services/linkedin_client.py` line 113 passes `countries=",".join(countries)`. This call has never returned filtered results — every request with a `countries` value returns 400 and the response gets caught and returned as `{"elements": [], ...}`. Country filtering has been silently broken.

---

## 3. Date filtering is not supported at all

- `searchStartDate` — 400 (`negative/searchStartDate.json`)
- `dateRange.*` — 400 (`negative/dateRange_start.json`)
- Any date range must be applied client-side after fetching, using `details.adStatistics.firstImpressionAt` / `latestImpressionAt` (epoch millis).

---

## 4. LinkedIn-Version header must be recent

Tested versions:

- `202601` (Jan 2026) — accepted ✅
- `202409` (Sep 2024, currently in `.env`) — accepted ✅
- `202501` (Jan 2025) — `426 NONEXISTENT_VERSION` ❌
- `202504` (Apr 2025) — `426 NONEXISTENT_VERSION` ❌

So the version window is not "everything current-or-older". LinkedIn actively deprecates older versions. Rough rule from this audit: versions must be within ~12 months of the current date; older ones are 426'd. Version 202409 is the current sweet spot (works, hasn't been deprecated as of 2026-07-03).

---

## 5. Ad ordering: deterministic, roughly chronological, but jittery

Two facts, both empirically confirmed in Phase B (2026-07-03):

1. **Deterministic per query** — the same call twice returns the identical 25 ads in the identical order. Fixture pair: `phase-b/determinism__personio_call_1.json` and `_call_2.json`.
2. **Roughly chronological, newer first** — deep pagination on Personio: start=0 returned ads from ~last 2 months, start=500 from ~2 months back, start=1500 from ~5 months back, start=2500 from ~11 months back. Fixtures: `phase-b/deep_pagination__personio_start_{500,1500,2500}.json`.

**BUT** — within any given page, ads are NOT strictly sorted by date. There's meaningful jitter. And historical batches from before the ordering algorithm's window may not fit the chronological pattern.

**Do not implement "stop when we hit old ads" pagination** — even in mostly-chronological ordering, a few older ads sneak into earlier pages. The safer pattern is: paginate the full result set (bounded by budget), then filter client-side by date.

---

## 6. Rate limits

Empirically confirmed during 2026-07-03 capture:

- **Burst threshold** — hit 429 after ~9-10 requests in ~30 seconds (`companies/notion/page_2.json` — 429 on 10th request in burst)
- **Recovery** — ~35 seconds is safe; ~4 seconds between requests is *not* enough when running many companies back-to-back. Our capture script's 4s inter-page sleep + 6s inter-company sleep worked reliably in round 2.
- **429 body** — same JSON envelope, status 429, `serviceErrorCode` present. LinkedIn does NOT return `Retry-After` header.
- **Daily quota** — 1,000 requests/day per user token (per LinkedIn Developer Portal). App-wide 10,000/day is a higher ceiling. Resets at midnight UTC.
- **Response headers do NOT expose remaining quota** — `X-RateLimit-*` headers were not present in any 200 response we captured. You cannot know how much of the daily quota you have left without hitting a 429.

---

## 7. Token expiry

- Access tokens have a limited lifetime. Ours was ~26 days old and expired (2026-07-03).
- Expiry surface: HTTP 401 with `serviceErrorCode: 65602`, `code: EXPIRED_ACCESS_TOKEN` — fixture: `negative/expired_token.json`.
- **No automatic refresh** in the current client code. Must be manually regenerated via LinkedIn Developer Portal.

---

## 8. What the API does NOT return (deliberate omissions)

The Ad Library search endpoint returns **metadata only**. It does not include:

- **Ad creative content** — no text, headline, image URLs, video URLs. Only `adUrl` (a pointer to LinkedIn's public preview page).
- **CTA button text** or **landing page URL** — must scrape the `adUrl` HTML page.
- **Click / engagement metrics** — only impression buckets.
- **Actual spend** — not exposed. Impressions are the only volumetric.
- **Audience size estimate** — not exposed.
- **Specific segment values for most targeting facets** — see § 9.

---

## 9. Targeting-facet segment obscuring — hard asymmetric rule

Across 1,606 targeting entries in 1,075 ads (15 companies, 2026-07-03 corpus):

| Facet name | Occurrences | Reveals segment names? |
|---|---|---|
| `Location` | 610 | **Yes — 100%** |
| `Language` | 609 | **Yes — 100%** |
| `Company` | 569 | No — 0% |
| `Job` | 539 | No — 0% |
| `Audience` | 419 | No — 0% |
| `Demographic` | 50 | No — 0% |
| `Member Interests and Traits` | 22 | No — 0% |
| `Education` | 7 | No — 0% |

The API always tells us *which facets* were used in targeting, and always tells us the **specific values** for `Location` and `Language`. It **never** exposes specific values for the other six facets — we only get `isIncluded: true` / `isExcluded: true` flags and `includedSegments: []` / `excludedSegments: []` empty arrays.

**Implication:** you can say "advertiser targeted by Job function" but not "advertiser targeted CFOs specifically" — never possible via this API.

---

## 10. Impression data is only present for EU/EEA-visible ads

Per LinkedIn DSA compliance, `details.adStatistics` (and all its sub-fields — `totalImpressions`, `impressionsDistributionByCountry`, `firstImpressionAt`, `latestImpressionAt`) is populated **only when the ad had EU/EEA impressions**. For pure US-targeted or non-EU-targeted campaigns:

- `adStatistics` is absent (not `null` — missing entirely from the ad object)
- `adTargeting` is present but the list is empty `[]`

Coverage from our corpus:

| Company | Ads w/ adStatistics | Ads w/ adTargeting non-empty | Interpretation |
|---|---|---|---|
| Personio | 71/75 (95%) | same | EU-headquartered, EU-targeted |
| HubSpot | 72/75 (96%) | same | Heavy EU ad presence |
| Alibaba | 75/75 (100%) | same | Global campaigns include EU |
| Novartis | 62/75 (83%) | same | Global pharma with EU |
| Meta | 44/75 (59%) | same | Mixed US/EU |
| Notion | 9/25 (36%) | same | Mixed |
| Miro | 23/75 (31%) | same | Mixed |
| BAE Systems | 21/75 (28%) | same | Mostly non-EU (India-heavy) |
| WeWork | 13/75 (17%) | same | Mostly non-EU |
| Peloton | 9/75 (12%) | same | Reduced EU activity |
| HSBC | 7/75 (9%) | same | Global bank, EU is small slice |
| Salesforce | 6/75 (8%) | same | US-headquartered, mostly hidden |

**Big inference caveat:** `impressionsDistributionByCountry` only characterizes the EU-visible subset. A LATAM-headquartered company like Rappi shows 99% European distribution — but that's because its LATAM ads are DSA-hidden. **Never use `impressionsDistributionByCountry` alone to infer a company's true target market for non-EU-headquartered advertisers.** See `inferable-signals.md § true-target-market` for a safer inference formula.

---

## 11. Restricted ads — behavior unobserved (round 2 also negative)

Zero ads with `isRestricted: true` across our expanded corpus (round 1: 1,075 ads incl. pharma/defense/finance/tech; Phase B: 4 more targeted queries — Pfizer, DraftKings, MoveOn, Aurora Cannabis = ~62 additional ads spanning gambling/political/cannabis/pharma). Two possible reasons:

1. LinkedIn's Ad Library public API does not surface restricted ads to third-party access tokens
2. Our token's OAuth scope does not include restricted-ad visibility

Per LinkedIn's engineering blog, restricted ads are supposed to have `restrictionDetails` and hide `advertiserName`, `payer`, and `ad preview`. **We cannot validate that shape from our fixtures.** Any code path that handles `isRestricted: true` is currently theoretical and should be labelled as such.

Fixtures: `phase-b/restricted_hunt__{pfizer,draftkings,moveon,aurora_cannabis}.json`.

---

## 12. Fuzzy-search collisions

The `advertiser` param is a fuzzy name match. Search collisions are frequent and can return completely unrelated companies:

- `advertiser=Meta` returned "Metalforms" (`companies/meta/page_*.json` — 1 out of 75 was Metalforms, but the collision demonstrates the pattern; see `$UNKNOWN` typed record in that fixture)
- `advertiser=Peloton` returned "Peloton Consulting Group" (a completely different company — `companies/peloton/page_*.json` shows one `FOLLOW_COMPANY_V2` ad from Peloton Consulting Group, not the fitness Peloton)

**Implication:** any pipeline that consumes results must filter by a known LinkedIn company ID (from `details.advertiser.advertiserUrl` — parsable as `/company/<id>`) or the returned set will be contaminated. This is what `batch_lookup.py` already does with its ID-match step.

---

## 13. Not-found path

Searching for a non-existent advertiser returns HTTP 200 with `elements: []` and `paging.total: 0`. Not an error — clean empty response. Fixture: `auxiliary/not_found__fake_company.json`.

---

## 14. Pagination cap: `count` maximum is 25

Per LinkedIn docs and confirmed in every fixture — `count > 25` is clipped to 25 server-side. Deep pagination via `start` is supported.

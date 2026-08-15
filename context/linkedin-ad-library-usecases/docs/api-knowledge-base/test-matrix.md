# Test Matrix — What we captured and why

Captured 2026-07-03 via `scripts/capture_fixtures.py`. All fixtures under `fixtures/`.

## Company fixtures — diversity axes exercised

| Slug | Advertiser | Hypothesis | Result |
|---|---|---|---|
| `personio` | Personio | EU-headquartered → `impression_data_coverage = full` | ✅ 71/75 ads have `adStatistics` (95%) |
| `userpilot` | Userpilot | Mixed EU+US SaaS → partial coverage | ✅ 66/75 with stats (88%) |
| `zenabm` | ZenABM | Small ABM SaaS, edge on ad count | ✅ 57/75 with stats (76%), `paging.total = 243` |
| `salesforce` | Salesforce | US-headquartered giant → `coverage = none` | ✅ 6/75 with stats (8%) — validates US-only path |
| `notion` | Notion | Variable cadence, edge for is_dark_period | ⚠️ Only 25 elements captured (hit 429 on page 2); 9/25 with stats (36%) |

## Auxiliary query probes

| Slug | Query | Purpose | Result |
|---|---|---|---|
| `keyword_only__product_management` | `keyword=product management` | Shape of broad keyword search | ✅ 200, 25 elements, `paging.total = 410,199` — first advertiser was Wharton Online |
| `country_filter__us` | `countries=US` | Country filter with ISO code | ❌ 400 `FIELD_INVALID: array type is not backed by a DataList` |
| `country_filter__gb` | `countries=GB` | Confirm `GB` (not `UK`) code | ❌ 400 same error |
| `ad_type_filter__video` | `adType=SPONSORED_VIDEO` | Ad-type filter | ❌ 400 `QUERY_PARAM_NOT_ALLOWED` |
| `not_found__fake_company` | `advertiser=zzz_nonexistent...` | Not-found path | ✅ 200, `elements=[]`, `paging.total=0` |

## Negative-test fixtures (all confirmed 400)

| Slug | Param sent | Response |
|---|---|---|
| `advertiserUrn` | `advertiserUrn=urn:li:organization:1441` | 400 `QUERY_PARAM_NOT_ALLOWED` |
| `advertiserPageUrl` | `advertiserPageUrl=<company>` | 400 `QUERY_PARAM_NOT_ALLOWED` |
| `dateRange_start` | `dateRange.start.{day,month,year}=...` | 400 (multiple validation errors) |
| `searchStartDate` | `searchStartDate=2025-01-01` | 400 `QUERY_PARAM_NOT_ALLOWED` |
| `payer` | `payer=<name>` | 400 `QUERY_PARAM_NOT_ALLOWED` |
| `expired_token` | (401 fixture, not 400) | 401 `EXPIRED_ACCESS_TOKEN` `serviceErrorCode=65602` |

## Countries encoding probe (`scripts/probe_countries_encoding.py`)

Tested 7 Rest.li 2.0 encoding candidates + 3 LinkedIn-Version values. **None accepted `countries`**:

| Encoding | Version 202601 | Version 202501 | Version 202504 |
|---|---|---|---|
| `countries=US` | 400 FIELD_INVALID | 426 NONEXISTENT_VERSION | 426 |
| `countries=List(US)` | 400 FIELD_INVALID | 426 | 426 |
| `countries=List(urn:li:country:US)` | 400 FIELD_INVALID | 426 | 426 |
| `countries=urn:li:country:US` | 400 FIELD_INVALID | 426 | 426 |
| `countries=US&countries=GB` | 400 ILLEGAL_ARGUMENT | — | — |
| `countries=List(US,GB)` | 400 FIELD_INVALID | 426 | 426 |
| `countries[0]=US` | 400 `QUERY_PARAM_NOT_ALLOWED countries[0]` | — | — |
| `countries=Set(US)` | 400 FIELD_INVALID | 426 | 426 |
| `countries=(US)` | 400 FIELD_INVALID | 426 | 426 |
| `countries=List()` | 400 FIELD_INVALID | 426 | 426 |
| `countries=List(urn:li:country:us)` (lowercase URN) | 400 FIELD_INVALID | 426 | 426 |

**Conclusion:** `countries` param name is recognized (encoding G returns `QUERY_PARAM_NOT_ALLOWED` for the bracketed variant, meaning the plain name IS known) but no value format we tested is accepted. Treat as unsupported until LinkedIn documents an accepted encoding. Do country filtering client-side on `impressionsDistributionByCountry`.

## Ad types actually observed in fixtures (75 ads × 5 companies = 375 ads)

Union of `details.type` values seen:

- `SPONSORED_STATUS_UPDATE` (dominant — 222 ads)
- `SPONSORED_VIDEO` (62 ads)
- `SPONSORED_UPDATE_NATIVE_DOCUMENT` (20 ads)
- `SPONSORED_UPDATE_CAROUSEL` (2 ads — Notion only)
- `SPONSORED_INMAILS` (6 ads — Salesforce, Userpilot)
- `TEXT_AD` (12 ads — ZenABM, Userpilot)
- `$UNKNOWN` (1 ad — Salesforce) ⚠️ **NEW — undocumented, not in current `AD_TYPE_MAP`**

**Not observed** (would need targeted captures to validate their shape):
- `SPOTLIGHT_V2`
- `FOLLOW_COMPANY_V2`
- `JOBS_V2`
- `SPONSORED_MESSAGE`
- `SPONSORED_UPDATE_EVENT`

## Notable gaps / uncaptured cases (for future capture rounds)

- **`isRestricted = true` ad** — none seen in any of the 375 ads; shape of restriction fields untested
- **US-only company with true dark period** — Salesforce is US-only but currently active; need a US-only company that stopped ~90+ days ago to validate `is_dark_period` NOT firing incorrectly
- **The 5 rare ad types** above
- **Very small advertiser** (<10 ads) — smallest we have is ZenABM at 243 total

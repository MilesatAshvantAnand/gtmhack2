# Endpoints & Request Shape

The Ad Library exposes a single search endpoint. This doc is the definitive reference for how to call it and what params work.

> **See also:** [`call-patterns.md`](./call-patterns.md) is the case-based companion to this doc — for every possible way to call the API (including edge cases: empty query, non-ASCII, combined advertiser+keyword, pagination edges), it shows the exact response you get and why. If you're implementing against this API, start there.

---

## Endpoint

```
GET https://api.linkedin.com/rest/adLibrary?q=criteria
```

The `q=criteria` finder parameter is required — it tells LinkedIn which finder we're using. Without it: 400.

---

## Required headers

| Header | Value | Note |
|---|---|---|
| `Authorization` | `Bearer <access_token>` | See `constraints.md § 7` on token expiry |
| `LinkedIn-Version` | `202409` (or any accepted version) | See `constraints.md § 4` — versions expire |
| `X-Restli-Protocol-Version` | `2.0.0` | Required for the array-parameter syntax |

Every 200 response fixture (e.g. `companies/personio/page_1.json`) was made with these three headers.

---

## Accepted query parameters (confirmed by fixtures)

| Param | Type | Fixture proof | Notes |
|---|---|---|---|
| `q` | string | Every fixture | Always `criteria`. |
| `advertiser` | string | Every company fixture | **Fuzzy match**. Collisions are common — see `constraints.md § 12`. |
| `keyword` | string | `auxiliary/keyword_only__product_management.json` | Full-text search of ad copy. Can be combined with `advertiser`. |
| `start` | int | Every page ≥ 2 | Pagination offset. |
| `count` | int, **must be 1–25** | Every fixture | `count > 25` returns 400 (fixture `call-patterns/17_count_50_should_clip_to_25.json`). `count = 0` returns 200 with `elements: []` (fixture `18_count_0.json`). |

**Nothing else works.** See `constraints.md § 1` for the full rejected-params list.

---

## Response envelope

Every successful (200) response has this shape:

```json
{
  "elements": [ { ...ad... }, ... ],
  "paging": {
    "count": 25,
    "start": 0,
    "total": 2755,
    "links": [
      { "rel": "next", "href": "/rest/adLibrary?...&start=25", "type": "application/json" }
    ]
  }
}
```

- `elements` — list of ads. Shape documented in `response-fields.md`.
- `paging.total` — the true count of matching ads for this query. **Present in every 200 fixture.** Useful for estimating scope before deep pagination.
- `paging.links[].rel = "next"` — presence of a "next" link indicates there are more pages. When absent, we've reached the end.

Confirmed sample values of `paging.total`:

| Query | total |
|---|---|
| `advertiser=Salesforce` | 9,403 |
| `advertiser=Notion` | 7,065 |
| `advertiser=Personio` | 2,755 |
| `advertiser=HubSpot` | inspectable in `companies/hubspot/page_1.json` |
| `advertiser=ZenABM` | 243 |
| `keyword=product management` | 410,199 |
| `advertiser=zzz_nonexistent_advertiser_xyz` | 0 |

---

## Error response shapes

All error responses use LinkedIn's standard Rest.li error envelope:

### 400 QUERY_PARAM_NOT_ALLOWED
```json
{
  "errorDetailType": "com.linkedin.common.error.BadRequest",
  "message": "Invalid param. Please see errorDetails for more information.",
  "errorDetails": {
    "inputErrors": [
      { "code": "QUERY_PARAM_NOT_ALLOWED",
        "input": { "inputPath": { "fieldPath": "adType" } } }
    ]
  },
  "status": 400
}
```
Fixtures: `negative/advertiserUrn.json`, `negative/advertiserPageUrl.json`, `negative/payer.json`, `negative/searchStartDate.json`, `auxiliary/ad_type_filter__video.json`.

### 400 FIELD_INVALID (bad value for a valid param name)
```json
{
  "errorDetailType": "com.linkedin.common.error.BadRequest",
  "message": "Multiple errors occurred during param validation. ...",
  "errorDetails": {
    "inputErrors": [
      { "code": "FIELD_INVALID",
        "description": "ERROR :: /value :: array type is not backed by a DataList",
        "input": { "inputPath": { "fieldPath": "countries/value" } } }
    ]
  },
  "status": 400
}
```
Fixtures: `auxiliary/country_filter__us.json`, `country_filter__gb.json`.

### 401 EXPIRED_ACCESS_TOKEN
```json
{
  "status": 401,
  "code": "EXPIRED_ACCESS_TOKEN",
  "serviceErrorCode": 65602,
  "message": "The token used in the request has expired"
}
```
Fixture: `negative/expired_token.json`.

### 426 NONEXISTENT_VERSION
Returned when `LinkedIn-Version` header value is not a currently-supported version window. Body wraps a standard error envelope. See `constraints.md § 4`.

### 429 Rate limited
Returned when burst rate limit exceeded. No `Retry-After` header. Fixture: any Notion page_2 attempts during round 1 (subsequently overwritten by successful round-2 retry; the shape is captured in the log). ~35s recovery observed.

---

## Reference: `paging.total` as a workload estimator

Given the max-page depth of `⌈total / 25⌉` and the ~1,000 requests/day quota, `paging.total` should be checked before starting a deep pagination on any single advertiser. Extreme cases in our corpus:

- Salesforce (9,403 total) → 377 pages → **>1 day of quota** to fully paginate one advertiser
- A keyword-only search on `product management` (410,199 total) → 16,408 pages → effectively impossible to exhaust

Any pipeline that paginates should either sample early pages (as our capture script does with `MAX_PAGES = 3`) or set a much larger per-run budget with quota-awareness.

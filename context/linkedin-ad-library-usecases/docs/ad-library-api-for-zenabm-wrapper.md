# LinkedIn Ad Library API — integration brief for a ZenABM wrapper

> **Purpose:** everything needed to build a ZenABM-side wrapper/proxy over the LinkedIn Ad Library, so the competitor skill calls **ZenABM's API** and ZenABM makes the LinkedIn calls on the user's behalf (more control, server-side metering, source hidden).
> **Source of truth:** this is a distilled export of `docs/api-knowledge-base/` (fixture-backed audit, 2026-07-03; 1,075 ads / 15 companies) and the working client `core/client.py`. Every claim below is backed by a captured fixture.

---

## 1. What the skill actually asks the Ad Library for

The skill only ever does **public competitor/keyword ad lookups**. Two call shapes, both against one endpoint:

1. **By advertiser** (the primary path — "profile this competitor's ads"): search by company name, then filter results to the exact advertiser by canonical company ID.
2. **By keyword** (discovery — "who advertises on this topic"): full-text search of ad copy.

It then paginates (25/page), and derives everything from **ad metadata only** (formats, impression-range buckets, first/last impression dates, per-country impression %, which targeting facets were used). It never needs write access, never touches the user's own account, and uses no other LinkedIn endpoint.

---

## 2. Endpoint, headers, auth

```
GET https://api.linkedin.com/rest/adLibrary?q=criteria
```

**Required headers:**

| Header | Value | Notes |
|---|---|---|
| `Authorization` | `Bearer <access_token>` | Token expires ~26 days → HTTP 401 `serviceErrorCode: 65602` / `EXPIRED_ACCESS_TOKEN`. No auto-refresh; regenerate via LinkedIn Developer Portal. |
| `LinkedIn-Version` | e.g. `202601` | Must be a currently-supported version window. `202601` and `202409` work today; `202501`/`202504` returned `426 NONEXISTENT_VERSION`. Rule of thumb: keep within ~12 months of "now" and re-verify. |
| `X-Restli-Protocol-Version` | `2.0.0` | Required. |

No OAuth handshake at call time — it's a bearer access token. **For the wrapper, ZenABM holds/rotates the token(s) server-side; the skill never sees a LinkedIn token.**

---

## 3. Accepted query parameters (the ONLY ones that work)

| Param | Type | Required | Notes |
|---|---|---|---|
| `q` | string | yes | Always `criteria`. Missing → 400. |
| `advertiser` | string | one of advertiser/keyword | **Fuzzy** name match (see §6). |
| `keyword` | string | one of advertiser/keyword | Full-text match of ad body copy. Can combine with `advertiser` (ANDed). |
| `start` | int | no | Pagination offset. |
| `count` | int **1–25** | no | `count > 25` → 400; server caps at 25. `count = 0` → 200 empty. |

**Everything else returns 400** and must NOT be sent: `countries`, `adType`, `advertiserUrn`, `advertiserPageUrl`, `payer`, `searchStartDate`, `dateRange.*`. So **date, country, and ad-type filtering are all client-side** — fetch, then filter. (If the wrapper wants to offer those as query params, it must implement the filtering itself over the returned data.)

---

## 4. Example requests (real call shapes the skill makes)

```
# Competitor by name (then filter to the real company by ID — see §6):
GET https://api.linkedin.com/rest/adLibrary?q=criteria&advertiser=Personio&start=0&count=25
GET https://api.linkedin.com/rest/adLibrary?q=criteria&advertiser=Personio&start=25&count=25   # page 2

# Keyword discovery:
GET https://api.linkedin.com/rest/adLibrary?q=criteria&keyword=product%20analytics&start=0&count=25

# Combined (narrower):
GET https://api.linkedin.com/rest/adLibrary?q=criteria&advertiser=Personio&keyword=hiring&start=0&count=25
```

Confirmed `paging.total` scale for sizing: `advertiser=Salesforce` → 9,403; `Notion` → 7,065; `Personio` → 2,755; `ZenABM` → 243; `keyword=product management` → 410,199; non-existent advertiser → 0.

---

## 5. Response shape (the data we get)

**Envelope:**
```json
{
  "elements": [ { /* ad */ } ],
  "paging": {
    "count": 25, "start": 0, "total": 2755,
    "links": [ { "rel": "next", "href": "/rest/adLibrary?...&start=25", "type": "application/json" } ]
  }
}
```

**One ad element (only the fields the skill consumes — pass these through in the wrapper):**
```jsonc
{
  "adUrl": "https://www.linkedin.com/ad-library/detail/1470155666",  // 100%; only pointer to creative (must scrape for copy/CTA/landing)
  "isRestricted": false,                                             // 100%
  "details": {
    "type": "SPONSORED_VIDEO",                                       // 100%; format enum (see below)
    "advertiser": {
      "advertiserName": "Personio",                                 // 100%
      "advertiserUrl": "https://www.linkedin.com/company/10180448",  // 100%; /company/<id> = canonical ID; /in/<slug> = individual
      "adPayer": "Personio SE & Co. KG"                             // 99.8% (Optional)
    },
    "adStatistics": {                                                // 64.3% — present ONLY for EU/EEA-visible ads (DSA). Absent for US-only.
      "firstImpressionAt": 1781795275387,                            // epoch ms
      "latestImpressionAt": 1783053369656,                           // epoch ms
      "totalImpressions": { "from": 0, "to": 1000 },                 // bucketed range, never exact (12 tiers, 0–1M+)
      "impressionsDistributionByCountry": [
        { "country": "urn:li:country:DE", "impressionPercentage": 91.54 }  // sums to 100 per ad
      ]
    },
    "adTargeting": [                                                 // 100% container; 64.3% non-empty (empty for non-EU ads)
      { "facetName": "Location", "isIncluded": true, "isExcluded": false,
        "includedSegments": ["Germany"], "excludedSegments": [] }
    ]
  }
}
```

**`details.type` values observed:** `SPONSORED_STATUS_UPDATE` (601), `SPONSORED_VIDEO` (316), `SPONSORED_UPDATE_NATIVE_DOCUMENT` (65), `SPONSORED_UPDATE_CAROUSEL` (48), `SPONSORED_MESSAGE` (16), `TEXT_AD` (12), `SPONSORED_INMAILS` (8), `$UNKNOWN` (7), plus rare `JOBS_V2`, `FOLLOW_COMPANY_V2`, `SPONSORED_UPDATE_EVENT`, `SPONSORED_UPDATE_JOB_POSTING`.

---

## 6. Gotchas the wrapper MUST handle

1. **Fuzzy advertiser collisions.** `advertiser=Meta` returns Metalforms; `advertiser=Peloton` returns "Peloton Consulting Group." **Always filter results to the intended advertiser by the numeric ID in `advertiserUrl` (`/company/<id>`).** A company-name string alone is not safe. (This is why a wrapper endpoint keyed on company ID/URL is more valuable than name.)
2. **Slug ≠ ID.** A LinkedIn company-page URL uses a vanity slug (`/company/personio`); the Ad Library keys ads by numeric ID (`/company/10180448`). The wrapper should resolve slug→numeric ID (or accept the numeric ID) — the current skill searches by name and filters by ID, which is imperfect. **This is the single biggest correctness win a wrapper can add.**
3. **Rate limits (no headers to tell you where you stand):** ~9–10 requests / 30s burst → **429 with no `Retry-After`** (~35s recovery); **1,000 requests/day per user token** (app-wide 10,000/day), resets midnight UTC; no `X-RateLimit-*` headers. → wrapper should pool tokens, queue/throttle, and **cache** (ads change slowly; cache by query+page).
4. **`count` ≤ 25**; deep pagination via `start`. Ordering is deterministic but jittery, roughly newest-first — **never "stop when you hit old ads."** Paginate to a budget, filter by date client-side.
5. **`paging.total` up front** lets you size a job before paginating (Salesforce = 9,403 ads = 377 pages = >1 day of one token's quota). Use it to guard.

---

## 7. What the API does NOT return (so the wrapper can't either, without scraping)

- **No ad creative** — no text, headline, image/video URLs, CTA, or landing URL. Only `adUrl` (scrape the public preview page for creative).
- **No clicks/engagement, no spend, no audience size.** Impression **ranges** are the only volumetric.
- **Targeting segment values are hidden** for all facets except `Location` and `Language`. You get "targeted by Job/Company/Audience" (the facet was used) but never the specific roles/accounts/segments.
- **`adStatistics` is EU/EEA-only** (DSA). US-only advertisers return no impression data and empty targeting — treat as *unknown*, never *zero*. And **`impressionsDistributionByCountry` reflects only the EU-visible slice** — do not infer a non-EU company's true target market from it.

---

## 8. Recommended ZenABM wrapper surface

Two clean endpoints cover 100% of the skill's needs:

- `GET /ads/by-advertiser?company=<url|id|name>&max=<n>` → resolve to numeric company ID (§6.2), paginate, filter to that ID (§6.1), return the normalized ad list from §5.
- `GET /ads/by-keyword?q=<phrase>&max=<n>` → paginate keyword search, return normalized ads (+ `total` for scope).

Server-side, ZenABM should own: **token storage + rotation** (before the ~26-day expiry), **version pinning**, **rate-limit pooling + queueing + caching + daily-quota accounting** across all users, and (optionally) the client-side **filters** (date/country/format) exposed as query params. This gives ZenABM: metering/enforcement of the free tier server-side, the LinkedIn source hidden from the client, and a single connector the skill can call (the "MCP-native" path) instead of pasting a LinkedIn token.

---

*Backing detail: `docs/api-knowledge-base/{endpoints,constraints,response-fields,call-patterns}.md` and `fixtures/` in this repo; client reference implementation: `core/client.py`.*

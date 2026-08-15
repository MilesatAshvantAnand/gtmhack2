# LinkedIn Ad Library API - Official Documentation

> ⚠️ **SUPERSEDED (2026-07-03).** This file was written from LinkedIn's public docs before we did our own audit. Several claims in this file are wrong or incomplete — for example, LinkedIn's docs list `countries` and `adType` as supported params, but they don't work in practice.
>
> **Use [`api-knowledge-base/`](api-knowledge-base/) instead.** That's a fixture-backed audit that validates every claim against real captured responses. Specifically:
> - [`api-knowledge-base/endpoints.md`](api-knowledge-base/endpoints.md) — accepted params (validated)
> - [`api-knowledge-base/constraints.md`](api-knowledge-base/constraints.md) — rejected params + real bugs
> - [`api-knowledge-base/call-patterns.md`](api-knowledge-base/call-patterns.md) — case-based "for every call, what response"
> - [`api-knowledge-base/response-fields.md`](api-knowledge-base/response-fields.md) — every field with coverage stats
>
> Kept here for historical reference only.

---

**Source:** https://www.linkedin.com/ad-library/api/ads

**Last Updated:** 2026-02-03 (obsolete — see supersession note above)

---

## Endpoint

```
GET https://api.linkedin.com/rest/adLibrary?q=criteria
```

## Required Headers

| Header | Value |
|--------|-------|
| `X-RestLi-Protocol-Version` | `2.0.0` |
| `Linkedin-Version` | `202409` (or current version) |
| `Authorization` | `Bearer {ACCESS_TOKEN}` |

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `keyword` | String | Optional | Keyword to search in ad content. Multiple keywords separated by spaces are treated as logical AND. |
| `countries` | String | Optional | Comma-separated country codes (e.g., "US,UK,DE") |
| `advertiser` | String | Optional | Advertiser name search (fuzzy match). |
| `start` | Integer | Optional | Pagination start index (default: 0) |
| `count` | Integer | Optional | Number of results per page. **Maximum: 25** |

### IMPORTANT: Unsupported Parameters

The following parameters are **NOT SUPPORTED** and will cause a 400 error:
- `advertiserUrn` - LinkedIn does NOT support exact company ID matching
- `dateRange` - Despite being mentioned in some docs, this returns QUERY_PARAM_NOT_ALLOWED
- `dateRange.start.day/month/year` - Not allowed
- `dateRange.end.day/month/year` - Not allowed
- `searchStartDate` / `searchEndDate` - Not allowed

**Date filtering must be done client-side after fetching results.**

## Countries Format

Simple comma-separated country codes:
```
countries=US,UK,DE
```

Common country codes:
- `US` - United States
- `GB` - United Kingdom (note: GB not UK)
- `DE` - Germany
- `FR` - France
- `CA` - Canada

## Sample Request

```bash
curl -X GET 'https://api.linkedin.com/rest/adLibrary?q=criteria&advertiser=Microsoft&countries=US' \
  -H 'X-RestLi-Protocol-Version: 2.0.0' \
  -H 'Linkedin-Version: 202601' \
  -H 'Authorization: Bearer {INSERT_TOKEN}'
```

## Response Structure

### AdsCreativeTransparencyEntity

| Field | Type | Description |
|-------|------|-------------|
| `adUrl` | String | Preview link to the ad |
| `details` | Object | AdTransparencyCreativeEntityDetails |
| `isRestricted` | Boolean | Whether ad violates policy |
| `restrictionDetails` | String | Explanation for restricted ads |

### AdTransparencyCreativeEntityDetails

| Field | Type | Description |
|-------|------|-------------|
| `advertiser` | Object | AdvertiserDetails (name, URL, payer) |
| `type` | Enum | Ad format (TEXT_AD, SPOTLIGHT_V2, etc.) |
| `adTargeting` | Array | Targeting parameters used |
| `adStatistics` | Object | Impression data |

### AdStatistics

| Field | Type | Description |
|-------|------|-------------|
| `firstImpressionAt` | Long | Epoch timestamp of first impression (up to 10 years history) |
| `latestImpressionAt` | Long | Epoch timestamp of most recent impression |
| `totalImpressions` | Object | Range with `from` and `to` values |
| `impressionsDistributionByCountry` | Array | Country codes with impression percentages |

## Ad Types (Enum)

- `SPONSORED_STATUS_UPDATE` - Static image/text posts (most common)
- `SPONSORED_VIDEO` - Video ads
- `SPONSORED_CAROUSEL` - Multi-image carousel
- `SPONSORED_INMAILS` - Direct message ads
- `TEXT_AD` - Sidebar text ads
- `SPOTLIGHT_V2` - Spotlight ads

## Pagination

- Maximum 25 ads per request
- Use `start` parameter to paginate
- Check response `paging.links` for `rel: "next"` to determine if more pages exist

## Rate Limits

- Approximately 100 requests per hour
- Returns 429 status code when exceeded
- Check `Retry-After` header for wait time

---

## Common Errors

### 400 Bad Request - QUERY_PARAM_NOT_ALLOWED

```json
{
  "errorDetailType": "com.linkedin.common.error.BadRequest",
  "message": "Invalid param.",
  "errorDetails": {
    "inputErrors": [{
      "input": {"inputPath": {"fieldPath": "advertiserUrn"}},
      "code": "QUERY_PARAM_NOT_ALLOWED"
    }]
  },
  "status": 400
}
```

**Solution:** Remove the unsupported parameter. LinkedIn does NOT support `advertiserUrn`.

### 429 Too Many Requests

Rate limit exceeded. Wait for `Retry-After` seconds and retry.

### 401 Unauthorized

Access token is invalid or expired. Refresh the token.

---

## Key Limitations

1. **No exact company matching** - Only fuzzy name search via `advertiser` parameter
2. **No ad creative content** - API returns metadata only, not actual images/video
3. **No click/engagement data** - Only impression counts are available
4. **No actual spend data** - Only impressions (spend must be estimated)
5. **No keyword targeting data** - LinkedIn uses audience-based targeting, not keywords

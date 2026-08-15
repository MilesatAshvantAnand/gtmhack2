> **⚠️ LEGACY / SUPERSEDED — historical reference only**
>
> This document describes the **PAUSED Streamlit chat agent** (`src/agent/`, `src/tools/`, `src/ui/`, `app.py`). It is kept for historical reference only and is **not** an accurate description of current API behavior.
>
> **For current, authoritative API behavior, use [`docs/api-knowledge-base/`](api-knowledge-base/)** — the fixture-backed audit. It supersedes any API claim made in this file.
>
> **Specific warning:** Any statement here that the `countries` or `ad_type`/`adType` parameters work is **WRONG**. The LinkedIn Ad Library API rejects **both** with HTTP 400. Do country and ad-type filtering **client-side** after fetching. See [`docs/api-knowledge-base/constraints.md`](api-knowledge-base/constraints.md) §1–2.
>
> **Repo direction:** the project is now a foundation knowledge base plus shareable skills — see [`CLAUDE.md`](../CLAUDE.md) and [`docs/architecture.md`](architecture.md). This chat agent is not part of that direction.

---

# Tool Reference

Complete documentation for all 15 tools in the LinkedIn Ad Library AI Assistant.

---

## 1. search_linkedin_ads

Search the LinkedIn Ad Library API for advertisements.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `advertiser` | string | No | Company name (fuzzy match - may return similar names) |
| `keyword` | string | No | Keyword to find in ad content |
| `countries` | array | No | ISO country codes (e.g., ["US", "UK"]) |
| `ad_type` | string | No | Filter by ad type (see below) |
| `start_date` | string | No | Start date (YYYY-MM-DD) - filtered client-side |
| `end_date` | string | No | End date (YYYY-MM-DD) - filtered client-side |
| `force_refresh` | boolean | No | Bypass cache, fetch fresh data |

### Company Matching

**Name search** (`advertiser`): Fuzzy match - "Pendo" may return "Pendo.io" AND "Pendoah"

**Note**: LinkedIn Ad Library API only supports name-based search. It does NOT support exact company ID matching via `advertiserUrn`. Use `lookup_company` tool to identify the correct company name if results include multiple similar companies.

### Ad Types
- `SPONSORED_STATUS_UPDATE` - Static image/text posts (most common)
- `SPONSORED_VIDEO` - Video ads
- `SPONSORED_CAROUSEL` - Multi-image carousel
- `SPONSORED_INMAILS` - Direct message ads
- `TEXT_AD` - Sidebar text ads

### Caching
- Results cached for 1 hour
- Same search parameters = cached result (no API call)
- Use `force_refresh=true` to bypass cache

### Returns
```json
{
  "success": true,
  "ads": [...],
  "count": 327,
  "from_cache": false,
  "rate_limit": {"remaining": 85, "resets_in_seconds": 2400}
}
```

---

## 2. get_company_ads

Get cached ads for a company from the local database.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `company_name` | string | Yes | Company name (partial match) |
| `limit` | integer | No | Max ads to return (default 100) |
| `ad_type` | string | No | Filter by ad type |
| `days_back` | integer | No | Only ads from last N days |

---

## 3. estimate_ad_spend

Calculate estimated LinkedIn ad spend using CPM benchmarks.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `company_name` | string | Yes | Company to analyze |
| `cpm_type` | string | No | CPM benchmark (default: "auto") |

### CPM Types
- `auto` - Detect based on geographic distribution
- `brand_awareness` - $5-$15 CPM
- `engagement` - $10-$25 CPM
- `website_visits` - $15-$35 CPM
- `lead_generation` - $30-$60 CPM
- `english_markets` - $20-$45 CPM

### Returns
```json
{
  "success": true,
  "company_name": "Userpilot",
  "total_ads": 327,
  "estimated_spend_min": 8200,
  "estimated_spend_max": 24600,
  "methodology": "Based on 327 ads with avg impressions at $20-$45 CPM"
}
```

**Note**: These are ESTIMATES based on public impression data, not actual spend.

---

## 4. detect_growth_signals

Find companies increasing their LinkedIn ad activity.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `lookback_days` | integer | No | Days to compare (default: 7) |
| `min_score` | integer | No | Minimum growth score (default: 60) |
| `limit` | integer | No | Max companies to return (default: 20) |

### Growth Signals
- **Explosive Growth** (Score 95): 100%+ increase
- **Strong Growth** (Score 80): 50-99% increase
- **Steady Growth** (Score 65): 25-49% increase
- **New Entrant** (Score 85): First-time advertiser
- **High Volume** (Score 60): 20+ ads in period

---

## 5. compare_companies

Compare two companies' LinkedIn advertising side-by-side.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `company1` | string | Yes | First company |
| `company2` | string | Yes | Second company |

### Returns
```json
{
  "success": true,
  "company1": {
    "advertiser_name": "Userpilot",
    "ad_count": 327,
    "ad_type_counts": {"SPONSORED_STATUS_UPDATE": 285, "SPONSORED_VIDEO": 32},
    "top_countries": [["US", 55], ["UK", 22]]
  },
  "company2": {...},
  "comparison": {
    "ad_count_difference": 164,
    "ad_count_percentage": 100.6
  }
}
```

---

## 6. track_company

Manage the company tracking list.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `action` | string | Yes | "add", "remove", or "list" |
| `company_name` | string | No* | Required for add/remove |
| `notes` | string | No | Notes about why tracking |

---

## 7. get_company_history

Get historical snapshots for a tracked company.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `company_name` | string | Yes | Company to get history for |
| `days_back` | integer | No | Days of history (default: 30) |

---

## 8. get_database_stats

Get statistics about the local database.

### Parameters
None required.

### Returns
```json
{
  "success": true,
  "total_ads": 15420,
  "unique_advertisers": 823,
  "tracked_companies": 12,
  "ad_types": {"SPONSORED_STATUS_UPDATE": 8500, ...}
}
```

---

## 9. export_data

Export ad data to CSV or JSON.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `format` | string | Yes | "csv" or "json" |
| `company_name` | string | No | Filter to company |
| `ad_type` | string | No | Filter to ad type |
| `filename` | string | No | Custom filename |

---

## 10. get_top_advertisers

Get top advertisers by ad count or impressions.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `limit` | integer | No | Number to return (default: 10) |
| `order_by` | string | No | "ad_count" or "impressions" |

---

## 11. analyze_ad_types

Analyze ad format distribution for a company.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `company_name` | string | No | Company to analyze (all if not provided) |

### Returns
```json
{
  "success": true,
  "company_name": "Userpilot",
  "ad_types": {
    "SPONSORED_STATUS_UPDATE": {"count": 285, "percentage": 87.2},
    "SPONSORED_VIDEO": {"count": 32, "percentage": 9.8}
  },
  "total_ads": 327,
  "primary_ad_type": "SPONSORED_STATUS_UPDATE"
}
```

---

## 12. analyze_geography

Analyze geographic distribution of a company's ads.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `company_name` | string | Yes | Company to analyze |

### Returns
```json
{
  "success": true,
  "company_name": "Userpilot",
  "countries": {"US": 55.2, "UK": 22.1, "DE": 8.5},
  "english_market_focus": true,
  "english_market_percentage": 85.3
}
```

---

## 13. get_recent_activity

Get the most recent advertising activity.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `limit` | integer | No | Number of ads (default: 20) |
| `company_name` | string | No | Filter to company |

---

## 14. lookup_company

Look up a company from previously fetched data to disambiguate similar names.

### Description
Use this when search results include multiple similarly-named companies (e.g., "Pendo" matches both "Pendo.io" and "Pendoah"). Returns the company's official name and LinkedIn URL for verification.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `company_name` | string | Yes | Company name to look up |

### Returns
```json
{
  "success": true,
  "company_name": "Pendo.io",
  "company_id": "5071271",
  "company_url": "https://www.linkedin.com/company/5071271",
  "message": "Use the exact name 'Pendo.io' for searching"
}
```

### Multiple Matches
```json
{
  "success": true,
  "warning": "Multiple companies match this name. Please specify which one:",
  "matches": [
    {"name": "Pendo.io", "url": "https://www.linkedin.com/company/5071271"},
    {"name": "Pendoah", "url": "https://www.linkedin.com/company/90798130"}
  ]
}
```

**Note**: Only works for companies already in the database from previous searches. LinkedIn API only supports fuzzy name search, so use this to clarify which company in results the user wants.

---

## 15. analyze_targeting

Analyze targeting strategy of a company's ads.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `company_name` | string | Yes | Company to analyze |

### Returns
```json
{
  "success": true,
  "company_name": "Userpilot",
  "languages": {"English": 327},
  "locations": {"United States": 180, "EMEA": 95, "Europe": 52},
  "audience_segments": "No specific audience segments found",
  "note": "LinkedIn uses audience-based targeting, not keywords"
}
```

**Note**: LinkedIn doesn't use keyword targeting like Google Ads. Companies target by job title, industry, company size, skills, etc.

---

## Data Availability Reference

| Data Point | Available? | Notes |
|------------|------------|-------|
| Ad counts | Yes | Accurate count of ads |
| Impressions | Yes | Min/max range |
| Ad types | Yes | Video, image, carousel, etc. |
| Geography | Yes | Country distribution % |
| Languages | Yes | From targeting info |
| Locations | Yes | Regions targeted |
| Dates | Yes | First/last impression |
| CTR | No | Not public |
| Conversions | No | Not public |
| Actual spend | No | Only estimates |
| Ad creative | No | Images/copy not available |
| Keywords | No | LinkedIn uses audience targeting |

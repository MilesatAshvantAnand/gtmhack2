# Call Patterns — The Whole Truth

This doc answers, for **every possible way to call the API**, exactly what response you get and why. Every claim below is backed by a fixture under `fixtures/call-patterns/` (23 patterns tested 2026-07-03).

If you're a skill author or sub-project builder, this is your **first stop**. Look up your intended call shape, see the exact response you should expect.

---

## 1. The complete input surface (recap)

The API accepts **exactly 4 query parameters**, all optional except `q`:

| Param | Values | Required? |
|---|---|---|
| `q` | must equal `"criteria"` (any other value → 404; omit → 404) | **Yes** |
| `advertiser` | any string, fuzzy-matched against LinkedIn company names | Only one of `advertiser` / `keyword` required |
| `keyword` | any string, matched against ad copy | Same |
| `start` | int ≥ 0 (negative → 400) | No — default 0 |
| `count` | int 1–25 (0 → 200 empty; >25 → 400) | No — default 25 |

Any other param name → 400 with `QUERY_PARAM_NOT_ALLOWED`. See `constraints.md § 1` for the full rejected list.

So the whole call-shape universe is:

```
GET /rest/adLibrary?q=criteria
  [ &advertiser=<string> ]
  [ &keyword=<string> ]
  [ &start=<int> ]
  [ &count=<int> ]
```

Combinations:

| Combination | Response character | Section below |
|---|---|---|
| `q` alone (no `advertiser`, no `keyword`) | 400 | § 2 |
| `q + advertiser` | 200 with matching ads | § 3 |
| `q + keyword` | 200 with matching ads | § 4 |
| `q + advertiser + keyword` | 200 with ANDed matches | § 5 |
| Invalid `q` or missing `q` | 404 | § 2 |
| Any invalid param name | 400 | § 6 |

---

## 2. `q` param behavior — required, must equal "criteria"

- **Omit `q` entirely** → **404 `RESOURCE_NOT_FOUND`**. Fixture: `22_no_q_param.json`.
- **`q=foo` (any value other than `criteria`)** → **404 `RESOURCE_NOT_FOUND`**. Fixture: `23_wrong_q_value.json`. The 404 is because LinkedIn interprets `q` as selecting a "finder"; only `criteria` is a valid finder for this endpoint.
- **`q=criteria` alone (no `advertiser`, no `keyword`)** → **400**. Fixture: `01_naked_q_criteria.json`. Response body is a generic 400 — one of `advertiser` or `keyword` must be present.

**Actionable:** always send `q=criteria` and at least one of `advertiser` / `keyword`.

---

## 3. `advertiser` alone

Fuzzy substring/token match against LinkedIn's company-name index. This is the primary call shape used by our 15-company round-1/2 captures.

### 3a. Normal case — well-known company

**Call:** `?q=criteria&advertiser=Personio&count=25`

**Response shape:**
- Status 200
- `elements: [ ... ]` — up to 25 ads (page 1)
- `paging.total` — the true count of matching ads (Personio=2755, Salesforce=9403, Alibaba=8k+, keyword-only "product management"=410k+)
- `paging.links[].rel = "next"` — present when there are more pages

Fixture: any `companies/*/page_1.json`. Full field reference in [`response-fields.md`](./response-fields.md).

### 3b. Advertiser has EU-visible ads (impression data present)

Ads have `details.adStatistics` and non-empty `details.adTargeting`. Example: Personio (95% coverage).

- `adStatistics` present because the ad had EU/EEA impressions → DSA disclosure required
- `adTargeting` non-empty because DSA also requires targeting-parameter disclosure for those ads
- See [`constraints.md § 10`](./constraints.md#10-impression-data-is-only-present-for-eueea-visible-ads)

### 3c. Advertiser is US-only or heavily non-EU (impression data absent)

Same call, but each ad's `details.adStatistics` is MISSING (not null — literally absent from the object) and `details.adTargeting: []` (empty list, present as container).

- **Why:** the DSA transparency requirement only applies to ads shown in the EU/EEA. Ads that never had EU impressions don't get their stats/targeting disclosed.
- **Example:** Salesforce — only 6/75 ads had `adStatistics`. See `companies/salesforce/page_1.json`.

### 3d. Advertiser name matches multiple companies (fuzzy collision)

**Call:** `?q=criteria&advertiser=Meta`

**Response:** may include ads from "Meta", "Metalforms", "Meta Platforms", etc. LinkedIn's fuzzy match is **substring / token-based**, not exact. Fixture: `companies/meta/page_*.json` shows a Metalforms ad in the results.

Similarly `advertiser=Peloton` returns "Peloton Consulting Group" alongside the fitness Peloton. Fixture: `companies/peloton/`.

**Actionable:** filter results by canonical LinkedIn company ID after fetching. Parse from `details.advertiser.advertiserUrl` (regex `/company/(\d+)`).

### 3e. Advertiser doesn't exist / very specific query

**Call:** `?q=criteria&advertiser=zzz_nonexistent_advertiser_xyz`

**Response:** status 200, `elements: []`, `paging.total: 0`. Fixture: `auxiliary/not_found__fake_company.json`.

**Not** a 404 — LinkedIn returns a normal empty result. Same for a long over-specific string that fails to match: `call-patterns/11_advertiser_very_long.json` — 200, 0 elements.

### 3f. Advertiser with punctuation

- `.com` suffix → 0 results (`Salesforce.com` matches nothing; `personio.com` matches nothing). Fixtures: `08_advertiser_with_dot.json`, `10_advertiser_domain_only.json`. LinkedIn's tokenizer appears to not handle domain-style strings.
- `&` character (AT&T) → 200, 139,369 results. Fixture: `09_advertiser_with_ampersand.json`. URL-encoded correctly by `requests`.

**Actionable:** normalize company names to remove `.com`, `.io`, TLDs before querying. Prefer plain brand name (`Salesforce`, `Personio`, `HubSpot`).

### 3g. Advertiser is empty string

**Call:** `?q=criteria&advertiser=`

**Response:** 400 `ILLEGAL_ARGUMENT`. Fixture: `05_advertiser_empty_string.json`.

### 3h. Advertiser is very short (1 or 2 chars)

- **1 char** ("A") → 200, 0 results. Minimum tokenizable length isn't 1. Fixture: `03_advertiser_short_1char.json`.
- **2 chars** ("AI") → 200, **1,346,051 results**. Fuzzy match is aggressive at ≥ 2 chars — this covers every ad by any company with "AI" in the name. Fixture: `04_advertiser_short_2char.json`.

**Actionable:** never send a 2-char advertiser query — you'll get millions of unrelated matches.

### 3i. Non-ASCII characters

- **Latin-1 extended** (e.g. "Deutschland" for German content, umlauts) → 200, 26,493 results. Fixture: `06_advertiser_nonascii_german.json`. Works.
- **Chinese characters** ("阿里巴巴" = Alibaba native script) → 200, 0 results. Fixture: `07_advertiser_nonlatin_chinese.json`. LinkedIn stores advertiser names in Latin script; native-language queries fail.

**Actionable:** always use the Latin/Roman-script name of a company (transliterate if needed).

---

## 4. `keyword` alone

Fuzzy full-text match against ad body/text.

### 4a. Normal case

**Call:** `?q=criteria&keyword=product management`

**Response:** 200, up to 25 ads returned per page, `paging.total = 410,199`. Ads span many advertisers. First advertiser in our fixture is "Wharton Online". Fixture: `auxiliary/keyword_only__product_management.json`.

### 4b. Multi-word keyword

**Call:** `?q=criteria&keyword=product management crm`

**Response:** 200, 4,802 results (much narrower than "product management" alone). Fixture: `12_keyword_multiword.json`.

**Semantics:** implicit AND — all words must appear in the ad copy. Per LinkedIn docs, and empirically confirmed by the narrowing.

### 4c. Quoted-phrase keyword

**Call:** `?q=criteria&keyword="product management"`

**Response:** 200, 410,223 results — same order-of-magnitude as unquoted "product management" (410,199). Fixture: `13_keyword_quoted_phrase.json`.

**Interpretation:** quotes are NOT respected as phrase-search markers — they're just treated as extra characters, likely ignored. Do not use `"..."` expecting phrase-search behavior.

### 4d. Single-character keyword

**Call:** `?q=criteria&keyword=a`

**Response:** 200, 0 results. Fixture: `14_keyword_short_1char.json`. Same minimum-length behavior as advertiser.

### 4e. Non-ASCII keyword

**Call:** `?q=criteria&keyword=Führung` (German)

**Response:** 200, 12,519 results. Fixture: `15_keyword_nonascii.json`. Works — LinkedIn indexes ad copy in multiple languages.

### 4f. Deep pagination on a huge result set

**Call:** `?q=criteria&keyword=product management&start=1000`

**Response:** 200, 5 elements returned, `paging.total = 410,223`. Fixture: `21_keyword_deep_pagination.json`. Deep pagination works — no observed upper limit on `start` other than exceeding the true total.

### 4g. No precision operators at all (live-confirmed 2026-07-06)

**Call:** `?q=criteria&keyword=<variant>` for `product analytics` in 7 forms.

**Response:** every form returns the **identical** `paging.total = 57,396`:

| Form | Query | total |
|---|---|---|
| baseline | `product analytics` | 57,396 |
| quoted | `"product analytics"` | 57,396 |
| plus tokens | `product +analytics` | 57,396 |
| explicit AND | `product AND analytics` | 57,396 |
| comma-separated | `product, analytics` | 57,396 |
| uppercase | `PRODUCT ANALYTICS` | 57,396 |
| surrounding whitespace | ` product analytics ` | 57,396 |

Fixture: `keyword-precision/product_analytics__query_forms.json`. Probe: `scripts/probe_keyword_precision.py`.

**Interpretation:** the keyword param supports **no** phrase/boolean/precision syntax — quotes, `+`, `AND`, and commas are stripped or ignored, matching is case-insensitive, and surrounding whitespace is trimmed. Combined with the fact that the API does **not** return ad copy (`response-fields.md`), this means keyword-match precision **cannot be improved server-side and cannot be filtered client-side**. Off-category matches (a company whose ad body merely contains the words) are unavoidable at the fetch layer; a skill must handle precision by **agent-layer relevance triage** (surface all advertisers, then judge category fit), not by a smarter query. Note §4b's narrowing came from adding a genuine third search *word* ("crm"), not from any operator.

---

## 5. `advertiser + keyword` combined

**Call:** `?q=criteria&advertiser=Personio&keyword=hiring`

**Response:** 200, `paging.total = 117` (vs Personio alone = 2,755). **AND semantics** — result set is ads that match both the fuzzy advertiser name AND contain the keyword in the ad copy. Fixture: `02_advertiser_and_keyword.json`.

Useful for skill patterns like "find all product-management-related ads from HubSpot" or "find ads mentioning `webinar` from a specific advertiser".

---

## 6. Rejected calls (400/404 catalog)

| Call | Result | Fixture | Reason |
|---|---|---|---|
| No `q` param | 404 RESOURCE_NOT_FOUND | `22_no_q_param.json` | LinkedIn interprets `q` as finder selector; required |
| `q` = anything other than `criteria` | 404 RESOURCE_NOT_FOUND | `23_wrong_q_value.json` | `criteria` is the only finder for adLibrary |
| No advertiser and no keyword | 400 | `01_naked_q_criteria.json` | At least one must be present |
| Empty advertiser string | 400 ILLEGAL_ARGUMENT | `05_advertiser_empty_string.json` | Must be non-empty when supplied |
| `count > 25` | 400 | `17_count_50_should_clip_to_25.json` | Server does NOT silently clip |
| `count = 0` | 200 with `elements: []` | `18_count_0.json` | Legal but useless |
| `start < 0` | 400 | `20_start_negative.json` | Non-negative required |
| `start > paging.total` | 200 with `elements: []` | `19_start_beyond_total_small_co.json` | Not an error — just empty |
| `advertiserUrn`, `advertiserPageUrl`, `payer`, `searchStartDate`, `dateRange.*`, `adType` | 400 QUERY_PARAM_NOT_ALLOWED | `negative/*.json`, `auxiliary/ad_type_filter__video.json` | Unsupported param names |
| `countries=<any value>` | 400 FIELD_INVALID | `auxiliary/country_filter_*.json` | Param name known but no accepted value encoding — see `constraints.md § 2` |
| Expired access token | 401 EXPIRED_ACCESS_TOKEN | `negative/expired_token.json` | Regenerate token |
| Old `LinkedIn-Version` (>12mo old) | 426 NONEXISTENT_VERSION | (not saved) | Use a recent version — 202601 works, 202501 doesn't |
| Any request during burst rate-limit | 429 (no Retry-After) | (Notion round-1 page 2 during original capture, later cleared) | ~35s cooldown; ~10 requests in 30s is the burst limit |

---

## 7. Response outcome decision tree

Given a call, this is how to interpret the response:

```
STATUS 200
├── elements.length > 0
│   ├── PROCESS AS: normal result
│   ├── For each ad:
│   │   ├── details.adStatistics present  →  EU-visible ad, all Tier S signals computable
│   │   └── details.adStatistics absent   →  US/non-EU-only, only Tier N signals computable
│   ├── paging.total tells you the TRUE match count (may be >> elements returned)
│   └── paging.links[].rel = "next" tells you if there's more
└── elements.length == 0
    ├── paging.total == 0
    │   ├── advertiser/keyword didn't match anything (fuzzy tokenizer returned no hits)
    │   ├── OR start > true total (advertiser has ads but you paged past them)
    │   └── OR count = 0 (deliberate empty request)
    └── paging.total > 0
        └── (shouldn't happen in practice; would indicate server pagination bug)

STATUS 400
├── errorDetails.inputErrors[].code == "QUERY_PARAM_NOT_ALLOWED"
│   └── Remove the offending param name from your request
├── errorDetails.inputErrors[].code == "FIELD_INVALID"
│   └── The param name is known but your value format is wrong (e.g. countries)
├── code == "ILLEGAL_ARGUMENT"
│   └── Empty string / bad value type
└── (generic 400 with no inputErrors)
    └── Structural issue (e.g. missing advertiser AND keyword)

STATUS 401
└── code == "EXPIRED_ACCESS_TOKEN" (serviceErrorCode 65602)
    └── Regenerate the token via LinkedIn Developer Portal

STATUS 404
└── code == "RESOURCE_NOT_FOUND"
    └── q param missing or has non-criteria value

STATUS 426
└── code == "NONEXISTENT_VERSION"
    └── LinkedIn-Version header is too old — use one within ~12 months

STATUS 429
└── (no body of substance, no Retry-After)
    └── Burst rate limit; wait ~35s before retrying
```

---

## 8. Behavior invariants (confirmed by Phase B probes 2026-07-03)

These properties hold across every advertiser and keyword we've tested. Skill authors can rely on them.

### 8a. Deterministic ordering
Same call twice returns the identical 25 ads in the identical order. Confirmed by fixture pair `phase-b/determinism__personio_call_1.json` and `phase-b/determinism__personio_call_2.json` — 25/25 overlap, identical order. **You can reproduce a result set by re-running the same query.**

The ordering itself is not chronological (see § 8b) but is stable per-query.

### 8b. Ordering is *roughly* chronological (newer first, some jitter)
Deep pagination on Personio:
- page 1 (start=0) → `firstImpressionAt` late 2026 (~last few months)
- start=500 → `firstImpressionAt` May-June 2026
- start=1500 → `firstImpressionAt` Feb 2026
- start=2500 → `firstImpressionAt` Aug 2025

Fixtures: `phase-b/deep_pagination__personio_start_500.json`, `_1500.json`, `_2500.json`.

**Implication:** don't fully trust the ordering (see `constraints.md § 5` on "smart-stop pagination" — LinkedIn's own docs and past experience say ordering is random; empirically it's mostly-chronological with jitter). For sub-projects that need "most recent N ads": early pages will over-represent recent ads but a "stop when we hit old ads" pagination would miss some outliers on later pages.

### 8c. Historical range extends to at least 11 months
Confirmed by start=2500 on Personio returning ads with `firstImpressionAt` in Aug 2025 (11 months old at time of capture). LinkedIn Engineering blog claims up to 10 years — we did not verify past 11 months, but there's no evidence of a lower cap.

### 8d. Case-insensitive on `advertiser`
`personio`, `Personio`, `PERSONIO` all return `paging.total = 2755`. Fixtures: `phase-b/case__personio_lowercase.json`, `_uppercase.json`.

### 8e. Whitespace trimmed on `advertiser`
Leading/trailing whitespace stripped — `"  Personio  "` returns `paging.total = 2755` (same as `"Personio"`). Fixture: `phase-b/whitespace__leading_trailing.json`. **All-whitespace** (`"   "`) returns 200 with `elements: []` and `paging.total: 0` — treated as empty query silently, does NOT error. Fixture: `phase-b/whitespace__only_whitespace.json`. Contrast with **empty string** which returns 400 (`call-patterns/05_advertiser_empty_string.json`).

### 8f. No stemming on `keyword`
The `hire` family returns different totals: `hire`=405,483; `hires`=396,885; `hired`=396,705; `hiring`=399,057. If LinkedIn stemmed, these would be identical. Fixtures: `phase-b/stem__keyword_{hire,hires,hired,hiring}.json`. **Skill implication:** to catch all forms, expand keyword variants client-side (`hire` OR `hires` OR `hiring` etc.) — do multiple queries and merge, or use a single word that captures the intent.

---

## 9. Advertiser-vs-individual: `advertiserUrl` disambiguation

Not every result is a company. Individual people running their own sponsored posts show up in keyword searches. To distinguish company advertisers from individuals, parse `details.advertiser.advertiserUrl`:
- `https://www.linkedin.com/company/<id>` → **company advertiser** (all 15 audit companies + most keyword-search results)
- `https://www.linkedin.com/in/<slug>` → **individual advertiser** (thought leaders)

Fixture examples of individual advertisers: `phase-b/skill1_kw__product_analytics.json` — "Sougata Mandal", "Emelia Hanson", "Catherine Palacios Pharm.D, MDRA" all appear alongside company advertisers on the "product analytics" keyword.

**Skill 1 recommendation:** filter to `/company/` URLs by default; expose an option to include individuals as "thought leaders" if the user wants the wider view. Individual accounts running paid promotion often signal micro-influence campaigns, worth flagging separately.

---

## 10. Fixture index (call-patterns/ + phase-b/)

Each pattern below has a JSON file under `fixtures/call-patterns/`:

| Slug | Purpose | Result |
|---|---|---|
| `01_naked_q_criteria` | q alone, no advertiser/keyword | 400 |
| `02_advertiser_and_keyword` | Personio + "hiring" combined | 200, 117 ads (AND) |
| `03_advertiser_short_1char` | "A" | 200, 0 |
| `04_advertiser_short_2char` | "AI" | 200, 1,346,051 |
| `05_advertiser_empty_string` | empty | 400 ILLEGAL_ARGUMENT |
| `06_advertiser_nonascii_german` | "Deutschland" | 200, 26,493 |
| `07_advertiser_nonlatin_chinese` | 阿里巴巴 | 200, 0 |
| `08_advertiser_with_dot` | "Salesforce.com" | 200, 0 |
| `09_advertiser_with_ampersand` | "AT&T" | 200, 139,369 |
| `10_advertiser_domain_only` | "personio.com" | 200, 0 |
| `11_advertiser_very_long` | 90-char sentence | 200, 0 |
| `12_keyword_multiword` | "product management crm" | 200, 4,802 (AND) |
| `13_keyword_quoted_phrase` | `"product management"` | 200, 410,223 (quotes ignored) |
| `14_keyword_short_1char` | "a" | 200, 0 |
| `15_keyword_nonascii` | "Führung" | 200, 12,519 |
| `16_count_1` | Personio, count=1 | 200, 1 |
| `17_count_50_should_clip_to_25` | count=50 | **400 (not clipped!)** |
| `18_count_0` | count=0 | 200, 0 elements |
| `19_start_beyond_total_small_co` | ZenABM start=500 | 200, 0 elements |
| `20_start_negative` | start=-1 | 400 |
| `21_keyword_deep_pagination` | keyword start=1000 | 200, works |
| `22_no_q_param` | omit q | 404 |
| `23_wrong_q_value` | q=foo | 404 |

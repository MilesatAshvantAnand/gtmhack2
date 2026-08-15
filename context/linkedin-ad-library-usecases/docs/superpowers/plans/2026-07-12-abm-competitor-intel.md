# abm-competitor-intel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the competitor skill as `abm-competitor-intel` — profile competitors' LinkedIn ads and compare them to the user's own ads — running entirely on the deployed **ZenABM API** (one Bearer token), delivered as a lean, branded, downloadable report; then contribute it to `ZENABM/linkedin-abm-skills`.

**Architecture:** A new ZenABM API client (`core/zenabm_api.py`) talks to `https://app.zenabm.com/api/v1` with a Bearer key. Pydantic models (`core/zenabm_models.py`) type the normalized competitor + own-data responses. The existing signal logic (`core/signals.py`) is adapted to the new models. `keyword_scan.py` becomes `competitor_scan.py` (compute → Zena authors insights → render). The report (`core/report_html.py`) is reskinned to ZenABM brand with progressive-disclosure sections and a Download-PDF button. No MCP, no LinkedIn token, no client-side caps.

**Tech Stack:** Python 3.9, pydantic 2, pytest 8, `requests`, `python-dotenv`. Dev repo: `/Users/bilal.ahmad/CC/linkedin-ad-library-usecases` (`.venv`). Target repo: `ZENABM/linkedin-abm-skills` (fork-based PR, Phase C).

## Global Constraints

- Python **3.9** compatible (`Optional[...]`, no `X | Y` annotations).
- Engine is stdlib + `requests`/`pydantic`; the shipped skill vendors `core/` via `scripts/vendor.py`.
- **API:** base `https://app.zenabm.com/api/v1`; header `Authorization: Bearer <ZENABM_TOKEN>`; token from `https://app.zenabm.com/api-keys`. Base overridable via `ZENABM_API_BASE_URL`.
- **No client-side caps** (server-enforced); on a `401/402/403/429` respond with a warm subtle upsell, never a hard-cap message. **Never fabricate data.**
- Persona: **Zena by ZenABM**; **no emojis in chat**, hyphens not em-dashes; never name the model/Anthropic/Claude; competitor data = "public advertising activity via ZenABM", own data = "your own LinkedIn ads in ZenABM".
- **Golden rule (signals):** `statistics: null` / no coverage ⇒ UNKNOWN (`None`), never `False`/`0`.
- Report: self-contained HTML, light mode, inline CSS/JS, inline SVG charts, `✓/✗/—` not emoji, Download-PDF button (`window.print()`).
- Full test command: `.venv/bin/python -m pytest tests/knowledge_base .claude/skills/abm-competitor-intel/tests -q` (plus engine tests). Keep the 114 knowledge-base regression green.
- Commit after every green step. Work on branch `abm-competitor-intel`.

---

## File Structure

**Create:**
- `core/zenabm_api.py` — ZenABM API client (Bearer, base URL, competitor + own-data methods, error handling).
- `core/zenabm_models.py` — pydantic models for the normalized API responses.
- `.claude/skills/abm-competitor-intel/scripts/competitor_scan.py` — skill entry (compute/render), replacing `keyword_scan.py`.
- `scripts/probe_zenabm_api.py` — live smoke-test script (Phase 0).
- `tests/test_zenabm_api.py`, `tests/test_zenabm_models.py` — engine tests.
- `docs/api-knowledge-base/fixtures/zenabm-api/` — captured example responses (from docs + live smoke).

**Modify:**
- `core/signals.py` — adapt accessors to the new models (keep the tier/golden-rule logic).
- `core/report_html.py` — reskin + progressive disclosure + Download-PDF + multi-platform delivery helper.
- `.claude/skills/abm-competitor-intel/SKILL.md` — rewrite (renamed from keyword-competitors).

**Rename:** `.claude/skills/keyword-competitors/` → `.claude/skills/abm-competitor-intel/` (git mv).

**Retire (delete):** `.claude/skills/abm-competitor-intel/scripts/session_ledger.py` + its tests; the `--no-ledger`/`--reset-session`/`ZENA_DEV` logic in the entry script; direct-LinkedIn token handling.

**Legacy, keep as reference (untouched):** `core/client.py` + `tests/test_core_client.py` (the raw LinkedIn client, referenced by the CTO brief), `docs/api-knowledge-base/` (still the source of truth for the underlying data).

---

## Phase 0 — Live smoke test (do first; needs a real token)

### Task 0.1: Probe the deployed ZenABM API

**Files:** Create `scripts/probe_zenabm_api.py`; Create `tests/test_probe_zenabm_api.py`.

**Interfaces:**
- Produces: `build_url(base, path, params) -> str`; `probe(client, base) -> Dict[str, Any]` (calls the endpoints, returns a summary of shapes + pagination fields).

- [ ] **Step 1: Write offline test for URL building + response summarizing (fake client)**

```python
# tests/test_probe_zenabm_api.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import probe_zenabm_api as p  # noqa: E402

class _Resp:
    def __init__(self, js): self._js = js; self.status_code = 200
    def json(self): return self._js

class _FakeClient:
    def __init__(self): self.calls = []
    def get(self, url, headers=None, params=None):
        self.calls.append((url, params))
        return _Resp({"data": {"ads": [], "advertisers": [], "total": 0, "scanned": 0, "truncated": False}})

def test_build_url_joins_base_and_path():
    assert p.build_url("https://app.zenabm.com/api/v1", "/ad-library/by-advertiser", {"company": "Personio"}) \
        == "https://app.zenabm.com/api/v1/ad-library/by-advertiser?company=Personio"

def test_probe_hits_all_endpoints():
    c = _FakeClient()
    summary = p.probe(c, "https://app.zenabm.com/api/v1")
    paths = [url for url, _ in c.calls]
    assert any("/ad-library/by-advertiser" in u for u in paths)
    assert any("/ad-library/by-keyword" in u for u in paths)
    assert any("/linkedin-metrics" in u for u in paths)
```

- [ ] **Step 2: Run → fails (module missing).** `.venv/bin/python -m pytest tests/test_probe_zenabm_api.py -q`

- [ ] **Step 3: Implement the probe**

```python
#!/usr/bin/env python3
"""Live smoke test of the deployed ZenABM API. Needs ZENABM_TOKEN.
Usage: ZENABM_TOKEN=... .venv/bin/python scripts/probe_zenabm_api.py [company]"""
from __future__ import annotations
import json, os, sys
from urllib.parse import urlencode

def build_url(base, path, params):
    q = urlencode({k: v for k, v in (params or {}).items() if v is not None})
    return f"{base.rstrip('/')}{path}" + (f"?{q}" if q else "")

def probe(client, base, company="Personio", keyword="product analytics"):
    hdr = {"Authorization": f"Bearer {os.environ.get('ZENABM_TOKEN','')}"}
    out = {}
    for name, path, params in [
        ("by_advertiser", "/ad-library/by-advertiser", {"company": company, "limit": 25}),
        ("by_keyword", "/ad-library/by-keyword", {"keyword": keyword, "limit": 25}),
        ("linkedin_metrics", "/linkedin-metrics", {"startDate": "2026-06-01", "endDate": "2026-06-30"}),
        ("creatives", "/creatives", {"pageSize": 5}),
        ("ad_spend", "/ad-spend", {"startDate": "2026-06-01", "endDate": "2026-06-30"}),
    ]:
        url = build_url(base, path, params)
        resp = client.get(url, headers=hdr, params=None)
        try:
            body = resp.json()
        except Exception:
            body = {"_nonjson": True}
        out[name] = {"status": getattr(resp, "status_code", "?"),
                     "top_keys": list(body.get("data", body).keys()) if isinstance(body, dict) else None,
                     "sample": body}
    return out

def main(argv):
    import requests
    base = os.environ.get("ZENABM_API_BASE_URL", "https://app.zenabm.com/api/v1")
    company = argv[0] if argv else "Personio"
    summary = probe(requests, base, company=company)
    print(json.dumps({k: {"status": v["status"], "top_keys": v["top_keys"]} for k, v in summary.items()}, indent=2))
    # dump full samples for fixture capture
    os.makedirs("docs/api-knowledge-base/fixtures/zenabm-api", exist_ok=True)
    for k, v in summary.items():
        with open(f"docs/api-knowledge-base/fixtures/zenabm-api/{k}.json", "w") as fh:
            json.dump(v["sample"], fh, indent=2)
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

> Note: `probe()` takes a `client` with `.get(url, headers, params)` — `requests` satisfies this, and the fake client in the test does too.

- [ ] **Step 4: Run offline test → passes.** `.venv/bin/python -m pytest tests/test_probe_zenabm_api.py -q`

- [ ] **Step 5: LIVE run (needs the user's token).** Ask the user for a current `app.zenabm.com/api-keys` token, then:
  `ZENABM_TOKEN="<token>" .venv/bin/python scripts/probe_zenabm_api.py "Personio"`
  Expected: 200s; `by_advertiser`/`by_keyword` top keys include `ads, advertisers, total, scanned, truncated`; `linkedin_metrics` returns `costInUsd/impressions/clicks/engagements`. **Record:** real response shapes → `fixtures/zenabm-api/`; the pagination behavior (does `limit` cap scan depth? is there a cursor/offset to go deeper?). These fixtures back all offline tests below.

- [ ] **Step 6: Commit** (`scripts/probe_zenabm_api.py`, `tests/test_probe_zenabm_api.py`, captured fixtures).

**Gate:** if live shapes differ from the docs, reconcile the models in Task A2 before proceeding.

---

## Phase A — Competitor skill on the ZenABM API

### Task A1: ZenABM API models

**Files:** Create `core/zenabm_models.py`; Create `tests/test_zenabm_models.py`.

**Interfaces:**
- Produces: `Advertiser(name,url,company_id,payer)`, `Statistics(...)`, `TargetingFacet(...)`, `Ad(ad_id,ad_url,is_restricted,type,advertiser,statistics,targeting)`, `AdvertiserRollup(name,url,company_id,ad_count)`, `AdLibraryResult(ads,advertisers,total,scanned,returned,truncated)`; `LinkedInMetrics(...)`, `Creative(...)`, all with `model_validate`.

- [ ] **Step 1: Failing test — validate the captured by-advertiser fixture**

```python
# tests/test_zenabm_models.py
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core.zenabm_models import AdLibraryResult  # noqa: E402

SAMPLE = {"data": {"ads": [{"adId":"1","adUrl":"u","isRestricted":False,"type":"SPONSORED_VIDEO",
  "advertiser":{"name":"Userpilot","url":"https://www.linkedin.com/company/27027108","companyId":"27027108","payer":"Userpilot Inc"},
  "statistics":{"firstImpressionAt":1,"latestImpressionAt":2,"totalImpressions":{"from":0,"to":1000},
    "impressionsByCountry":[{"country":"DE","percentage":4.45}]},
  "targeting":[{"facet":"Location","isIncluded":True,"isExcluded":False,"includedSegments":["Germany"],"excludedSegments":[]}]}],
  "advertisers":[{"name":"Userpilot","url":"x","companyId":"27027108","adCount":24}],
  "total":1617,"scanned":25,"returned":1,"truncated":True}}

def test_parses_ad_library_result():
    r = AdLibraryResult.from_response(SAMPLE)
    assert r.total == 1617 and r.truncated is True
    ad = r.ads[0]
    assert ad.advertiser.company_id == "27027108"
    assert ad.statistics.total_impressions.to == 1000
    assert ad.targeting[0].facet == "Location"
    assert r.advertisers[0].ad_count == 24

def test_null_statistics_is_none():
    s = dict(SAMPLE); s = json.loads(json.dumps(SAMPLE))
    s["data"]["ads"][0]["statistics"] = None
    r = AdLibraryResult.from_response(s)
    assert r.ads[0].statistics is None
```

- [ ] **Step 2: Run → fails.** `.venv/bin/python -m pytest tests/test_zenabm_models.py -q`

- [ ] **Step 3: Implement `core/zenabm_models.py`**

```python
"""Pydantic models for the normalized ZenABM API responses (v1)."""
from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field

class Advertiser(BaseModel):
    name: str
    url: str
    company_id: Optional[str] = Field(default=None, alias="companyId")
    payer: Optional[str] = None
    class Config: populate_by_name = True

class ImpressionsRange(BaseModel):
    from_: int = Field(alias="from")
    to: int
    class Config: populate_by_name = True

class CountryShare(BaseModel):
    country: str            # plain ISO, e.g. "DE"
    percentage: float

class Statistics(BaseModel):
    first_impression_at: int = Field(alias="firstImpressionAt")
    latest_impression_at: int = Field(alias="latestImpressionAt")
    total_impressions: ImpressionsRange = Field(alias="totalImpressions")
    impressions_by_country: List[CountryShare] = Field(default_factory=list, alias="impressionsByCountry")
    class Config: populate_by_name = True

class TargetingFacet(BaseModel):
    facet: str
    is_included: bool = Field(alias="isIncluded")
    is_excluded: bool = Field(alias="isExcluded")
    included_segments: List[str] = Field(default_factory=list, alias="includedSegments")
    excluded_segments: List[str] = Field(default_factory=list, alias="excludedSegments")
    class Config: populate_by_name = True

class Ad(BaseModel):
    ad_id: str = Field(alias="adId")
    ad_url: str = Field(alias="adUrl")
    is_restricted: bool = Field(default=False, alias="isRestricted")
    type: str
    advertiser: Advertiser
    statistics: Optional[Statistics] = None
    targeting: List[TargetingFacet] = Field(default_factory=list)
    class Config: populate_by_name = True

class AdvertiserRollup(BaseModel):
    name: str
    url: str
    company_id: Optional[str] = Field(default=None, alias="companyId")
    ad_count: int = Field(alias="adCount")
    class Config: populate_by_name = True

class AdLibraryResult(BaseModel):
    ads: List[Ad] = Field(default_factory=list)
    advertisers: List[AdvertiserRollup] = Field(default_factory=list)
    total: int = 0
    scanned: int = 0
    returned: int = 0
    truncated: bool = False
    @classmethod
    def from_response(cls, body: dict) -> "AdLibraryResult":
        return cls.model_validate((body or {}).get("data", {}))

class LinkedInMetrics(BaseModel):
    cost_in_usd: float = Field(default=0.0, alias="costInUsd")
    impressions: int = 0
    clicks: int = 0
    engagements: int = 0
    @classmethod
    def from_response(cls, body: dict) -> "LinkedInMetrics":
        return cls.model_validate((body or {}).get("data", {}))
    @property
    def ctr(self) -> Optional[float]:
        return (self.clicks / self.impressions * 100) if self.impressions else None
    @property
    def cpc(self) -> Optional[float]:
        return (self.cost_in_usd / self.clicks) if self.clicks else None

class Creative(BaseModel):
    linkedin_id: Optional[str] = Field(default=None, alias="linkedInId")
    name: Optional[str] = None
    format: Optional[str] = None
    status: Optional[str] = None
    is_serving: Optional[bool] = Field(default=None, alias="isServing")
    class Config: populate_by_name = True
```

- [ ] **Step 4: Run → passes.** `.venv/bin/python -m pytest tests/test_zenabm_models.py -q`
- [ ] **Step 5: Commit.**

### Task A2: ZenABM API client

**Files:** Create `core/zenabm_api.py`; Create `tests/test_zenabm_api.py`.

**Interfaces:**
- Consumes: `core.zenabm_models`.
- Produces: `class ZenABMClient(token=None, base_url=None, session=None)` with `search_by_advertiser(company=None, company_id=None, countries=None, start_date=None, end_date=None, limit=25) -> AdLibraryResult`, `search_by_keyword(keyword, advertiser=None, countries=None, ..., limit=25) -> AdLibraryResult`, `linkedin_metrics(start_date, end_date) -> LinkedInMetrics`, `list_creatives(page_size=100, cursor=None) -> tuple[List[Creative], Optional[str]]`; raises `ZenABMAuthError` (401), `ZenABMPlanError` (402/403), `ZenABMRateLimit` (429), `ZenABMError` (other).

- [ ] **Step 1: Failing tests (fake session returning fixtures)** — assert the client sends `Authorization: Bearer`, hits the right path, parses into models, and maps 401→`ZenABMAuthError`, 402/403→`ZenABMPlanError`, 429→`ZenABMRateLimit`.

```python
# tests/test_zenabm_api.py (sketch — implementer fills asserts against fixtures)
import os, sys, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core.zenabm_api import ZenABMClient, ZenABMAuthError, ZenABMPlanError

class _Resp:
    def __init__(self, code, js): self.status_code=code; self._js=js
    def json(self): return self._js
class _Sess:
    def __init__(self, code=200, js=None): self.code=code; self.js=js or {"data":{"ads":[],"advertisers":[],"total":0}}; self.last=None
    def get(self, url, headers=None, params=None, timeout=None): self.last=(url,headers,params); return _Resp(self.code, self.js)

def test_sends_bearer_and_hits_by_advertiser():
    s=_Sess(); c=ZenABMClient(token="k", session=s)
    c.search_by_advertiser(company_id="27027108", limit=25)
    url,headers,params=s.last
    assert url.endswith("/ad-library/by-advertiser")
    assert headers["Authorization"]=="Bearer k"
    assert params["companyId"]=="27027108" and params["limit"]==25

def test_401_maps_to_auth_error():
    s=_Sess(code=401, js={"error":"expired"}); c=ZenABMClient(token="k", session=s)
    with pytest.raises(ZenABMAuthError): c.linkedin_metrics("2026-06-01","2026-06-30")
```

- [ ] **Step 2: Run → fails.**
- [ ] **Step 3: Implement `core/zenabm_api.py`**

```python
"""Client for the deployed ZenABM API (https://app.zenabm.com/api/v1)."""
from __future__ import annotations
import os
from typing import Any, Dict, List, Optional, Tuple
import requests
from core.zenabm_models import AdLibraryResult, LinkedInMetrics, Creative

class ZenABMError(Exception):
    def __init__(self, status, body=None): self.status=status; self.body=body; super().__init__(f"ZenABM API HTTP {status}")
class ZenABMAuthError(ZenABMError): pass      # 401 - token expired/invalid
class ZenABMPlanError(ZenABMError): pass      # 402/403 - trial ended / plan gate
class ZenABMRateLimit(ZenABMError): pass      # 429

class ZenABMClient:
    DEFAULT_BASE_URL = "https://app.zenabm.com/api/v1"
    def __init__(self, token: Optional[str] = None, base_url: Optional[str] = None,
                 session: Optional[requests.Session] = None, timeout: float = 30.0):
        self._token = token or os.environ.get("ZENABM_TOKEN")
        self.base_url = (base_url or os.environ.get("ZENABM_API_BASE_URL") or self.DEFAULT_BASE_URL).rstrip("/")
        self.session = session if session is not None else requests.Session()
        self.timeout = timeout
    def _headers(self) -> Dict[str, str]:
        if not self._token:
            raise ZenABMAuthError(0, "No ZENABM_TOKEN. Get one at https://app.zenabm.com/api-keys.")
        return {"Authorization": f"Bearer {self._token}"}
    def _get(self, path: str, params: Dict[str, Any]) -> dict:
        params = {k: v for k, v in params.items() if v is not None}
        resp = self.session.get(self.base_url + path, headers=self._headers(), params=params, timeout=self.timeout)
        s = resp.status_code
        if s == 200:
            return resp.json()
        body = None
        try: body = resp.json()
        except Exception: pass
        if s == 401: raise ZenABMAuthError(s, body)
        if s in (402, 403): raise ZenABMPlanError(s, body)
        if s == 429: raise ZenABMRateLimit(s, body)
        raise ZenABMError(s, body)
    def search_by_advertiser(self, company=None, company_id=None, countries=None,
                             start_date=None, end_date=None, limit=25) -> AdLibraryResult:
        return AdLibraryResult.from_response(self._get("/ad-library/by-advertiser", {
            "company": company, "companyId": company_id, "countries": countries,
            "startDate": start_date, "endDate": end_date, "limit": limit}))
    def search_by_keyword(self, keyword, advertiser=None, countries=None,
                          start_date=None, end_date=None, limit=25) -> AdLibraryResult:
        return AdLibraryResult.from_response(self._get("/ad-library/by-keyword", {
            "keyword": keyword, "advertiser": advertiser, "countries": countries,
            "startDate": start_date, "endDate": end_date, "limit": limit}))
    def linkedin_metrics(self, start_date, end_date) -> LinkedInMetrics:
        return LinkedInMetrics.from_response(self._get("/linkedin-metrics",
            {"startDate": start_date, "endDate": end_date}))
    def list_creatives(self, page_size=100, cursor=None) -> Tuple[List[Creative], Optional[str]]:
        body = self._get("/creatives", {"pageSize": page_size, "cursor": cursor})
        data = (body or {}).get("data", []) or []
        nxt = ((body or {}).get("pagination") or {}).get("nextCursor")
        return [Creative.model_validate(c) for c in data], nxt
```

- [ ] **Step 4: Run → passes.**
- [ ] **Step 5: LIVE check** (token): a tiny `search_by_advertiser(company="Personio", limit=5)` and `linkedin_metrics(...)` in a REPL/one-liner; confirm real parsing. Resolve deeper-pagination need here (if `truncated` and more ads needed, use the cursor/offset the smoke test revealed; add a `max_ads` loop to the client if applicable).
- [ ] **Step 6: Commit.**

### Task A3: Adapt `core/signals.py` to the new models

**Files:** Modify `core/signals.py`; Modify `tests/test_core_signals.py` (or new `tests/test_signals_zenabm.py`).

**Interfaces:** `compute_company_signals(ads: List[Ad], now_ms: int) -> Dict[str, Any]` — same output keys as today, reading the new `Ad` model (`ad.statistics` may be `None`; `ad.advertiser.company_id`; `facet` name; plain-ISO `country`).

- [ ] **Step 1: Port the signal tests** to build `Ad` objects (from `core.zenabm_models`) instead of the old `AdElement`, keeping the same assertions (golden rule: `statistics is None` ⇒ Tier S/T signals return `None`; momentum, formats, SOV, reach unchanged).
- [ ] **Step 2: Run → fails** (signals still read old field names).
- [ ] **Step 3: Update `signals.py` accessors** — `a.details.adStatistics` → `a.statistics`; `a.details.type` → `a.type`; `a.details.advertiser.advertiserUrl` company-id parse → `a.advertiser.company_id` (already numeric, no regex); `facetName` → `facet`; country URN strip removed (already ISO); `impressionPercentage` → `percentage`; `totalImpressions.from_/to` unchanged. Keep the tier/gating logic identical.
- [ ] **Step 4: Run → passes.**
- [ ] **Step 5: Commit.**

### Task A4: Rename skill + rework the entry script (competitor compute/render)

**Files:** `git mv .claude/skills/keyword-competitors .claude/skills/abm-competitor-intel`; rename `scripts/keyword_scan.py` → `scripts/competitor_scan.py`; delete `scripts/session_ledger.py` + `tests/test_session_ledger.py`; Modify tests.

**Interfaces:** `run(competitors: List[str], keywords: List[str], *, client, out_dir, now_ms, generated_at, ...) -> Dict` builds the combined `report_data.json` (per-competitor profiles + field rollup) using `ZenABMClient` (via `make_client()` reading `ZENABM_TOKEN`); `render(json_path, out_path)` bakes insights → HTML.

- [ ] **Step 1: Port + trim tests** — reuse `test_keyword_scan.py` structure but: (a) drive a **fake `ZenABMClient`** serving `zenabm-api/by_advertiser.json` fixtures; (b) add competitor-by-URL/company-id path; (c) delete all ledger/`ZENA_DEV`/`--no-ledger`/cap tests. Keep: combined-object shape, per-competitor signal fields, digest, render round-trip, zero-ads path.
- [ ] **Step 2: Run → fails.**
- [ ] **Step 3: Rework `competitor_scan.py`** — replace the LinkedIn client + `scan_keyword_ads` pagination with `ZenABMClient.search_by_advertiser`/`search_by_keyword`; parse competitor input (company-page URL → `companyId` when numeric, else `company` slug/name; confirm via returned `advertisers[]`); build per-competitor profiles via `compute_company_signals`; rank by ad volume/SOV (keep the fixed `_rank_key`); remove ledger + `ZENA_DEV` + `--max-*` gating (no client caps); on `ZenABMAuthError/PlanError` print a warm upsell line and stop.
- [ ] **Step 4: Run → passes.** Re-vendor: `python3 scripts/vendor.py` (now copies `zenabm_api.py` + `zenabm_models.py` + `signals.py` + `report_html.py`; update `vendor.py`'s file list).
- [ ] **Step 5: Commit.**

### Task A5: SKILL.md rewrite (persona + 3-step onboarding + flow)

**Files:** Modify `.claude/skills/abm-competitor-intel/SKILL.md`; adapt `references/onboarding.md`.

- [ ] **Step 1: Write an acceptance test** `tests/test_skill_md.py` asserting the SKILL.md frontmatter `name: abm-competitor-intel`, description contains the trigger + "Do NOT use for" clauses, and the body contains: "Zena by ZenABM", the 3 onboarding links (`/signup`, connect LinkedIn, `/api-keys`), "no emojis", competitor-by-URL as primary, keyword "approximate", and NO occurrences of "token from LinkedIn", "MCP", "session_ledger", "ZENA_DEV". Run → fails.
- [ ] **Step 2: Rewrite SKILL.md** per spec §5/§6/§9: persona block, golden rule, Step 0 pitch, Step 1 three-step onboarding (exact links), get-competitors step, relevance triage, progressive-disclosure delivery, subtle-upsell rules. Adapt `references/onboarding.md` from the sibling canonical file (drop MCP; add the api-keys token step). Persona lint: no em-dashes/emoji.
- [ ] **Step 3: Run acceptance test + lint → pass.** Commit.

### Task A6: Report reskin — brand, progressive disclosure, Download-PDF, multi-platform delivery

**Files:** Modify `core/report_html.py`; add `assets/` (ZenABM `logo_white.png`/`logo_dark.png` copied from a sibling skill at Phase C, or a placeholder inline SVG now); Test `tests/test_report_html.py`.

- [ ] **Step 1: Tests** — `build_combined_report_html(data)` returns a self-contained doc that: starts `<!doctype html>`, has `<style>` (no external `src=`/`href=http`), contains a **Download-PDF** control (`window.print()`), renders the default sections (takeaways, per-competitor cards, field-at-a-glance, you-vs-them when present), wraps deep detail in a collapsible `<details>`/toggle, uses inline `<svg>` for the SOV chart, and contains no emoji. `select_delivery(env) -> str` returns `"cowork_artifact"` / `"claude_artifact"` / `"file"` for the detected environment. Run → fails.
- [ ] **Step 2: Implement** the reskinned renderer (progressive disclosure via `<details>` blocks for the ABM-depth sections; inline SVG SOV bars; Download-PDF button) + a small `select_delivery()` helper. Keep it stdlib-only.
- [ ] **Step 3: Run → pass.** Commit.

**Phase A gate — live end-to-end (token):** `ZENABM_TOKEN=... .venv/bin/python .claude/skills/abm-competitor-intel/scripts/competitor_scan.py --competitors "linkedin.com/company/personio, linkedin.com/company/notion" --out-dir /tmp/aci` → produces `report_data.json` + a branded `report.html`. Open it; verify the lean default + expandable detail. Fix issues before Phase B.

---

## Phase B — Own-data comparison

### Task B1: Own-data fetch + normalize
**Files:** extend `core/zenabm_api.py` (add `ad_spend(start,end)` if needed), `core/zenabm_models.py` (spend model); Test with `fixtures/zenabm-api/{linkedin_metrics,creatives,ad_spend}.json`.
- [ ] TDD: fake client returns the own-data fixtures; assert parsing + derived CTR/CPC. Commit.

### Task B2: Comparison assembly
**Files:** Create `core/comparison.py`; Test `tests/test_comparison.py`.
**Interfaces:** `build_comparison(own_metrics, own_creatives, competitor_profiles, now_ms) -> Dict` → `{head_to_head: {activity, formats, share_of_voice}, scale_vs_efficiency: {...}, moves: [...]}`.
- [ ] **Step 1: Test** — given own creatives (formats/count) + own metrics (CTR/CPC/spend) + competitor profiles (adCount/formats/reach/SOV), assert: activity gap (are you running fewer/more), **format gaps** (competitor uses X, you don't), your SOV vs the field, and a scale-vs-efficiency pairing (competitor reach vs your CTR/CPC). Golden rule respected (unknown competitor stats never counted as zero). Run → fails.
- [ ] **Step 2: Implement `core/comparison.py`** (pure functions; no I/O). Run → pass. Commit.

### Task B3: Wire comparison into the flow + report + probe-gate
**Files:** Modify `competitor_scan.py` (own-data fetch when connected; probe `/linkedin-metrics` first), `core/report_html.py` (you-vs-them section), SKILL.md (offer-comparison step + subtle upsell on `ZenABMPlanError`).
- [ ] TDD: fake client with/without own data → report includes/omits the you-vs-them section; on `ZenABMPlanError`, the flow emits the warm upsell and still delivers the competitor report. Commit.
- [ ] **Phase B gate — live:** with a token on an account that has own data, run end-to-end; verify the you-vs-them section (head-to-head + scale-vs-efficiency) and the subtle upsell path (e.g. expired token).

### Task B4: Full offline suite + re-vendor
- [ ] Run `.venv/bin/python -m pytest tests/knowledge_base tests/test_zenabm_api.py tests/test_zenabm_models.py tests/test_comparison.py .claude/skills/abm-competitor-intel/tests -q` → all green. `python3 scripts/vendor.py`. Commit.

---

## Phase C — Contribute to `ZENABM/linkedin-abm-skills`

### Task C1: Fork + place the skill
- [ ] Fork `ZENABM/linkedin-abm-skills` (`gh repo fork ZENABM/linkedin-abm-skills --clone` into `/Users/bilal.ahmad/CC/`), branch `add-abm-competitor-intel`.
- [ ] Copy the finished self-contained `.claude/skills/abm-competitor-intel/` → the fork's `skills/abm-competitor-intel/` (SKILL.md + scripts/ incl. vendored core + references/ + assets/ + evals/). Ensure ZenABM `logo_white/dark.png` are copied from a sibling skill's `assets/` for brand consistency. Commit.

### Task C2: Register the skill (the "four → five" edits)
- [ ] `README.md`: add the row to the skills table, the journey diagram, a per-skill section, and change "four"/"The four skills"/"install all four" wording to five. `CLAUDE.md`: add to intro count, routing table, do-not-confuse bullets, layout tree. Bump `version` in `.claude-plugin/plugin.json` + `marketplace.json` (equal). Commit.
- [ ] Update the sibling routing references: in `skills/linkedin-abm-audit/SKILL.md` and `skills/linkedin-abm-report/SKILL.md`, change `keyword-competitors` → `abm-competitor-intel` (routing string only). Commit.

### Task C3: Release zip + notes (for a maintainer)
- [ ] Build `abm-competitor-intel.zip` via Python zipfile (single top-level `abm-competitor-intel/` dir, exclude `__pycache__`/`.pyc`/`.DS_Store`/`__MACOSX`; verify no token inside). Draft a release-notes entry + the release-body table row. Save both under the fork; note in the PR that a maintainer must attach the zip to the GitHub Release + tag (contributor is read-only).

### Task C4: Open the PR
- [ ] `gh pr create --repo ZENABM/linkedin-abm-skills` from the fork branch to `main`, with a body summarizing the skill, the "four→five" edits, the routing-ref change, and the maintainer release step.

---

## Self-Review

**1. Spec coverage:** unified ZenABM API (Tasks 0.1, A1–A2) ✓; competitor-by-URL + companyId (A2/A4) ✓; keyword discovery flagged (A4/A5) ✓; signals/golden-rule (A3) ✓; 3-step onboarding + persona (A5) ✓; lean progressive-disclosure report + Download-PDF + multi-platform (A6) ✓; own-data comparison head-to-head + scale-vs-efficiency (B1–B3) ✓; no client caps + subtle upsell (A4/B3) ✓; retire ledger/ZENA_DEV/LinkedIn-token (A4) ✓; repo integration + four→five + routing refs + release (C1–C4) ✓; live smoke tests each phase ✓.

**2. Placeholder scan:** SKILL.md and report HTML are content files authored against explicit acceptance tests (A5/A6) rather than inlined verbatim — the tests define the required, checkable content. All code modules have complete implementations. No TBD/TODO.

**3. Type consistency:** `AdLibraryResult.from_response`, `Ad.statistics: Optional[Statistics]`, `Advertiser.company_id`, `ZenABMClient.search_by_advertiser/search_by_keyword/linkedin_metrics/list_creatives`, `compute_company_signals(ads, now_ms)`, `build_comparison(...)`, `select_delivery(env)` — names consistent across tasks.

---

## Execution Handoff

See the top-of-plan REQUIRED SUB-SKILL note. Phase 0 and the phase gates need a live `app.zenabm.com/api-keys` token from the user.

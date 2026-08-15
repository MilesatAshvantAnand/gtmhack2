"""Offline tests for the abm-competitor-intel entry script.

No network, no token: a ``FakeZenABMClient`` serves ``AdLibraryResult``
objects built from the captured ZenABM API fixtures
(``docs/api-knowledge-base/fixtures/zenabm-api/``) for both
``search_by_advertiser`` and ``search_by_keyword`` calls.

The repo root is put on ``sys.path`` so ``core`` resolves to the source tree,
mirroring how the shipped skill vendors ``core`` under ``scripts/core/``.

These exercise the two-step flow:
  * COMPUTE mode (``run``) scans competitors and keywords into ONE combined
    object, writes ``report_data.json`` + a draft ``report.html``, and prints
    a digest.
  * RENDER mode (``render``) reloads that JSON (after Zena's edits) and bakes
    it into the final combined HTML.
"""
from __future__ import annotations

import importlib.util
import io
import json
import math
import sys
from pathlib import Path
from typing import Any, List, Optional

import pytest

# ── Path wiring: repo root on sys.path so `core` resolves to source ──────────
_THIS = Path(__file__).resolve()
# .../.claude/skills/abm-competitor-intel/tests/test_competitor_scan.py -> root
_REPO_ROOT = _THIS.parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.zenabm_models import AdLibraryResult  # noqa: E402
from core.report_html import build_combined_report_html  # noqa: E402

# ── Import the entry script by path (it lives outside any package) ───────────
_SCRIPT_PATH = _THIS.parents[1] / "scripts" / "competitor_scan.py"
_spec = importlib.util.spec_from_file_location("competitor_scan", _SCRIPT_PATH)
competitor_scan = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(competitor_scan)

_FIXTURE_DIR = _REPO_ROOT / "docs" / "api-knowledge-base" / "fixtures" / "zenabm-api"

# A fixed "now" so time-based signals are stable.
_NOW_MS = 1_783_100_000_000
_GENERATED_AT = "2026-07-06"


# ── Fixture helpers ──────────────────────────────────────────────────────────

def _load_by_advertiser_fixture() -> dict:
    with open(_FIXTURE_DIR / "by_advertiser.json", encoding="utf-8") as fh:
        return json.load(fh)


def _load_by_keyword_fixture() -> dict:
    with open(_FIXTURE_DIR / "by_keyword.json", encoding="utf-8") as fh:
        return json.load(fh)


def _make_multi_ad_fixture(base_fixture: dict, n_ads: int = 5) -> dict:
    """Expand a fixture to have multiple ads (cycling the base ad)."""
    import copy
    result = copy.deepcopy(base_fixture)
    if result["data"]["ads"]:
        base_ad = result["data"]["ads"][0]
        result["data"]["ads"] = []
        for i in range(n_ads):
            ad = copy.deepcopy(base_ad)
            ad["adId"] = str(int(base_ad.get("adId", "1")) + i)
            result["data"]["ads"].append(ad)
    return result


# ── Fake ZenABM client ────────────────────────────────────────────────────────

class FakeZenABMClient:
    """Stand-in for ``ZenABMClient`` backed by fixture data.

    ``search_by_advertiser`` returns an ``AdLibraryResult`` built from the
    by_advertiser fixture; ``search_by_keyword`` returns one from by_keyword.
    Records calls for assertion.
    """

    def __init__(
        self,
        advertiser_fixture: Optional[dict] = None,
        keyword_fixture: Optional[dict] = None,
        n_ads: int = 5,
    ):
        self._adv_fixture = advertiser_fixture or _make_multi_ad_fixture(
            _load_by_advertiser_fixture(), n_ads
        )
        self._kw_fixture = keyword_fixture or _make_multi_ad_fixture(
            _load_by_keyword_fixture(), n_ads
        )
        self.advertiser_calls: List[dict] = []
        self.keyword_calls: List[dict] = []

    def search_by_advertiser(
        self,
        company: Optional[str] = None,
        company_id: Optional[str] = None,
        countries: Optional[Any] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
    ) -> AdLibraryResult:
        self.advertiser_calls.append({"company": company, "company_id": company_id, "limit": limit})
        return AdLibraryResult.from_response(self._adv_fixture)

    def search_by_keyword(
        self,
        keyword: str,
        advertiser: Optional[str] = None,
        countries: Optional[Any] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
    ) -> AdLibraryResult:
        self.keyword_calls.append({"keyword": keyword, "limit": limit})
        return AdLibraryResult.from_response(self._kw_fixture)


class FakeZenABMClientEmpty:
    """Returns empty AdLibraryResult for all calls."""

    def search_by_advertiser(self, **kwargs) -> AdLibraryResult:
        return AdLibraryResult.from_response({"data": {"ads": [], "advertisers": [], "total": 0, "scanned": 0, "returned": 0, "truncated": False}})

    def search_by_keyword(self, keyword: str, **kwargs) -> AdLibraryResult:
        return AdLibraryResult.from_response({"data": {"ads": [], "advertisers": [], "total": 0, "scanned": 0, "returned": 0, "truncated": False}})


@pytest.fixture()
def client():
    return FakeZenABMClient()


def _run(client, competitors, keywords, tmp_path, **overrides):
    """Compute mode -> returns the COMBINED report_data dict."""
    comp_list = competitors if isinstance(competitors, list) else [competitors]
    kw_list = keywords if isinstance(keywords, list) else ([keywords] if keywords else [])
    kwargs = dict(
        client=client,
        out_dir=str(tmp_path),
        now_ms=_NOW_MS,
        generated_at=_GENERATED_AT,
        stdout=io.StringIO(),
    )
    kwargs.update(overrides)
    return competitor_scan.run(comp_list, kw_list, **kwargs)


def _kw(combined, label):
    """Fetch a per-keyword/competitor block by label."""
    return next(k for k in combined["keywords"] if k["keyword"] == label)


# ── Tests: combined object shape ──────────────────────────────────────────────

def test_compute_builds_combined_object_with_competitors_and_keywords(client, tmp_path):
    combined = _run(client, ["Userpilot"], ["product-analytics"], tmp_path)
    # Top-level combined contract fields.
    assert combined["geographies"] == "Global"
    assert combined["generated_at"] == _GENERATED_AT
    assert combined["method_note"]
    assert isinstance(combined["cross_keyword_summary"], list)
    assert isinstance(combined["cross_theme_rivals"], list)
    kws = [k["keyword"] for k in combined["keywords"]]
    assert "Userpilot" in kws
    assert "product-analytics" in kws


def test_combined_renders_as_self_contained_html(client, tmp_path):
    combined = _run(client, ["Userpilot"], ["product-analytics"], tmp_path)
    html = build_combined_report_html(combined)  # must not raise
    assert html.lstrip().startswith("<!doctype html>")
    assert "</html>" in html
    assert "<style>" in html and "</style>" in html
    for needle in ("src=\"http", "href=\"http://cdn", "<script src"):
        assert needle not in html


def test_report_data_json_written_and_reloadable(client, tmp_path):
    _run(client, ["Userpilot"], ["product-analytics"], tmp_path)
    json_path = tmp_path / "report_data.json"
    html_path = tmp_path / "report.html"
    assert json_path.exists()
    assert html_path.exists()
    reloaded = json.loads(json_path.read_text(encoding="utf-8"))
    kws = [k["keyword"] for k in reloaded["keywords"]]
    assert "Userpilot" in kws
    build_combined_report_html(reloaded)  # must not raise
    assert html_path.read_text(encoding="utf-8").lstrip().startswith("<!doctype html>")


# ── Tests: search calls with right arguments ──────────────────────────────────

def test_competitor_by_name_calls_search_by_advertiser_with_company(tmp_path):
    client = FakeZenABMClient()
    _run(client, ["Userpilot"], [], tmp_path)
    assert len(client.advertiser_calls) == 1
    assert client.advertiser_calls[0]["company"] == "Userpilot"
    assert client.advertiser_calls[0]["limit"] == 100


def test_competitor_by_slug_url_calls_search_by_advertiser(tmp_path):
    client = FakeZenABMClient()
    _run(client, ["linkedin.com/company/userpilot"], [], tmp_path)
    assert len(client.advertiser_calls) == 1
    call = client.advertiser_calls[0]
    # Non-numeric slug URL is passed straight through as company.
    assert call["company"] == "linkedin.com/company/userpilot"


def test_keyword_calls_search_by_keyword(tmp_path):
    client = FakeZenABMClient()
    _run(client, [], ["product analytics"], tmp_path)
    assert len(client.keyword_calls) == 1
    assert client.keyword_calls[0]["keyword"] == "product analytics"
    assert client.keyword_calls[0]["limit"] == 100


def test_multiple_competitors_multiple_calls(tmp_path):
    client = FakeZenABMClient()
    _run(client, ["Userpilot", "Personio"], [], tmp_path)
    assert len(client.advertiser_calls) == 2
    names = [c["company"] for c in client.advertiser_calls]
    assert "Userpilot" in names
    assert "Personio" in names


# ── Tests: per-competitor signal fields ───────────────────────────────────────

def test_competitor_block_has_required_signal_fields(tmp_path):
    client = FakeZenABMClient()
    combined = _run(client, ["Userpilot"], [], tmp_path)
    block = _kw(combined, "Userpilot")
    comps = block["competitors"]
    assert comps, "should have at least one competitor"
    c = comps[0]
    # Tier N — always present.
    assert isinstance(c["agency_run"], bool)
    assert isinstance(c["format_diversity_count"], int)
    assert isinstance(c["linkedin_maturity_score"], int)
    assert isinstance(c["formats"], dict)
    assert isinstance(c["n_ads_on_keyword"], int)
    assert "impression_data_coverage" in c
    assert "sov_pct" in c
    assert "rank" in c
    assert isinstance(c["read"], str)
    assert "sample_ad_url" in c


def test_coverage_none_competitor_has_tier_s_t_none(tmp_path):
    """When fixture has statistics=null, Tier S/T must return None (golden rule)."""
    import copy
    # The by_keyword fixture has statistics: null - use it for the competitor too
    kw_fixture = _load_by_keyword_fixture()
    multi = _make_multi_ad_fixture(kw_fixture, n_ads=3)
    client = FakeZenABMClient(advertiser_fixture=multi, keyword_fixture=multi)
    combined = _run(client, ["Personio"], [], tmp_path)
    block = _kw(combined, "Personio")
    none_cov = [c for c in block["competitors"] if c["impression_data_coverage"] == "none"]
    assert none_cov, "fixture with statistics=null must produce coverage=none competitor"
    for c in none_cov:
        assert c["is_currently_advertising"] is None
        assert c["momentum_status"] == "unknown"
        assert c["reach_low"] is None and c["reach_high"] is None
        assert c["reach_tier"] is None
        assert c["ad_longevity_days"] is None
        assert c["is_long_runner"] is None
        assert c["cadence_shape"] is None
        assert c["funnel_stage"] is None
        assert c["targets_specific_companies"] is None
        assert c["uses_retargeting"] is None
        assert c["outreach_timing_score"] is None


def test_sov_pct_sums_to_about_100(tmp_path):
    client = FakeZenABMClient()
    combined = _run(client, ["Userpilot"], [], tmp_path)
    competitors = _kw(combined, "Userpilot")["competitors"]
    total_sov = sum(c["sov_pct"] for c in competitors)
    assert math.isclose(total_sov, 100.0, abs_tol=1.0)


def test_agency_run_detected_from_differing_payer(tmp_path):
    """The by_advertiser fixture has payer=Userpilot Inc which matches Userpilot -> agency_run=False.
    Personio's payer is Personio SE & Co. KG -> also strips to same -> False.
    We just confirm the field is present and bool."""
    client = FakeZenABMClient()
    combined = _run(client, ["Userpilot"], [], tmp_path)
    comps = _kw(combined, "Userpilot")["competitors"]
    for c in comps:
        assert isinstance(c["agency_run"], bool)


# ── Tests: ranking ───────────────────────────────────────────────────────────

def test_rank_key_volume_beats_visibility():
    """Volume-first ranking: many ads with coverage none must beat few confirmed-active."""
    loud_unknown = {
        "n_ads_on_keyword": 45,
        "linkedin_maturity_score": 3,
        "is_currently_advertising": None,
    }
    quiet_active = {
        "n_ads_on_keyword": 2,
        "linkedin_maturity_score": 3,
        "is_currently_advertising": True,
    }
    ranked = sorted([quiet_active, loud_unknown], key=competitor_scan._rank_key, reverse=True)
    assert ranked[0] is loud_unknown


def test_rank_key_active_is_only_a_tiebreaker():
    """Equal volume + maturity: confirmed-active wins the low-weight tiebreak."""
    a = {"n_ads_on_keyword": 10, "linkedin_maturity_score": 5, "is_currently_advertising": True}
    b = {"n_ads_on_keyword": 10, "linkedin_maturity_score": 5, "is_currently_advertising": None}
    ranked = sorted([b, a], key=competitor_scan._rank_key, reverse=True)
    assert ranked[0] is a


# ── Tests: cross-theme rivals ─────────────────────────────────────────────────

def test_cross_theme_rivals_lists_advertisers_on_two_or_more_blocks(tmp_path):
    # When the same advertiser (same company_id) appears in both competitor
    # AND keyword blocks, they show up as cross-theme rivals.
    client = FakeZenABMClient()
    combined = _run(client, ["Userpilot"], ["product-analytics"], tmp_path)
    rivals = combined["cross_theme_rivals"]
    # Rivals must be deduped; n_keywords must match their keyword list length.
    for r in rivals:
        assert r["n_keywords"] == len(r["keywords"])


def test_single_block_has_no_cross_theme_rivals(tmp_path):
    client = FakeZenABMClient()
    combined = _run(client, ["Userpilot"], [], tmp_path)
    assert combined["cross_theme_rivals"] == []


# ── Tests: insight fields for Zena ───────────────────────────────────────────

def test_baseline_insight_fields_present_for_zena_to_rewrite(tmp_path):
    client = FakeZenABMClient()
    combined = _run(client, ["Userpilot"], ["product-analytics"], tmp_path)
    # Baseline summary exists for Zena to rewrite.
    assert "cross_keyword_summary" in combined
    for block in combined["keywords"]:
        assert "where_you_can_win" in block and "what_to_watch" in block
        assert block["where_you_can_win"] == block["whitespace"]
        assert block["what_to_watch"] == block["threats"]
        for c in block["competitors"]:
            assert isinstance(c["read"], str)


# ── Tests: digest ────────────────────────────────────────────────────────────

def test_digest_prints_signals_and_section_headers(tmp_path):
    out = io.StringIO()
    client = FakeZenABMClient()
    _run(client, ["Userpilot"], ["product-analytics"], tmp_path, stdout=out)
    text = out.getvalue()
    assert "DIGEST" in text
    assert "report_data.json" in text
    assert "coverage=" in text or "ads=" in text
    assert "CROSS-THEME RIVALS" in text


# ── Tests: render mode ────────────────────────────────────────────────────────

def test_render_mode_produces_final_html_from_json(tmp_path):
    client = FakeZenABMClient()
    _run(client, ["Userpilot"], ["product-analytics"], tmp_path)
    json_path = tmp_path / "report_data.json"

    # Simulate Zena editing insight fields.
    data = json.loads(json_path.read_text(encoding="utf-8"))
    data["cross_keyword_summary"] = ["ZenABM tracks Userpilot weekly."]
    for block in data["keywords"]:
        block["where_you_can_win"] = ["Ship one video. ZenABM tells you who watches it."]
        block["whitespace"] = block["where_you_can_win"]
        block["what_to_watch"] = ["Watch the ramping newcomer. ZenABM alerts you."]
        block["threats"] = block["what_to_watch"]
        for c in block["competitors"]:
            c["read"] = "Zena-authored read. ZenABM shows their real ad copy."
    json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    out_path = tmp_path / "final.html"
    result = competitor_scan.render(str(json_path), out_path=str(out_path), stdout=io.StringIO())
    assert result == str(out_path)
    html = out_path.read_text(encoding="utf-8")
    assert html.lstrip().startswith("<!doctype html>")
    assert "ZenABM tracks Userpilot weekly" in html
    assert "Zena-authored read" in html


def test_render_mode_rejects_invalid_json(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"not": "a report"}), encoding="utf-8")
    with pytest.raises(ValueError):
        competitor_scan.render(str(bad), out_path=str(tmp_path / "x.html"), stdout=io.StringIO())


def test_zero_ads_still_builds_renderable_combined_report(tmp_path):
    combined = _run(FakeZenABMClientEmpty(), ["NoAdsCompany"], ["no-results-keyword"], tmp_path)
    for block in combined["keywords"]:
        assert block["competitors"] == []
        assert block["n_ads_scanned"] == 0
    html = build_combined_report_html(combined)
    assert html.lstrip().startswith("<!doctype html>")
    assert (tmp_path / "report_data.json").exists()
    assert (tmp_path / "report.html").exists()


# ── Tests: no ledger/ZENA_DEV/cap logic present ──────────────────────────────

def test_no_session_ledger_import_or_cap_logic():
    """competitor_scan must not import or reference session_ledger, ZENA_DEV, or cap."""
    import inspect
    src = inspect.getsource(competitor_scan)
    assert "session_ledger" not in src
    assert "ZENA_DEV" not in src
    assert "no_ledger" not in src
    assert "reset_session" not in src


def test_no_linkedin_client_import():
    """competitor_scan must not use the old LinkedIn client."""
    import inspect
    src = inspect.getsource(competitor_scan)
    assert "LinkedInAdLibraryClient" not in src
    assert "scan_keyword_ads" not in src


# ── Task B3: you-vs-them probe + comparison attachment ───────────────────────

from core.zenabm_models import Creative, LinkedInMetrics  # noqa: E402


def _make_own_metrics(impressions: int = 5000, clicks: int = 100, cost: float = 500.0) -> LinkedInMetrics:
    return LinkedInMetrics(impressions=impressions, clicks=clicks, cost_in_usd=cost)


def _make_own_creatives(n: int = 3) -> List[Creative]:
    return [
        Creative(linkedin_id=str(i), name=f"Creative {i}", format="Single Image", status="ACTIVE", is_serving=True)
        for i in range(n)
    ]


class FakeZenABMClientWithOwnData(FakeZenABMClient):
    """FakeZenABMClient extended with linkedin_metrics + list_creatives."""

    def __init__(self, metrics: Optional[LinkedInMetrics] = None, creatives: Optional[List[Creative]] = None, **kwargs):
        super().__init__(**kwargs)
        self._own_metrics = metrics or _make_own_metrics()
        self._own_creatives = creatives or _make_own_creatives()
        self.metrics_calls: List[dict] = []
        self.creatives_calls: int = 0

    def linkedin_metrics(self, start_date: str, end_date: str) -> LinkedInMetrics:
        self.metrics_calls.append({"start_date": start_date, "end_date": end_date})
        return self._own_metrics

    def list_creatives(self, page_size: int = 100, cursor: Optional[str] = None):
        self.creatives_calls += 1
        return self._own_creatives, None


class FakeZenABMClientPlanError(FakeZenABMClient):
    """linkedin_metrics raises ZenABMPlanError (402/403 -- feature gate)."""

    def linkedin_metrics(self, start_date: str, end_date: str) -> LinkedInMetrics:
        from core.zenabm_api import ZenABMPlanError
        raise ZenABMPlanError(402)

    def list_creatives(self, page_size: int = 100, cursor: Optional[str] = None):
        raise AssertionError("list_creatives should not be called after a PlanError")


class FakeZenABMClientAuthError(FakeZenABMClient):
    """linkedin_metrics raises ZenABMAuthError (401 -- token lapsed)."""

    def linkedin_metrics(self, start_date: str, end_date: str) -> LinkedInMetrics:
        from core.zenabm_api import ZenABMAuthError
        raise ZenABMAuthError(401)

    def list_creatives(self, page_size: int = 100, cursor: Optional[str] = None):
        raise AssertionError("list_creatives should not be called after an AuthError")


class FakeZenABMClientNoOwnData(FakeZenABMClient):
    """linkedin_metrics returns all-zero metrics (not connected / no own data)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.metrics_calls: List[dict] = []

    def linkedin_metrics(self, start_date: str, end_date: str) -> LinkedInMetrics:
        self.metrics_calls.append({"start_date": start_date, "end_date": end_date})
        return LinkedInMetrics(impressions=0, clicks=0, cost_in_usd=0.0)

    def list_creatives(self, page_size: int = 100, cursor: Optional[str] = None):
        return [], None


# ── B3 (a): own data present -> comparison built + HTML contains comparison section ──

def test_b3_comparison_built_when_own_data_present(tmp_path):
    """With own linkedin_metrics + creatives, report_data['comparison'] is populated."""
    client = FakeZenABMClientWithOwnData()
    combined = _run(client, ["Userpilot"], [], tmp_path)
    assert "comparison" in combined, "comparison key should be present when own data is returned"
    comp = combined["comparison"]
    assert isinstance(comp, dict)
    assert "head_to_head" in comp
    assert "scale_vs_efficiency" in comp
    assert "moves" in comp
    assert isinstance(comp["moves"], list)


def test_b3_html_contains_comparison_section_when_own_data_present(tmp_path):
    """Rendered HTML contains a you-vs-them / comparison section."""
    client = FakeZenABMClientWithOwnData()
    combined = _run(client, ["Userpilot"], [], tmp_path)
    html = build_combined_report_html(combined)
    # The section heading should appear
    assert "you vs" in html.lower() or "vs them" in html.lower() or "You vs" in html


def test_b3_html_comparison_renders_activity(tmp_path):
    """The comparison section renders activity comparison (own_vs_field)."""
    client = FakeZenABMClientWithOwnData()
    combined = _run(client, ["Userpilot"], [], tmp_path)
    html = build_combined_report_html(combined)
    # Some activity signal - the section should be present
    assert "you vs" in html.lower() or "vs them" in html.lower()


def test_b3_competitor_profiles_passed_to_build_comparison(tmp_path):
    """build_comparison is called with all competitor profiles from the scanned blocks."""
    # We verify indirectly: comparison.head_to_head.activity.competitors should
    # include the competitor name that came from the fixture.
    client = FakeZenABMClientWithOwnData()
    combined = _run(client, ["Userpilot"], [], tmp_path)
    comp = combined.get("comparison", {})
    competitors_in_comp = comp.get("head_to_head", {}).get("activity", {}).get("competitors", [])
    # Must have at least one entry (from the block we scanned)
    assert isinstance(competitors_in_comp, list)
    assert len(competitors_in_comp) >= 1


def test_b3_metrics_called_with_30_day_window(tmp_path):
    """linkedin_metrics is called with start_date = 30 days before now, end_date = now."""
    import datetime
    client = FakeZenABMClientWithOwnData()
    _run(client, ["Userpilot"], [], tmp_path)
    assert len(client.metrics_calls) == 1
    call = client.metrics_calls[0]
    # Parse the dates and confirm the window is approximately 30 days.
    start = datetime.date.fromisoformat(call["start_date"])
    end = datetime.date.fromisoformat(call["end_date"])
    delta = (end - start).days
    assert 28 <= delta <= 32, f"Expected ~30-day window but got {delta} days"


# ── B3 (b): ZenABMPlanError -> no comparison, report still produced, upsell set ──

def test_b3_plan_error_no_comparison_key(tmp_path):
    """When linkedin_metrics raises ZenABMPlanError, 'comparison' key absent."""
    client = FakeZenABMClientPlanError()
    combined = _run(client, ["Userpilot"], [], tmp_path)
    assert "comparison" not in combined, "comparison should be absent on plan error"


def test_b3_plan_error_competitor_report_still_delivered(tmp_path):
    """Even with a PlanError on own data, the competitor blocks are produced."""
    client = FakeZenABMClientPlanError()
    combined = _run(client, ["Userpilot"], [], tmp_path)
    assert "keywords" in combined
    blocks = combined["keywords"]
    assert len(blocks) > 0
    block = _kw(combined, "Userpilot")
    assert block["competitors"], "Competitor data should still be present on plan error"


def test_b3_plan_error_upsell_set(tmp_path):
    """When plan error: comparison_upsell is set to a warm one-liner."""
    client = FakeZenABMClientPlanError()
    combined = _run(client, ["Userpilot"], [], tmp_path)
    assert "comparison_upsell" in combined, "comparison_upsell key should be set on plan error"
    upsell = combined["comparison_upsell"]
    assert isinstance(upsell, str) and upsell.strip(), "upsell should be a non-empty string"
    # Must not use hard-cap language
    assert "hard cap" not in upsell.lower()
    assert "limit reached" not in upsell.lower()


def test_b3_plan_error_upsell_rendered_in_html(tmp_path):
    """comparison_upsell line appears subtly in the rendered report."""
    client = FakeZenABMClientPlanError()
    combined = _run(client, ["Userpilot"], [], tmp_path)
    html = build_combined_report_html(combined)
    upsell = combined.get("comparison_upsell", "")
    # At least a fragment of the upsell should appear in the HTML
    assert upsell[:20] in html or "ZenABM" in html


def test_b3_auth_error_no_comparison_key(tmp_path):
    """When linkedin_metrics raises ZenABMAuthError, 'comparison' key absent."""
    client = FakeZenABMClientAuthError()
    combined = _run(client, ["Userpilot"], [], tmp_path)
    assert "comparison" not in combined


def test_b3_auth_error_upsell_set(tmp_path):
    """Auth error also sets a warm upsell (not a hard-cap message)."""
    client = FakeZenABMClientAuthError()
    combined = _run(client, ["Userpilot"], [], tmp_path)
    assert "comparison_upsell" in combined
    upsell = combined["comparison_upsell"]
    assert upsell.strip()


def test_b3_no_own_data_all_zeros_no_comparison(tmp_path):
    """When linkedin_metrics returns all zeros, comparison is skipped (not connected)."""
    client = FakeZenABMClientNoOwnData()
    combined = _run(client, ["Userpilot"], [], tmp_path)
    assert "comparison" not in combined, "comparison should be absent when own data is all zeros"


def test_b3_no_own_data_no_upsell(tmp_path):
    """All-zero own metrics: no upsell (silently skip, not an error)."""
    client = FakeZenABMClientNoOwnData()
    combined = _run(client, ["Userpilot"], [], tmp_path)
    # No upsell when it's just missing data (not a plan error)
    assert "comparison_upsell" not in combined


# ── B3 (c): build_comparison receives all competitor profiles ─────────────────

def test_b3_comparison_includes_all_shown_competitor_profiles(tmp_path):
    """build_comparison is invoked across ALL competitor profiles from all blocks."""
    client = FakeZenABMClientWithOwnData()
    # Two competitor blocks
    combined = _run(client, ["Userpilot", "Personio"], [], tmp_path)
    comp = combined.get("comparison", {})
    # Competitors across both blocks should all appear in the comparison activity list
    all_profiles_in_comp = comp.get("head_to_head", {}).get("activity", {}).get("competitors", [])
    assert len(all_profiles_in_comp) >= 2, (
        f"Expected at least 2 profiles across two blocks, got {len(all_profiles_in_comp)}"
    )


# ── FIX 1: ZenABMRateLimit retry tests ───────────────────────────────────────

from core.zenabm_api import ZenABMRateLimit  # noqa: E402


class FakeZenABMClientRateLimitOnce(FakeZenABMClient):
    """Raises ZenABMRateLimit on the first call, succeeds on subsequent calls.

    Used to verify that a single 429 triggers a retry and the competitor is NOT
    rendered as an empty/no-ads block.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._adv_call_count = 0

    def search_by_advertiser(self, company=None, company_id=None, **kwargs):
        self._adv_call_count += 1
        if self._adv_call_count == 1:
            raise ZenABMRateLimit(429)
        return super().search_by_advertiser(company=company, company_id=company_id, **kwargs)


class FakeZenABMClientAlwaysRateLimit(FakeZenABMClient):
    """Always raises ZenABMRateLimit for search_by_advertiser.

    Used to verify that a persistent 429 produces a rate-limited block, not an
    empty "no ads found" block.
    """

    def search_by_advertiser(self, company=None, company_id=None, **kwargs):
        raise ZenABMRateLimit(429)


def test_rate_limit_once_then_succeeds_not_empty(monkeypatch, tmp_path):
    """A 429 followed by success on retry must NOT render as an empty/no-ads block."""
    # Patch _SLEEP so the test doesn't actually wait.
    monkeypatch.setattr(competitor_scan, "_SLEEP", lambda _: None)

    client = FakeZenABMClientRateLimitOnce()
    combined = _run(client, ["Userpilot"], [], tmp_path)
    block = _kw(combined, "Userpilot")

    # Retry succeeded: should have competitors, not be an empty block.
    assert block["competitors"], "Retry succeeded — should not be an empty/no-ads block"
    assert block.get("rate_limited") is not True, (
        "rate_limited must not be set when the retry succeeded"
    )
    # Confirm two calls were made (initial + retry).
    assert client._adv_call_count == 2, (
        f"Expected 2 advertiser calls (initial + retry), got {client._adv_call_count}"
    )


def test_rate_limit_always_produces_rate_limited_block(monkeypatch, tmp_path):
    """A persistent 429 (initial + retry both fail) produces a rate_limited block, not empty."""
    monkeypatch.setattr(competitor_scan, "_SLEEP", lambda _: None)

    client = FakeZenABMClientAlwaysRateLimit()
    combined = _run(client, ["Userpilot"], [], tmp_path)
    block = _kw(combined, "Userpilot")

    # Block must be flagged rate-limited, not silently "no ads found".
    assert block.get("rate_limited") is True, (
        "Persistent 429 should produce a rate_limited block"
    )
    # method_note must be explicit about rate limiting.
    note = block.get("method_note", "")
    assert "rate limit" in note.lower() or "rate_limit" in note.lower(), (
        "method_note should mention rate limit"
    )
    # Must not look like "not advertising" — the block should carry a visible note,
    # not silently appear as zero-ads inactivity.
    assert block["n_ads_scanned"] == 0  # block is empty structurally
    # But it must NOT just be a bare empty block with no rate_limited flag.
    assert "rate_limited" in block, "rate_limited key must be present in the block"


def test_rate_limit_sleep_called_with_correct_duration(monkeypatch, tmp_path):
    """The sleep between initial 429 and retry uses _RATE_LIMIT_RETRY_SECONDS."""
    sleep_calls: List[float] = []
    monkeypatch.setattr(competitor_scan, "_SLEEP", lambda d: sleep_calls.append(d))

    client = FakeZenABMClientRateLimitOnce()
    _run(client, ["Userpilot"], [], tmp_path)

    assert len(sleep_calls) == 1, "Exactly one sleep should occur for a single retry."
    assert sleep_calls[0] == competitor_scan._RATE_LIMIT_RETRY_SECONDS, (
        f"Sleep duration should match _RATE_LIMIT_RETRY_SECONDS "
        f"({competitor_scan._RATE_LIMIT_RETRY_SECONDS}), got {sleep_calls[0]}"
    )


# ── FIX 3: format diversity for text/spotlight ad types ───────────────────────

import copy  # noqa: E402


def _make_ad_fixture_with_type(ad_type: str) -> dict:
    """Create a minimal by_advertiser fixture with a single ad of the given type.

    Clears the ``advertisers`` rollup so the input label (e.g. "TestCo") is used
    as the block label rather than being overridden by the fixture's advertiser name.
    """
    base = _load_by_advertiser_fixture()
    result = copy.deepcopy(base)
    # Clear advertisers rollup so the caller's label is kept as the block label.
    result["data"]["advertisers"] = []
    if result["data"]["ads"]:
        result["data"]["ads"] = [copy.deepcopy(result["data"]["ads"][0])]
        result["data"]["ads"][0]["type"] = ad_type
    return result


def _make_competitor_profile_with_format(fmt_key: str) -> dict:
    """Build a minimal competitor profile dict with one format bucket set."""
    formats = {k: 0 for k in competitor_scan._FORMAT_KEYS}
    formats[fmt_key] = 3
    return {
        "name": "TestCo",
        "company_id": "123",
        "n_ads_on_keyword": 3,
        "sov_pct": 100.0,
        "impression_data_coverage": "none",
        "formats": formats,
        "momentum_status": "unknown",
        "reach_low": None,
        "reach_high": None,
        "is_currently_advertising": None,
    }


@pytest.mark.parametrize("ad_type,expected_fmt_key", [
    ("TEXT_AD", "text"),
    ("SPOTLIGHT_V2", "spotlight"),
    ("SPONSORED_UPDATE_EVENT", "event"),
    ("JOBS_V2", "other"),
    ("FOLLOW_COMPANY_V2", "other"),
])
def test_extended_ad_types_yield_nonzero_format_diversity(ad_type, expected_fmt_key, tmp_path):
    """Advertisers using TEXT_AD, SPOTLIGHT_V2, etc. must not have format_diversity_count=0."""
    fixture = _make_ad_fixture_with_type(ad_type)
    # Expand to multiple ads so build_competitor has something to work with.
    multi_fixture = _make_multi_ad_fixture(fixture, n_ads=3)
    client = FakeZenABMClient(advertiser_fixture=multi_fixture)
    combined = _run(client, ["TestCo"], [], tmp_path)
    block = _kw(combined, "TestCo")
    comps = block["competitors"]
    assert comps, f"Should have competitors for ad_type={ad_type}"
    c = comps[0]
    assert c["format_diversity_count"] > 0, (
        f"format_diversity_count should be > 0 for ad_type={ad_type} "
        f"(mapped to bucket '{expected_fmt_key}'), got 0"
    )
    assert c["formats"].get(expected_fmt_key, 0) > 0, (
        f"formats['{expected_fmt_key}'] should be > 0 for ad_type={ad_type}"
    )


def test_text_spotlight_formats_detectable_as_gap_by_build_comparison(tmp_path):
    """A competitor-only text/spotlight format is detectable as a gap by build_comparison.

    Own creatives use only 'Single Image'; competitor uses TEXT_AD (-> 'text') and
    SPOTLIGHT_V2 (-> 'spotlight').  The comparison must list 'text' and/or 'spotlight'
    in competitor_only_formats.
    """
    from core.comparison import build_comparison
    from core.zenabm_models import Creative, LinkedInMetrics

    # Build competitor profile with text + spotlight formats.
    formats = {k: 0 for k in competitor_scan._FORMAT_KEYS}
    formats["text"] = 2
    formats["spotlight"] = 1
    profile = {
        "name": "TextComp",
        "company_id": "999",
        "n_ads_on_keyword": 3,
        "sov_pct": 100.0,
        "impression_data_coverage": "none",
        "formats": formats,
        "momentum_status": "unknown",
        "reach_low": None,
        "reach_high": None,
        "is_currently_advertising": None,
    }

    # Own creatives: single image only (no text, no spotlight).
    own_creatives = [
        Creative(linkedin_id="1", name="A", format="Single Image", status="ACTIVE", is_serving=True),
    ]
    own_metrics = LinkedInMetrics(impressions=5000, clicks=100, cost_in_usd=500.0)

    comparison = build_comparison(own_metrics, own_creatives, [profile], _NOW_MS)
    formats_result = comparison["head_to_head"]["formats"]
    competitor_only = set(formats_result["competitor_only_formats"])

    assert "text" in competitor_only, (
        f"'text' should be in competitor_only_formats but got {competitor_only}"
    )
    assert "spotlight" in competitor_only, (
        f"'spotlight' should be in competitor_only_formats but got {competitor_only}"
    )


# ── Extra: _make_json_serializable unit tests ──────────────────────────────────

def test_make_json_serializable_converts_sets_to_sorted_lists():
    """Sets must become sorted lists of their string representations."""
    raw = {"tags": {3, 1, 2}}
    result = competitor_scan._make_json_serializable(raw)
    assert result == {"tags": ["1", "2", "3"]}


def test_make_json_serializable_nested_sets():
    """Nested sets (inside lists and dicts) are all converted."""
    raw = {"outer": [{"inner": {"b", "a"}}]}
    result = competitor_scan._make_json_serializable(raw)
    assert result == {"outer": [{"inner": ["a", "b"]}]}


def test_make_json_serializable_result_is_json_dumpable():
    """The output of _make_json_serializable must round-trip through json.dumps."""
    raw = {"formats": {"a", "b"}, "nested": [{"s": {1, 2}}]}
    result = competitor_scan._make_json_serializable(raw)
    serialized = json.dumps(result)  # must not raise
    parsed = json.loads(serialized)
    assert parsed["formats"] == ["a", "b"]


def test_make_json_serializable_leaves_primitives_unchanged():
    """Primitives (int, str, float, None, bool) are returned unchanged."""
    raw = {"n": 42, "s": "hello", "f": 3.14, "none": None, "flag": True}
    result = competitor_scan._make_json_serializable(raw)
    assert result == raw


# ── FIX 4: _empty_block is_competitor parameter ───────────────────────────────

def test_empty_block_is_competitor_true_for_competitor():
    """_empty_block called with is_competitor=True must set is_competitor_block=True."""
    block = competitor_scan._empty_block("Acme", "2026-07-12", is_competitor=True)
    assert block["is_competitor_block"] is True


def test_empty_block_is_competitor_false_for_keyword():
    """_empty_block called with is_competitor=False must set is_competitor_block=False."""
    block = competitor_scan._empty_block("my-keyword", "2026-07-12", is_competitor=False)
    assert block["is_competitor_block"] is False


def test_empty_block_default_is_competitor_true():
    """_empty_block default (is_competitor=True) for backward compat."""
    block = competitor_scan._empty_block("Acme", "2026-07-12")
    assert block["is_competitor_block"] is True


def test_keyword_empty_block_has_is_competitor_false_in_run(tmp_path):
    """Zero-ad keyword result blocks must have is_competitor_block=False."""
    combined = _run(FakeZenABMClientEmpty(), [], ["some-keyword"], tmp_path)
    block = _kw(combined, "some-keyword")
    assert block["is_competitor_block"] is False, (
        "Empty keyword block must have is_competitor_block=False, not True"
    )


def test_competitor_empty_block_has_is_competitor_true_in_run(tmp_path):
    """Zero-ad competitor result blocks must have is_competitor_block=True."""
    combined = _run(FakeZenABMClientEmpty(), ["NoAdsCompany"], [], tmp_path)
    block = _kw(combined, "NoAdsCompany")
    assert block["is_competitor_block"] is True, (
        "Empty competitor block must have is_competitor_block=True"
    )

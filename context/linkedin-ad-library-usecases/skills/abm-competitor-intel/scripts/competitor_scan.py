#!/usr/bin/env python3
"""ABM competitor scan -- the skill's entry script.

Powers a two-step "script computes the data, Zena writes the insights" flow
that produces one COMBINED, multi-competitor-and-keyword report:

  1. **Compute mode** (default): for each competitor, call the ZenABM API's
     ``/ad-library/by-advertiser`` endpoint; for each discovery keyword, call
     ``/ad-library/by-keyword``. Derive per-competitor signals via
     ``core.signals``, honoring the golden rule (Tier S/T signals degrade to
     ``None``/unknown when impression coverage is none, never to False/0).
     Assemble ONE combined data object, write it to ``report_data.json``,
     render a DRAFT ``report.html``, and print a compact DIGEST to stdout that
     Zena reads to author the insight fields.

  2. **Render mode** (``--render report_data.json``): after Zena has rewritten
     the insight fields inside ``report_data.json``, reload the JSON and render
     the FINAL combined ``report.html`` -- baking Zena's authored insights into
     the shipped report.

Competitor input:
  * A company name (``Personio``), a LinkedIn vanity slug
    (``linkedin.com/company/personio``), or a full URL -- all resolve.
  * Numeric-id URLs (``/company/10180448``) may return empty results; if so,
    the user is told to provide the advertiser name instead.
  * The matched advertiser is confirmed via ``result.advertisers[0].name``.

On ``ZenABMAuthError``/``ZenABMPlanError``: a warm, subtle upsell line is
printed and the script exits gracefully (no hard-cap language).

Env:
  * ``ZENABM_TOKEN``        -- Bearer token, required at request time.
  * ``ZENABM_API_BASE_URL`` -- optional base-url override.

A local ``.env`` is loaded via python-dotenv when present.
Only ``core.report_html`` (stdlib-only) is imported at module top level so
``--render`` mode works with no third-party deps.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import OrderedDict
from typing import Any, Callable, Dict, List, Optional, Sequence, TYPE_CHECKING

from core.report_html import build_combined_report_html, write_combined_report

if TYPE_CHECKING:
    from core.zenabm_api import ZenABMClient
    from core.zenabm_models import Ad


# ── Constants ────────────────────────────────────────────────────────────────

#: Scan depth: server ignores limit > 100; this is the sample ceiling.
_SCAN_LIMIT = 100

#: > 90 days of continuous running = a "long-runner".
_LONG_RUNNER_DAYS = 90.0

#: Sleep duration (seconds) between a 429 and the single retry.
#: Approximately 35 s per the API knowledge base (hard limit: ~10 req/30 s).
_RATE_LIMIT_RETRY_SECONDS = 35

#: Injectable sleep function so tests can monkeypatch without real delays.
_SLEEP: Callable[[float], None] = time.sleep

#: Ordered format keys the renderer's stacked bars expect.
#: Vocabulary is aligned with ``core.comparison._normalize_format`` so format-gap
#: detection works both ways (own creatives normalize to these same keys).
_FORMAT_KEYS = (
    "video", "single_image", "carousel", "document", "message",
    "text", "spotlight", "thought_leader", "event", "other",
)

#: Ad-type -> renderer format bucket.
#: Keys are LinkedIn ad type strings from the API.
#: Buckets align with ``_normalize_format`` canonical names in ``core.comparison``.
_TYPE_TO_FORMAT: Dict[str, str] = {
    "SPONSORED_STATUS_UPDATE": "single_image",
    "SPONSORED_VIDEO": "video",
    "SPONSORED_UPDATE_CAROUSEL": "carousel",
    "SPONSORED_UPDATE_NATIVE_DOCUMENT": "document",
    "SPONSORED_MESSAGE": "message",
    "SPONSORED_INMAILS": "message",
    # Extended types (FIX 3)
    "TEXT_AD": "text",
    "SPOTLIGHT_V2": "spotlight",
    "SPONSORED_UPDATE_EVENT": "event",
    "JOBS_V2": "other",
    "FOLLOW_COMPANY_V2": "other",
}

#: Ad-type -> human label for ``ad_types_used`` display.
_TYPE_LABELS: Dict[str, str] = {
    "SPONSORED_STATUS_UPDATE": "Single image",
    "SPONSORED_VIDEO": "Video",
    "SPONSORED_UPDATE_CAROUSEL": "Carousel",
    "SPONSORED_UPDATE_NATIVE_DOCUMENT": "Document",
    "SPONSORED_MESSAGE": "Message",
    "SPONSORED_INMAILS": "Message",
    # Extended types (FIX 3)
    "TEXT_AD": "Text",
    "SPOTLIGHT_V2": "Spotlight",
    "SPONSORED_UPDATE_EVENT": "Event",
    "JOBS_V2": "Jobs",
    "FOLLOW_COMPANY_V2": "Follow company",
}

#: signals campaign_size_tier -> renderer reach band vocabulary.
_SIZE_TIER_TO_REACH_TIER: Dict[str, str] = {
    "micro": "micro",
    "small": "small",
    "medium": "mid",
    "large": "large",
    "enterprise": "enterprise",
}

_COUNTRY_NAMES: Dict[str, str] = {
    "US": "United States", "GB": "United Kingdom", "DE": "Germany",
    "FR": "France", "CA": "Canada", "AU": "Australia", "NL": "Netherlands",
    "IE": "Ireland", "ES": "Spain", "IT": "Italy", "SE": "Sweden",
    "PL": "Poland", "BE": "Belgium", "AT": "Austria", "CH": "Switzerland",
    "DK": "Denmark", "FI": "Finland", "NO": "Norway", "PT": "Portugal",
    "IN": "India", "JP": "Japan", "BR": "Brazil", "MX": "Mexico",
    "SG": "Singapore", "AE": "United Arab Emirates", "SA": "Saudi Arabia",
    "IL": "Israel", "TR": "Turkey", "ZA": "South Africa", "NG": "Nigeria",
    "CZ": "Czechia", "GR": "Greece", "HU": "Hungary", "RO": "Romania",
    "EE": "Estonia", "SI": "Slovenia", "SK": "Slovakia", "HR": "Croatia",
    "BG": "Bulgaria", "LT": "Lithuania", "LV": "Latvia", "LU": "Luxembourg",
    "EG": "Egypt", "KE": "Kenya", "RS": "Serbia", "UA": "Ukraine",
}


# ── Small helpers ─────────────────────────────────────────────────────────────

def _country_name(code: str) -> str:
    return _COUNTRY_NAMES.get(code.upper(), code.upper())


def _parse_list(raw: str) -> List[str]:
    """Split a comma-separated value into cleaned, de-duped items."""
    seen: "OrderedDict[str, None]" = OrderedDict()
    for part in (raw or "").split(","):
        term = part.strip()
        if term and term.lower() not in {k.lower() for k in seen}:
            seen[term] = None
    return list(seen.keys())


def _is_numeric_id_url(value: str) -> bool:
    """True if value looks like a numeric-id LinkedIn company URL."""
    return bool(re.search(r"linkedin\.com/company/\d+", value))


# ── Per-competitor field assembly ─────────────────────────────────────────────

def _format_counts(ads: Sequence[Any]) -> Dict[str, int]:
    """Count creative formats into the renderer's five buckets."""
    counts = {k: 0 for k in _FORMAT_KEYS}
    for a in ads:
        bucket = _TYPE_TO_FORMAT.get(a.type)
        if bucket:
            counts[bucket] += 1
    return counts


def _ad_type_labels(ads: Sequence[Any]) -> List[str]:
    """Distinct human labels for the creative types used, stable-ordered."""
    seen: "OrderedDict[str, None]" = OrderedDict()
    for a in ads:
        label = _TYPE_LABELS.get(a.type, a.type)
        seen.setdefault(label, None)
    return list(seen.keys())


def _agency_run(ads: Sequence[Any]) -> "tuple[bool, Optional[str]]":
    """Tier N -- agency-run when payer differs from advertiser name."""
    from core.signals import ad_payer_differs_normalized

    for a in ads:
        if ad_payer_differs_normalized(a):
            return True, a.advertiser.payer
    return False, None


def _momentum_status(signals: Dict[str, Any]) -> str:
    """Composite momentum label from coverage-gated Tier S signals."""
    if signals["impression_data_coverage"] == "none":
        return "unknown"
    new = signals.get("is_new_advertiser")
    ramp = signals.get("is_ramping_up")
    dark = signals.get("is_dark_period")
    curr = signals.get("is_currently_advertising")
    if dark:
        return "dark"
    if new:
        return "new"
    if ramp:
        return "ramping"
    if curr is False:
        return "cooling"
    if curr:
        return "steady"
    return "unknown"


def _reach_bounds(signals: Dict[str, Any]) -> "tuple[Optional[int], Optional[int]]":
    """Company-level reach as (low, high) or (None, None)."""
    est = signals.get("total_impressions_est")
    if not est:
        return None, None
    return int(est["lower"]), int(est["upper"])


def _reach_tier(signals: Dict[str, Any]) -> Optional[str]:
    """Reach band from per-ad campaign size tiers (the largest observed)."""
    tiers = signals.get("campaign_size_tier_per_ad")
    if not tiers:
        return None
    order = ["micro", "small", "medium", "large", "enterprise"]
    best = None
    best_rank = -1
    for t in tiers:
        if t is None:
            continue
        rank = order.index(t)
        if rank > best_rank:
            best_rank = rank
            best = t
    if best is None:
        return None
    return _SIZE_TIER_TO_REACH_TIER.get(best, best)


def _ad_longevity(
    ads: Sequence[Any], coverage: str
) -> "tuple[Optional[int], Optional[bool]]":
    """Longest continuous run in days + the long-runner flag."""
    from core.signals import campaign_duration_days

    if coverage == "none":
        return None, None
    durations = [d for d in (campaign_duration_days(a) for a in ads) if d is not None]
    if not durations:
        return None, None
    longest = max(durations)
    return int(round(longest)), longest >= _LONG_RUNNER_DAYS


def _cadence_shape(ads: Sequence[Any], signals: Dict[str, Any]) -> Optional[str]:
    """Rough cadence: one-off, bursty, or steady. None when coverage is none."""
    if signals["impression_data_coverage"] == "none":
        return None
    stats_ads = [a for a in ads if a.statistics is not None]
    if not stats_ads:
        return None
    if len(stats_ads) == 1:
        return "one-off"
    firsts = sorted(a.statistics.first_impression_at for a in stats_ads)
    span_days = (firsts[-1] - firsts[0]) / 86_400_000
    if span_days <= 7:
        return "bursty"
    return "steady"


def _top_regions(signals: Dict[str, Any], k: int = 3) -> Optional[List[Dict[str, Any]]]:
    """Top-k countries by impression share."""
    shares = signals.get("country_impression_share_pct")
    if not shares:
        return None
    top = sorted(shares.items(), key=lambda kv: kv[1], reverse=True)[:k]
    return [{"country": _country_name(code), "pct": round(pct, 1)} for code, pct in top]


def _geo_summary(top_regions: Optional[List[Dict[str, Any]]]) -> Optional[str]:
    """Short plain sentence from top regions, or None."""
    if not top_regions:
        return None
    parts = [f"{r['country']} {r['pct']:.0f}%" for r in top_regions]
    return ", ".join(parts)


def _primary_eu_market(signals: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Render-ready primary market {country, share_pct, caveat} or None."""
    pm = signals.get("primary_market_country")
    if not pm:
        return None
    caveat = "of disclosed impressions"
    if pm.get("caveat") == "eu_visible_only":
        caveat = "EU-visible subset only"
    return {
        "country": _country_name(str(pm["country"])),
        "share_pct": round(float(pm["share_pct"]), 1),
        "caveat": caveat,
    }


def _targeting_dimensions_count(ads: Sequence[Any], coverage: str) -> Optional[int]:
    """Distinct targeting facet names used (Tier T; gated)."""
    if coverage == "none":
        return None
    facets = set()
    for a in ads:
        for f in a.targeting:
            facets.add(f.facet)
    return len(facets) if facets else 0


def _baseline_read_line(c: Dict[str, Any]) -> str:
    """BASELINE plain rule-based read line (Zena rewrites this)."""
    coverage = c["impression_data_coverage"]
    run_by = "Agency-run" if c["agency_run"] else "In-house"
    fmt_count = c["format_diversity_count"]
    single_only = fmt_count <= 1

    if coverage == "none":
        base = f"{run_by} and " + ("single-format only" if single_only else "uses a few formats")
        return base + " - beatable on creative range. Reach and momentum are not public, not zero."

    momentum = c["momentum_status"]
    if momentum == "new":
        return "Fresh push - just started here. Watch them; they will get louder."
    if momentum == "ramping":
        return "Ramping up fast on this theme. Act before they get hard to catch."
    if momentum == "dark":
        return "Was active, now gone quiet. If they stay dark there is share to take."
    if c.get("is_long_runner"):
        return "Long-runner - keeps winning ads live for months. Study their creative before you brief yours."
    if c.get("targets_specific_companies"):
        return "Chasing specific accounts, not the broad market - likely after the same buyers you want."
    if single_only:
        return f"{run_by} and single-format - a beatable, narrow presence. Out-do them on format range."
    return f"{run_by} and steady - a mid-pack name to pass, not to fear."


def build_competitor(
    ads: List[Any],
    *,
    company_id: Optional[str],
    adv_type: str,
    now_ms: int,
    label: str,
) -> Dict[str, Any]:
    """Assemble one competitor dict in the exact ``report_html`` contract shape."""
    from core.signals import compute_company_signals

    signals = compute_company_signals(ads, now_ms)
    coverage = str(signals["impression_data_coverage"])
    first = ads[0]

    agency_run, payer = _agency_run(ads)
    formats = _format_counts(ads)
    ad_types = _ad_type_labels(ads)
    reach_low, reach_high = _reach_bounds(signals)
    longevity, is_long = _ad_longevity(ads, coverage)
    top_regions = _top_regions(signals)
    geo_summary = _geo_summary(top_regions)
    eu_mean = signals.get("eu_disclosed_share_mean")

    return {
        "rank": 0,  # stamped after ranking
        "name": first.advertiser.name,
        "company_id": company_id,
        "advertiser_type": adv_type,
        "advertiser_url": first.advertiser.url,
        "n_ads_on_keyword": len(ads),
        "impression_data_coverage": coverage,

        # Tier N (always rendered)
        "linkedin_maturity_score": int(signals["linkedin_maturity_score"]),
        "ad_types_used": ad_types,
        "format_diversity_count": sum(1 for v in formats.values() if v > 0),
        "agency_run": agency_run,
        "ad_payer_name": payer,
        "formats": formats,

        # Tier S (gated; None -> "unknown")
        "is_currently_advertising": signals["is_currently_advertising"],
        "momentum_status": _momentum_status(signals),
        "outreach_timing_score": signals["outreach_timing_score"],
        "reach_low": reach_low,
        "reach_high": reach_high,
        "reach_tier": _reach_tier(signals),
        "reach_confidence": {
            "full": "higher confidence",
            "partial": "partial coverage",
            "none": "not available",
        }.get(coverage, "partial coverage"),
        "ad_longevity_days": longevity,
        "is_long_runner": is_long,
        "cadence_shape": _cadence_shape(ads, signals),
        "eu_disclosed_share_pct": round(float(eu_mean), 1) if eu_mean is not None else None,
        "primary_eu_market": _primary_eu_market(signals),
        "top_regions": top_regions,
        "geo_summary": geo_summary,
        "active_ads_7d": signals.get("active_ads_7d"),
        "active_ads_30d": signals.get("active_ads_30d"),
        "active_ads_90d": signals.get("active_ads_90d"),
        "sov_pct": 0.0,  # filled once the field total is known

        # Tier T (gated; None -> "unknown")
        "funnel_stage": signals["funnel_stage"],
        "targets_specific_companies": signals["targets_specific_companies"],
        "targets_job_roles": signals["targets_job_roles"],
        "uses_retargeting": signals["uses_retargeting"],
        "targeting_dimensions_count": _targeting_dimensions_count(ads, coverage),

        "read": "",  # BASELINE filled after ranking; Zena rewrites in report_data.json
        "sample_ad_url": first.ad_url,
    }


def _rank_key(c: Dict[str, Any]) -> tuple:
    """Rank by share of voice first; visibility never buries volume.

    Sorted DESCENDING (caller uses ``reverse=True``) on:
      1. n_ads_on_keyword     - share of voice
      2. linkedin_maturity_score
      3. active_tiebreak      - {True: 2, None: 1, False: 0}
    """
    active_tiebreak = {True: 2, None: 1, False: 0}[c["is_currently_advertising"]]
    return (c["n_ads_on_keyword"], c["linkedin_maturity_score"], active_tiebreak)


# ── Per-block assembly ────────────────────────────────────────────────────────

def build_block(
    label: str,
    ads: List[Any],
    *,
    now_ms: int,
    generated_at: str,
    is_competitor: bool = True,
) -> Dict[str, Any]:
    """Group ads -> competitors + thought-leaders, build the block.

    ``label`` is the competitor name or keyword used to title this block.
    """
    from core.signals import (
        ad_payer_differs_normalized,
        advertiser_type,
        linkedin_company_id,
    )

    company_groups: "OrderedDict[str, List[Any]]" = OrderedDict()
    individual_groups: "OrderedDict[str, List[Any]]" = OrderedDict()

    for ad in ads:
        atype = advertiser_type(ad)
        if atype == "individual":
            individual_groups.setdefault(ad.advertiser.url, []).append(ad)
        else:
            cid = linkedin_company_id(ad)
            key = cid if cid is not None else ad.advertiser.url
            company_groups.setdefault(key, []).append(ad)

    competitors: List[Dict[str, Any]] = [
        build_competitor(
            group,
            company_id=linkedin_company_id(group[0]),
            adv_type=advertiser_type(group[0]),
            now_ms=now_ms,
            label=label,
        )
        for group in company_groups.values()
    ]

    competitors.sort(key=_rank_key, reverse=True)

    company_ad_total = sum(c["n_ads_on_keyword"] for c in competitors) or 1
    for i, c in enumerate(competitors, start=1):
        c["rank"] = i
        c["sov_pct"] = round(c["n_ads_on_keyword"] / company_ad_total * 100, 1)
        c["read"] = _baseline_read_line(c)

    coverage_breakdown = {"full": 0, "partial": 0, "none": 0}
    for c in competitors:
        coverage_breakdown[c["impression_data_coverage"]] += 1

    field_format = {k: 0 for k in _FORMAT_KEYS}
    for c in competitors:
        for k in _FORMAT_KEYS:
            field_format[k] += c["formats"][k]

    n_agency_run = sum(1 for c in competitors if c["agency_run"])
    n_currently = sum(1 for c in competitors if c["is_currently_advertising"] is True)
    n_long_runners = sum(1 for c in competitors if c.get("is_long_runner") is True)
    n_none = coverage_breakdown["none"]
    n_companies = len(competitors)
    pct_us_only = round(n_none / n_companies * 100, 1) if n_companies else 0.0

    thought_leaders: List[Dict[str, Any]] = []
    for group in individual_groups.values():
        first = group[0]
        adv = first.advertiser
        payer = None
        if ad_payer_differs_normalized(first) and adv.payer:
            payer = adv.payer
        thought_leaders.append({
            "name": adv.name,
            "advertiser_url": adv.url,
            "n_ads_on_keyword": len(group),
            "promoted_by": payer,
            "sample_ad_url": first.ad_url,
        })

    whitespace, threats = _baseline_whitespace_and_threats(competitors, field_format)
    n_more = max(0, n_companies - 5)

    return {
        "keyword": label,
        "is_competitor_block": is_competitor,
        "geographies": "Global",
        "total_matching_ads": len(ads),
        "n_ads_scanned": len(ads),
        "n_individuals": len(thought_leaders),
        "generated_at": generated_at,

        "coverage_breakdown": coverage_breakdown,
        "pct_us_only": pct_us_only,
        "field_format_distribution": field_format,
        "n_agency_run": n_agency_run,
        "n_thought_leaders": len(thought_leaders),
        "n_currently_advertising": n_currently,
        "n_long_runners": n_long_runners,
        "thought_leaders": thought_leaders,

        "competitors": competitors,
        "where_you_can_win": whitespace,
        "what_to_watch": threats,
        "whitespace": whitespace,
        "threats": threats,
        "method_note": (
            "This report is built from public advertising activity via ZenABM. "
            "For some advertisers we can see full detail; for others (marked "
            "limited visibility) detailed reach is not publicly available, so we "
            "show what we can and never guess. Limited visibility does not mean "
            "a company is inactive."
        ),
        "upgrade_teaser": "",
        "n_more_competitors": n_more,
    }


def _empty_block(label: str, generated_at: str, *, is_competitor: bool = True) -> Dict[str, Any]:
    """A minimal honest 'no advertisers found' block."""
    return {
        "keyword": label,
        "is_competitor_block": is_competitor,
        "geographies": "Global",
        "total_matching_ads": 0,
        "n_ads_scanned": 0,
        "n_individuals": 0,
        "generated_at": generated_at,
        "coverage_breakdown": {"full": 0, "partial": 0, "none": 0},
        "pct_us_only": 0.0,
        "field_format_distribution": {k: 0 for k in _FORMAT_KEYS},
        "n_agency_run": 0,
        "n_thought_leaders": 0,
        "n_currently_advertising": 0,
        "n_long_runners": 0,
        "thought_leaders": [],
        "competitors": [],
        "where_you_can_win": [],
        "what_to_watch": [],
        "whitespace": [],
        "threats": [],
        "method_note": (
            "This report is built from public advertising activity via ZenABM. "
            "No matching public ads were found for this entry in the sample; "
            "this does not mean the company is not advertising."
        ),
        "upgrade_teaser": "",
        "n_more_competitors": 0,
    }


def _baseline_whitespace_and_threats(
    competitors: List[Dict[str, Any]],
    field_format: Dict[str, int],
) -> "tuple[List[str], List[str]]":
    """BASELINE opinion-labeled openings + watch-outs (Zena rewrites these)."""
    whitespace: List[str] = []
    threats: List[str] = []

    total_fmt = sum(field_format.values())
    if total_fmt:
        if field_format.get("video", 0) / total_fmt < 0.15:
            whitespace.append("Almost no one uses video. One good video would stand out fast.")
        if field_format.get("document", 0) == 0:
            whitespace.append("No one runs how-to / document ads here. Go first for cheap attention.")
        if field_format.get("message", 0) == 0:
            whitespace.append("No one uses the message ad format. It is cheap and untried here.")

    leader = competitors[0] if competitors else None
    if leader and leader.get("is_long_runner"):
        threats.append(
            f"{leader['name']} keeps adding ads and keeps the good ones running. "
            "Wait too long and their lead grows."
        )
    ramping = next((c for c in competitors if c["momentum_status"] in ("new", "ramping")), None)
    if ramping:
        threats.append(
            f"{ramping['name']} is new and getting loud fast. Act before they get "
            "hard to catch."
        )
    abm = next((c for c in competitors if c.get("targets_specific_companies") is True), None)
    if abm:
        threats.append(
            f"{abm['name']} aims at a few set companies. They may want the same "
            "buyers you do."
        )

    return whitespace, threats


# ── Combined assembly ─────────────────────────────────────────────────────────

def _cross_theme_rivals(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Advertisers appearing across 2+ blocks, deduped by company_id."""
    by_key: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
    for block in blocks:
        label = block.get("keyword", "")
        for c in block.get("competitors", []) or []:
            cid = c.get("company_id")
            dedupe_key = str(cid) if cid is not None else str(c.get("advertiser_url") or c.get("name"))
            entry = by_key.get(dedupe_key)
            if entry is None:
                entry = {
                    "name": c.get("name"),
                    "company_id": cid,
                    "advertiser_url": c.get("advertiser_url"),
                    "keywords": [],
                }
                by_key[dedupe_key] = entry
            if label and label not in entry["keywords"]:
                entry["keywords"].append(label)

    rivals = [
        {
            "name": e["name"],
            "company_id": e["company_id"],
            "advertiser_url": e["advertiser_url"],
            "keywords": e["keywords"],
            "n_keywords": len(e["keywords"]),
        }
        for e in by_key.values()
        if len(e["keywords"]) >= 2
    ]
    rivals.sort(key=lambda r: (-r["n_keywords"], str(r["name"] or "").lower()))
    return rivals


def _baseline_cross_keyword_summary(
    blocks: List[Dict[str, Any]],
    cross_theme_rivals: List[Dict[str, Any]],
) -> List[str]:
    """BASELINE cross-block takeaways (Zena rewrites these)."""
    bullets: List[str] = []

    for rival in cross_theme_rivals[:1]:
        themes = ", ".join(rival.get("keywords", []))
        bullets.append(
            f"{rival['name']} is advertising across more than one of your tracked "
            f"entries ({themes}). A rival spanning several themes is the one to beat overall."
        )

    for block in blocks:
        comps = block.get("competitors", []) or []
        if comps:
            leader = comps[0]
            bullets.append(
                f"For \"{block['keyword']}\", {leader['name']} runs the most ads right "
                "now. They are the front-runner to watch."
            )

    total_fmt = 0
    total_video = 0
    for block in blocks:
        ff = block.get("field_format_distribution") or {}
        total_fmt += sum(int(ff.get(k, 0)) for k in _FORMAT_KEYS)
        total_video += int(ff.get("video", 0))
    if total_fmt and total_video / total_fmt < 0.15:
        bullets.append(
            "Almost no one runs video across your tracked competitors. "
            "That gap is wide open for you."
        )

    return bullets


def build_combined_report_data(
    blocks: List[Dict[str, Any]],
    *,
    generated_at: str,
) -> Dict[str, Any]:
    """Assemble the COMBINED data object from per-block data."""
    rivals = _cross_theme_rivals(blocks)
    return {
        "generated_at": generated_at,
        "geographies": "Global",
        "free_tier_note": "",
        "cross_keyword_summary": _baseline_cross_keyword_summary(blocks, rivals),
        "keywords": blocks,
        "cross_theme_rivals": rivals,
        "method_note": (
            "This report is built from public advertising activity via ZenABM. "
            "For some advertisers we can see full detail; for others (marked "
            "limited visibility) detailed reach is not publicly available, so we "
            "show what we can and never guess. Limited visibility does not mean "
            "a company is inactive. ZenABM fills these gaps with data you cannot "
            "get from public sources alone."
        ),
        "upgrade_teaser": "",
    }


# ── DIGEST ────────────────────────────────────────────────────────────────────

def _signal_bits(c: Dict[str, Any]) -> str:
    """A compact single-line summary of one competitor's key signals."""
    bits: List[str] = []
    bits.append(f"ads={c.get('n_ads_on_keyword')}")
    bits.append(f"coverage={c['impression_data_coverage']}")
    bits.append("agency-run" if c["agency_run"] else "in-house")
    if c.get("ad_payer_name"):
        bits.append(f"payer={c['ad_payer_name']}")
    fmts = c.get("ad_types_used") or []
    bits.append("formats=" + (", ".join(fmts) if fmts else "none"))
    bits.append(f"format-diversity={c.get('format_diversity_count')}")
    bits.append(f"maturity={c['linkedin_maturity_score']}/10")
    bits.append(f"momentum={c['momentum_status']}")

    a30, a90 = c.get("active_ads_30d"), c.get("active_ads_90d")
    if a30 is not None or a90 is not None:
        bits.append(f"active-ads=30d:{a30 if a30 is not None else '?'}/90d:{a90 if a90 is not None else '?'}")
    else:
        bits.append("active-ads=unknown")

    reach_low, reach_high = c.get("reach_low"), c.get("reach_high")
    if reach_low is not None or reach_high is not None:
        lo = f"{reach_low:,}" if reach_low is not None else "?"
        hi = f"{reach_high:,}" if reach_high is not None else "?"
        bits.append(f"reach={lo}-{hi} ({c.get('reach_tier') or 'unknown'})")
    else:
        bits.append("reach=unknown")

    geo = c.get("geo_summary")
    bits.append(f"geo={geo}" if geo else "geo=unknown")

    eu = c.get("eu_disclosed_share_pct")
    bits.append(f"eu-disclosed={eu}%" if eu is not None else "eu-disclosed=unknown")

    long_days = c.get("ad_longevity_days")
    if long_days is not None:
        tag = " (long-runner)" if c.get("is_long_runner") else ""
        bits.append(f"longevity={long_days}d{tag}")
    else:
        bits.append("longevity=unknown")

    cadence = c.get("cadence_shape")
    bits.append(f"cadence={cadence}" if cadence else "cadence=unknown")

    funnel = c.get("funnel_stage")
    bits.append(f"funnel={funnel}" if funnel else "funnel=unknown")

    timing = c.get("outreach_timing_score")
    if timing is not None:
        bits.append(f"outreach-timing={timing}/8")

    if c.get("targets_specific_companies") is True:
        bits.append("ABM/named-accounts")
    if c.get("targets_job_roles") is True:
        bits.append("targets-roles")
    if c.get("uses_retargeting") is True:
        bits.append("retargeting")
    return "; ".join(bits)


def print_digest(
    combined: Dict[str, Any],
    *,
    out_dir: str,
    json_path: str,
    html_path: str,
    stdout: Any,
) -> None:
    """Print a compact DIGEST for Zena to author insights from."""

    def emit(line: str = "") -> None:
        print(line, file=stdout)

    emit("=" * 68)
    emit("DIGEST -- read this + report_data.json, then AUTHOR the insight fields.")
    emit("=" * 68)
    emit(f"Data:   {json_path}")
    emit(f"Draft:  {html_path}")
    emit(f"Entries: {', '.join(k['keyword'] for k in combined['keywords'])}")
    emit()

    for block in combined["keywords"]:
        emit(f'ENTRY: "{block["keyword"]}"')
        emit(f"  {block['n_ads_scanned']} ads found in public advertising data")
        competitors = block.get("competitors", [])
        if not competitors:
            emit("  No advertisers found.")
            emit()
            continue
        top = competitors[:5]
        emit(f"  Top {len(top)} competitors:")
        for c in top:
            emit(f"    #{c['rank']} {c['name']} ({c['sov_pct']:.0f}% SoV)")
            emit(f"       {_signal_bits(c)}")
        n_more = block.get("n_more_competitors", 0)
        if n_more:
            emit(f"    ...and {n_more} more.")
        leaders = block.get("thought_leaders", [])
        if leaders:
            names = ", ".join(
                f"{t['name']}" + (f" (promoted by {t['promoted_by']})" if t.get("promoted_by") else "")
                for t in leaders
            )
            emit(f"  Thought-leaders: {names}")
        emit()

    rivals = combined.get("cross_theme_rivals", [])
    emit("CROSS-THEME RIVALS (appearing in 2+ tracked entries):")
    if rivals:
        for r in rivals:
            emit(f"  {r['name']} - {r['n_keywords']} entries: {', '.join(r['keywords'])}")
    else:
        emit("  None (no advertiser spans more than one entry).")
    emit()
    emit("NEXT: rewrite cross_keyword_summary, each entry's where_you_can_win /")
    emit("      what_to_watch, and each shown competitor's read in report_data.json,")
    emit(f"      then run:  python3 {__file__} --render {json_path}")


# ── CLI orchestration ─────────────────────────────────────────────────────────

def _load_dotenv_if_present() -> None:
    """Load a local ``.env`` when python-dotenv is available."""
    try:
        from dotenv import load_dotenv
    except Exception:
        return
    load_dotenv()


def make_client() -> "ZenABMClient":
    """Build a ZenABMClient reading ZENABM_TOKEN from the env.

    ``core.zenabm_api`` (which needs ``requests``) is imported lazily here so
    that ``--render`` mode never pulls in the third-party deps.
    """
    from core.zenabm_api import ZenABMClient
    return ZenABMClient()


def _upsell_message(error: Exception) -> str:
    """Warm, subtle upsell for auth/plan errors -- no hard-cap language."""
    status = getattr(error, "status", None)
    if status == 401:
        return (
            "It looks like your ZenABM access has lapsed. "
            "Reconnect or grab a fresh API key at https://app.zenabm.com -- "
            "your competitor data will be waiting."
        )
    return (
        "Your current ZenABM plan does not include this feature right now. "
        "Head to https://app.zenabm.com to explore what is available -- "
        "it is worth a look."
    )


def _fetch_with_rate_limit_retry(
    fetch_fn: Callable[[], Any],
    label: str,
    *,
    emit: Callable[[str], None],
) -> "tuple[Any, bool]":
    """Call ``fetch_fn()`` once; on 429 sleep and retry once.

    Returns ``(result, rate_limited)`` where ``rate_limited`` is True only when
    the retry also returned 429 (caller should surface an incomplete-data note).
    On any other exception the caller handles it.  ``ZenABMAuthError`` /
    ``ZenABMPlanError`` are never caught here — they propagate to the caller.
    """
    from core.zenabm_api import ZenABMRateLimit

    try:
        return fetch_fn(), False
    except ZenABMRateLimit:
        emit(
            f"Rate limit hit for '{label}'; waiting {_RATE_LIMIT_RETRY_SECONDS}s then retrying..."
        )
        _SLEEP(_RATE_LIMIT_RETRY_SECONDS)
        try:
            return fetch_fn(), False
        except ZenABMRateLimit:
            # Still rate-limited after retry — surface as incomplete, not empty.
            return None, True


def _rate_limited_block(label: str, generated_at: str, *, is_competitor: bool) -> Dict[str, Any]:
    """An empty block annotated as rate-limited so it is never read as 'not advertising'."""
    block = _empty_block(label, generated_at, is_competitor=is_competitor)
    block["rate_limited"] = True
    block["method_note"] = (
        "Results may be incomplete - the ZenABM rate limit was reached for this entry "
        "and the retry also hit the limit. "
        "This does not mean the company is not advertising; try again shortly."
    )
    return block


def run(
    competitors: List[str],
    keywords: List[str],
    *,
    client: Any,
    out_dir: str,
    now_ms: int,
    generated_at: str,
    stdout: Any = sys.stdout,
) -> Dict[str, Any]:
    """Compute mode: scan each competitor and keyword, build the COMBINED object.

    For each competitor: ``client.search_by_advertiser(company=<value>, limit=100)``.
    For each keyword: ``client.search_by_keyword(keyword=<value>, limit=100)``.

    Writes ``report_data.json`` and a draft ``report.html`` into ``out_dir``,
    prints the DIGEST, and returns the combined dict. Never crashes on zero ads.

    Rate limits (429): a single sleep-and-retry is attempted per entry.  If the
    retry also 429s the block is flagged ``rate_limited: True`` with an honest
    note — never rendered as "not advertising".
    """
    from core.zenabm_api import ZenABMAuthError, ZenABMPlanError

    def emit(line: str = "") -> None:
        print(line, file=stdout)

    os.makedirs(out_dir, exist_ok=True)
    blocks: List[Dict[str, Any]] = []

    # ── Competitor blocks ──
    for comp_input in competitors:
        try:
            result, was_rate_limited = _fetch_with_rate_limit_retry(
                lambda c=comp_input: client.search_by_advertiser(
                    company=c, limit=_SCAN_LIMIT
                ),
                comp_input,
                emit=emit,
            )
        except (ZenABMAuthError, ZenABMPlanError) as exc:
            emit(_upsell_message(exc))
            combined = build_combined_report_data(blocks, generated_at=generated_at)
            _write_outputs(combined, out_dir, now_ms, generated_at, stdout)
            return combined
        except Exception as exc:
            emit(f"Warning: could not fetch competitor '{comp_input}': {exc}")
            blocks.append(_empty_block(comp_input, generated_at, is_competitor=True))
            continue

        if was_rate_limited:
            emit(f"Warning: rate limit persisted for '{comp_input}' — results may be incomplete.")
            blocks.append(_rate_limited_block(comp_input, generated_at, is_competitor=True))
            continue

        # Confirm matched advertiser or warn on empty numeric-id URL.
        matched_name = comp_input
        if result.advertisers:
            matched_name = result.advertisers[0].name
        elif _is_numeric_id_url(comp_input):
            emit(
                f"No results for numeric-id URL '{comp_input}'. "
                "Numeric company IDs may not resolve -- try using the company name "
                "or vanity slug (e.g. 'Personio' or 'linkedin.com/company/personio')."
            )
            blocks.append(_empty_block(comp_input, generated_at, is_competitor=True))
            continue

        ads = result.ads
        if not ads:
            blocks.append(_empty_block(matched_name, generated_at, is_competitor=True))
        else:
            blocks.append(build_block(
                matched_name,
                ads,
                now_ms=now_ms,
                generated_at=generated_at,
                is_competitor=True,
            ))

    # ── Keyword discovery blocks ──
    for keyword in keywords:
        try:
            result, was_rate_limited = _fetch_with_rate_limit_retry(
                lambda kw=keyword: client.search_by_keyword(keyword=kw, limit=_SCAN_LIMIT),
                keyword,
                emit=emit,
            )
        except (ZenABMAuthError, ZenABMPlanError) as exc:
            emit(_upsell_message(exc))
            combined = build_combined_report_data(blocks, generated_at=generated_at)
            _write_outputs(combined, out_dir, now_ms, generated_at, stdout)
            return combined
        except Exception as exc:
            emit(f"Warning: could not fetch keyword '{keyword}': {exc}")
            blocks.append(_empty_block(keyword, generated_at, is_competitor=False))
            continue

        if was_rate_limited:
            emit(f"Warning: rate limit persisted for keyword '{keyword}' — results may be incomplete.")
            blocks.append(_rate_limited_block(keyword, generated_at, is_competitor=False))
            continue

        ads = result.ads
        if not ads:
            blocks.append(_empty_block(keyword, generated_at, is_competitor=False))
        else:
            blocks.append(build_block(
                keyword,
                ads,
                now_ms=now_ms,
                generated_at=generated_at,
                is_competitor=False,
            ))

    combined = build_combined_report_data(blocks, generated_at=generated_at)

    # ── Own-data probe (Task B3) ──
    # Attempt to fetch own LinkedIn metrics + creatives for the last 30 days.
    # On success with non-empty data, build the you-vs-them comparison.
    # On auth/plan error, attach a warm upsell note (no hard-cap language).
    # On all-zero data (not connected), silently skip.
    _attach_comparison(combined, client=client, blocks=blocks, now_ms=now_ms)

    _write_outputs(combined, out_dir, now_ms, generated_at, stdout)
    return combined


def _write_outputs(
    combined: Dict[str, Any],
    out_dir: str,
    now_ms: int,
    generated_at: str,
    stdout: Any,
) -> None:
    """Write report_data.json + draft report.html and print the digest."""
    json_path = os.path.join(out_dir, "report_data.json")
    html_path = os.path.join(out_dir, "report.html")
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(combined, fh, indent=2, ensure_ascii=False)
    write_combined_report(combined, html_path)
    print_digest(
        combined,
        out_dir=out_dir,
        json_path=json_path,
        html_path=html_path,
        stdout=stdout,
    )


def _make_json_serializable(obj: Any) -> Any:
    """Recursively convert sets to sorted lists so the dict is JSON-safe."""
    if isinstance(obj, set):
        return sorted(str(x) for x in obj)
    if isinstance(obj, dict):
        return {k: _make_json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_make_json_serializable(v) for v in obj]
    return obj


def _date_window_30d(now_ms: int) -> "tuple[str, str]":
    """Return (start_date, end_date) strings for the last 30 days.

    ``now_ms`` is epoch milliseconds.  Returns ISO date strings
    (``YYYY-MM-DD``) so the caller never reads the clock directly.
    """
    import datetime
    end_dt = datetime.datetime.utcfromtimestamp(now_ms / 1000).date()
    start_dt = end_dt - datetime.timedelta(days=30)
    return start_dt.isoformat(), end_dt.isoformat()


def _all_competitor_profiles(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Collect every competitor profile from all blocks into one flat list."""
    profiles: List[Dict[str, Any]] = []
    for block in blocks:
        for c in (block.get("competitors") or []):
            profiles.append(c)
    return profiles


def _metrics_is_empty(metrics: Any) -> bool:
    """Return True when own metrics are all zeros (LinkedIn not connected)."""
    return (
        getattr(metrics, "impressions", 0) == 0
        and getattr(metrics, "clicks", 0) == 0
        and getattr(metrics, "cost_in_usd", 0.0) == 0.0
    )


def _attach_comparison(
    combined: Dict[str, Any],
    *,
    client: Any,
    blocks: List[Dict[str, Any]],
    now_ms: int,
) -> None:
    """Probe own LinkedIn data and attach a comparison dict (mutates combined).

    Tries ``client.linkedin_metrics`` for the last 30 days.  Three outcomes:

    1. Success with non-empty data: fetch own creatives, call
       ``build_comparison``, attach result to ``combined["comparison"]``.
    2. ``ZenABMAuthError`` or ``ZenABMPlanError``: set
       ``combined["comparison_upsell"]`` with a warm one-liner; no comparison.
    3. Success but all-zero metrics (not connected): silently skip; no
       comparison, no upsell.

    Never raises; failures are silently absorbed to keep the competitor
    report intact.
    """
    try:
        from core.zenabm_api import ZenABMAuthError, ZenABMPlanError
        from core.comparison import build_comparison
    except ImportError:
        # comparison module not available (pre-vendor state); skip gracefully
        return

    start_date, end_date = _date_window_30d(now_ms)

    try:
        metrics = client.linkedin_metrics(start_date, end_date)
    except (ZenABMAuthError, ZenABMPlanError):
        combined["comparison_upsell"] = (
            "Connect your LinkedIn ads in ZenABM to see how you stack up against the field."
        )
        return
    except Exception:
        # Any other error (network, unexpected): skip silently
        return

    if _metrics_is_empty(metrics):
        # Not connected or no ad spend in the window - skip without upsell
        return

    # Fetch own creatives (first page is enough).
    try:
        own_creatives, _ = client.list_creatives(page_size=100)
    except Exception:
        own_creatives = []

    # Gather all competitor profiles across all blocks.
    all_profiles = _all_competitor_profiles(blocks)

    try:
        comparison = build_comparison(metrics, own_creatives, all_profiles, now_ms)
    except Exception:
        # Build failure: skip silently (golden rule - never crash the main report)
        return

    # Ensure the comparison dict is JSON-serializable (sets -> sorted lists).
    combined["comparison"] = _make_json_serializable(comparison)


def render(json_path: str, *, out_path: Optional[str] = None, stdout: Any = sys.stdout) -> str:
    """Render mode: bake Zena's authored insights into the final combined report."""

    def emit(line: str = "") -> None:
        print(line, file=stdout)

    with open(json_path, encoding="utf-8") as fh:
        data = json.load(fh)

    if not isinstance(data, dict):
        raise ValueError(f"{json_path}: expected a JSON object at the top level.")
    keywords = data.get("keywords")
    if not isinstance(keywords, list) or not keywords:
        raise ValueError(
            f"{json_path}: 'keywords' must be a non-empty list of per-block entries."
        )
    for i, kw in enumerate(keywords):
        if not isinstance(kw, dict) or "keyword" not in kw:
            raise ValueError(
                f"{json_path}: keywords[{i}] is not a valid block (missing 'keyword')."
            )
        kw.setdefault("competitors", [])

    if out_path is None:
        out_path = os.path.join(os.path.dirname(os.path.abspath(json_path)), "report.html")

    build_combined_report_html(data)  # validates render without error
    write_combined_report(data, out_path)
    emit(f"Rendered final combined report: {out_path}")
    return out_path


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="competitor_scan",
        description=(
            "ABM competitor scan. Compute mode scans competitors and keywords "
            "via the ZenABM API and writes report_data.json + a draft report.html; "
            "render mode bakes Zena's authored insights into the final report."
        ),
    )
    p.add_argument(
        "--competitors",
        help='Comma-separated competitor names / URLs, e.g. "Personio, linkedin.com/company/notion".',
    )
    p.add_argument(
        "--keywords",
        help='Comma-separated discovery keywords, e.g. "product analytics,data warehouse".',
    )
    p.add_argument(
        "--out-dir",
        default=".",
        help="Directory to write report_data.json + report.html (default: .).",
    )
    p.add_argument(
        "--render",
        metavar="REPORT_DATA_JSON",
        help="Render mode: bake insights from this report_data.json into the final report.",
    )
    p.add_argument(
        "--out",
        help="Render mode: output HTML path (default: report.html next to the JSON).",
    )
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    _load_dotenv_if_present()

    # ── Render mode ──
    if args.render:
        try:
            render(args.render, out_path=args.out)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"Render failed: {exc}", file=sys.stderr)
            return 2
        return 0

    # ── Compute mode ──
    competitors = _parse_list(args.competitors or "")
    keywords = _parse_list(args.keywords or "")

    if not competitors and not keywords:
        print(
            "No competitors or keywords given. Use --competitors and/or --keywords "
            "(compute mode) or --render report_data.json (render mode).",
            file=sys.stderr,
        )
        return 2

    now_ms = int(time.time() * 1000)
    generated_at = time.strftime("%Y-%m-%d", time.gmtime(now_ms / 1000))

    client = make_client()

    run(
        competitors,
        keywords,
        client=client,
        out_dir=args.out_dir,
        now_ms=now_ms,
        generated_at=generated_at,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

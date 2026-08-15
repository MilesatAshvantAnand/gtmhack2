"""Inferable-signals toolkit (Layer 2 shared toolkit).

Pure functions that derive the signals documented in
``docs/api-knowledge-base/inferable-signals.md`` from the pydantic models in
``core.schema``. That markdown file is the authoritative spec — every formula,
prerequisite tier, and failure case below is implemented exactly as documented
there. When in doubt, read the spec, not this file.

Design rules (all enforced):
  * **Pure.** No I/O, no network, no global clock. Every time-based function
    takes an explicit ``now_ms: int`` argument (epoch milliseconds).
  * **Tier system.** Every signal is tagged N / S / T (see the spec's
    "Signal dependency graph"):
        - Tier N: needs only ``details.type`` / ``details.advertiser``
          (works for 100% of ads).
        - Tier S: needs ``details.adStatistics`` (EU/EEA-visible ads only).
        - Tier T: needs non-empty ``details.adTargeting``.
  * **THE GOLDEN RULE.** Impression stats exist only for EU/EEA-visible ads.
    ``impression_data_coverage`` (full / partial / none) gates all Tier S and
    Tier T signals. When coverage is ``none`` — or a given ad lacks
    ``adStatistics`` / has empty ``adTargeting`` — the signal value is
    **UNKNOWN → return ``None``, never ``False`` and never a computed number.**
    This is the single most important correctness property in this module.

All functions are type-hinted; ``Optional[...]`` is used wherever a signal can
be unknown.
"""
from __future__ import annotations

import re
import statistics
from collections import Counter, defaultdict
from typing import Dict, List, Literal, Optional, Sequence

from core.schema import AdElement

# ── Constants ──────────────────────────────────────────────────────────────

DAY_MS: int = 86_400_000  # milliseconds in one day

Coverage = Literal["full", "partial", "none"]
AdvertiserType = Literal["company", "individual", "unknown"]
CampaignSizeTier = Literal["micro", "small", "medium", "large", "enterprise"]
RangeConfidence = Literal["tight", "medium", "wide", "no_data"]
FunnelStage = Literal["awareness", "consideration", "conversion", "mixed"]

# Legal-entity suffix regex (validated on the corpus — see F1b in the spec).
_LEGAL_SUFFIX_RE = re.compile(
    r"[,\s]+("
    r"Inc\.?|LLC|Ltd\.?|Corp\.?|GmbH|SE(\s*&\s*Co\.?\s*KG)?|Limited|B\.V\.|"
    r"Pty\.?\s*Ltd\.?|S\.A\.|N\.V\.|PLC|AG|A/S|Sp\.\s*z\s*o\.o\.|Group|"
    r"Holdings?"
    r")\s*$",
    flags=re.IGNORECASE,
)

# Ad-format scoring weights for linkedin_maturity_score (WE5).
# Types used for the format-presence helpers (uses_video etc.).
_VIDEO_TYPES = {"SPONSORED_VIDEO"}
_CAROUSEL_TYPES = {"SPONSORED_UPDATE_CAROUSEL"}
_DOCUMENT_TYPES = {"SPONSORED_UPDATE_NATIVE_DOCUMENT"}
_MESSAGE_TYPES = {"SPONSORED_MESSAGE", "SPONSORED_INMAILS"}


# ── Internal helpers ───────────────────────────────────────────────────────

def _ads_with_stats(ads: Sequence[AdElement]) -> List[AdElement]:
    """Return only the ads that carry ``details.adStatistics`` (Tier S)."""
    return [a for a in ads if a.details.adStatistics is not None]


def _ads_with_targeting(ads: Sequence[AdElement]) -> List[AdElement]:
    """Return only the ads with non-empty ``details.adTargeting`` (Tier T)."""
    return [a for a in ads if a.details.adTargeting]


def _strip_legal_suffix(name: str) -> str:
    """Strip common legal-entity suffixes and normalize for comparison."""
    prev = None
    out = name.strip()
    # Apply repeatedly to catch stacked suffixes (e.g. "Foo Group Ltd.").
    while out != prev:
        prev = out
        out = _LEGAL_SUFFIX_RE.sub("", out).strip()
    return out.strip().casefold()


def _midpoint(ad: AdElement) -> Optional[float]:
    """Per-ad impressions midpoint, or None if the ad has no stats."""
    st = ad.details.adStatistics
    if st is None:
        return None
    return (st.totalImpressions.from_ + st.totalImpressions.to) / 2


def _type_counts(ads: Sequence[AdElement]) -> Counter:
    return Counter(a.details.type for a in ads)


# ════════════════════════════════════════════════════════════════════════════
# Tier N — works for 100% of ads (needs only details.type / details.advertiser)
# ════════════════════════════════════════════════════════════════════════════

def linkedin_company_id(ad: AdElement) -> Optional[str]:
    """F2 (Tier N). Numeric LinkedIn company id from ``advertiserUrl``.

    Parses ``/company/(\\d+)``. Returns None for individual (``/in/``)
    advertisers — the safest canonical identifier LinkedIn exposes.
    """
    m = re.search(r"/company/(\d+)", ad.details.advertiser.advertiserUrl)
    return m.group(1) if m else None


def ad_id(ad: AdElement) -> Optional[str]:
    """WE13 (Tier N). Numeric ad id from ``adUrl`` (``/detail/(\\d+)``)."""
    m = re.search(r"/detail/(\d+)", ad.adUrl)
    return m.group(1) if m else None


def advertiser_type(ad: AdElement) -> AdvertiserType:
    """F4 (Tier N). Classify advertiser as company | individual | unknown.

    ``/company/`` → company (dominant case), ``/in/`` → individual (thought
    leaders running sponsored posts), else unknown.
    """
    url = ad.details.advertiser.advertiserUrl
    if re.search(r"/company/\d+", url):
        return "company"
    if "/in/" in url:
        return "individual"
    return "unknown"


def ad_types_used(ads: Sequence[AdElement]) -> List[str]:
    """B1 (Tier N). Sorted unique ``details.type`` values across all ads."""
    return sorted({a.details.type for a in ads})


def linkedin_maturity_score(ads: Sequence[AdElement]) -> int:
    """B2 / WE5 (Tier N). 0–10 ad-format sophistication score.

    Weighted by the set of distinct types used (see WE5 rubric), capped at 10.
    """
    types_used = {a.details.type for a in ads}
    score = 0
    if "SPONSORED_STATUS_UPDATE" in types_used:
        score += 1
    if "SPONSORED_VIDEO" in types_used:
        score += 2
    if "SPONSORED_UPDATE_CAROUSEL" in types_used:
        score += 2
    if "SPONSORED_UPDATE_NATIVE_DOCUMENT" in types_used:
        score += 2
    if "SPONSORED_INMAILS" in types_used or "SPONSORED_MESSAGE" in types_used:
        score += 1
    if "SPOTLIGHT_V2" in types_used:
        score += 3
    return min(score, 10)


def ad_payer_differs_normalized(ad: AdElement) -> bool:
    """F1b / WE4 (Tier N). True when the payer differs from the advertiser
    name *after* stripping legal-entity suffixes.

    "Personio SE & Co. KG" vs "Personio" → same after stripping → False.
    "WeWork" vs a genuinely different parent LLC → True.

    When ``adPayer`` is absent (rare — 0.2% of ads) we treat the payer as the
    advertiser name (i.e. does not differ).
    """
    adv = ad.details.advertiser
    payer = adv.adPayer
    if payer is None:
        return False
    return _strip_legal_suffix(adv.advertiserName) != _strip_legal_suffix(payer)


def uses_video(ads: Sequence[AdElement]) -> bool:
    """B4 (Tier N). Any ad uses a video format."""
    return any(a.details.type in _VIDEO_TYPES for a in ads)


def uses_carousel(ads: Sequence[AdElement]) -> bool:
    """B4 (Tier N). Any ad uses a carousel format."""
    return any(a.details.type in _CAROUSEL_TYPES for a in ads)


def uses_document(ads: Sequence[AdElement]) -> bool:
    """B4 (Tier N). Any ad uses a native-document format."""
    return any(a.details.type in _DOCUMENT_TYPES for a in ads)


def uses_message(ads: Sequence[AdElement]) -> bool:
    """B4 (Tier N). Any ad uses a message/InMail format."""
    return any(a.details.type in _MESSAGE_TYPES for a in ads)


# ════════════════════════════════════════════════════════════════════════════
# Tier N gate — impression_data_coverage classifies whether S/T signals are
# trustworthy. THIS IS THE GATE for THE GOLDEN RULE.
# ════════════════════════════════════════════════════════════════════════════

def impression_data_coverage(ads: Sequence[AdElement]) -> Coverage:
    """D1 / WE2 (Tier N). Classify EU-visibility of an advertiser's activity.

    ``full`` if >= 80% of ads carry ``adStatistics``, ``partial`` if
    20% <= pct < 80%, else ``none``. An empty input set is ``none`` (nothing
    to infer from). Every Tier S / T signal must gate on this: when it returns
    ``none`` those signals degrade to UNKNOWN (None), never False.
    """
    n_total = len(ads)
    if n_total == 0:
        return "none"
    n_with_stats = len(_ads_with_stats(ads))
    pct = n_with_stats / n_total * 100
    if pct >= 80:
        return "full"
    if pct >= 20:
        return "partial"
    return "none"


# ════════════════════════════════════════════════════════════════════════════
# Tier S — needs details.adStatistics. Company-level signals gate on
# impression_data_coverage != "none"; per-ad signals return None when the ad
# has no stats.
# ════════════════════════════════════════════════════════════════════════════

def impressions_midpoint(ad: AdElement) -> Optional[int]:
    """C1 / WE12 (Tier S, per-ad). ``(from + to) / 2`` or None if no stats.

    Never present a single number without acknowledging the bucket width — see
    ``impression_range_confidence``.
    """
    mid = _midpoint(ad)
    return None if mid is None else int(mid)


def impression_range_confidence(ad: AdElement) -> RangeConfidence:
    """C2 (Tier S, per-ad). How much to trust ``impressions_midpoint``.

    ``no_data`` if no stats; ``tight`` if bucket width <= 5k; ``medium`` if
    <= 50k; ``wide`` otherwise.
    """
    st = ad.details.adStatistics
    if st is None:
        return "no_data"
    width = st.totalImpressions.to - st.totalImpressions.from_
    if width <= 5_000:
        return "tight"
    if width <= 50_000:
        return "medium"
    return "wide"


def campaign_size_tier(ad: AdElement) -> Optional[CampaignSizeTier]:
    """C4 / WE12 (Tier S, per-ad). Tier from the ad's impressions midpoint.

    micro < 5k, small < 30k, medium < 150k, large < 500k, enterprise >= 500k.
    Returns None when the ad has no stats (UNKNOWN).
    """
    mid = _midpoint(ad)
    if mid is None:
        return None
    if mid < 5_000:
        return "micro"
    if mid < 30_000:
        return "small"
    if mid < 150_000:
        return "medium"
    if mid < 500_000:
        return "large"
    return "enterprise"


def campaign_duration_days(ad: AdElement) -> Optional[float]:
    """H1 / WE9 (Tier S, per-ad). ``(latest - first) / DAY_MS`` or None."""
    st = ad.details.adStatistics
    if st is None:
        return None
    return (st.latestImpressionAt - st.firstImpressionAt) / DAY_MS


def active_ads_within(
    ads: Sequence[AdElement], now_ms: int, days: int
) -> Optional[int]:
    """C5 / WE10 (Tier S). Count of ads with ``latestImpressionAt`` within the
    last ``days`` days.

    Gated on coverage: returns None (UNKNOWN) when coverage is ``none``.
    """
    if impression_data_coverage(ads) == "none":
        return None
    cutoff = now_ms - days * DAY_MS
    return sum(
        1
        for a in _ads_with_stats(ads)
        if a.details.adStatistics.latestImpressionAt >= cutoff  # type: ignore[union-attr]
    )


def is_currently_advertising(
    ads: Sequence[AdElement], now_ms: int
) -> Optional[bool]:
    """A2 / WE8 (Tier S). Any ad had impressions in the last 30 days.

    Gated: None (UNKNOWN) when coverage is ``none`` — a ``False`` there would
    be a false-negative for US-only advertisers whose EU-visible slice is stale.
    """
    if impression_data_coverage(ads) == "none":
        return None
    cutoff = now_ms - 30 * DAY_MS
    return any(
        a.details.adStatistics.latestImpressionAt >= cutoff  # type: ignore[union-attr]
        for a in _ads_with_stats(ads)
    )


def is_new_advertiser(ads: Sequence[AdElement], now_ms: int) -> Optional[bool]:
    """A3 / WE8 (Tier S). All ads' earliest impression is within the last
    90 days (i.e. ``min(firstImpressionAt) >= now - 90d``).

    Gated: None (UNKNOWN) when coverage is ``none``.
    """
    if impression_data_coverage(ads) == "none":
        return None
    firsts = [
        a.details.adStatistics.firstImpressionAt  # type: ignore[union-attr]
        for a in _ads_with_stats(ads)
    ]
    if not firsts:
        return None
    return min(firsts) >= now_ms - 90 * DAY_MS


def is_ramping_up(ads: Sequence[AdElement], now_ms: int) -> Optional[bool]:
    """A5 / WE8 (Tier S). >= 20% of ads started in the last 30 days.

    Gated: None (UNKNOWN) when coverage is ``none``.
    """
    if impression_data_coverage(ads) == "none":
        return None
    firsts = [
        a.details.adStatistics.firstImpressionAt  # type: ignore[union-attr]
        for a in _ads_with_stats(ads)
    ]
    if not firsts:
        return None
    cutoff = now_ms - 30 * DAY_MS
    new_ads = sum(1 for f in firsts if f >= cutoff)
    return new_ads / len(firsts) >= 0.20


def is_dark_period(ads: Sequence[AdElement], now_ms: int) -> Optional[bool]:
    """A4 / WE8 (Tier S). Was active, went quiet 30+ days ago.

    ``max(latestImpressionAt) < now - 30d`` AND coverage != none. The coverage
    gate is what prevents false positives on US-only advertisers whose
    EU-visible ads are stale but who are still active in the US. Returns None
    (UNKNOWN) when coverage is ``none``.
    """
    if impression_data_coverage(ads) == "none":
        return None
    latests = [
        a.details.adStatistics.latestImpressionAt  # type: ignore[union-attr]
        for a in _ads_with_stats(ads)
    ]
    if not latests:
        return None
    return max(latests) < now_ms - 30 * DAY_MS


def outreach_timing_score(
    ads: Sequence[AdElement], now_ms: int
) -> Optional[int]:
    """A6 / WE3 (Tier S). Composite 0–8 "how good a moment to reach out."

    ``+3 is_ramping_up, +2 is_new_advertiser, +2 is_dark_period,
    +1 is_currently_advertising``. Inherits the failure modes of its
    components, so it is only meaningful when coverage != none — returns None
    (UNKNOWN) otherwise.
    """
    if impression_data_coverage(ads) == "none":
        return None
    ramp = is_ramping_up(ads, now_ms)
    new = is_new_advertiser(ads, now_ms)
    dark = is_dark_period(ads, now_ms)
    curr = is_currently_advertising(ads, now_ms)
    score = 0
    if ramp:
        score += 3
    if new:
        score += 2
    if dark:
        score += 2
    if curr:
        score += 1
    return score


def total_impressions_est(
    ads: Sequence[AdElement],
) -> Optional[Dict[str, float]]:
    """C3 / WE12 (Tier S). Company-level impression estimate.

    Sum of per-ad bounds across all EU-visible ads → dict with keys
    ``lower`` / ``upper`` / ``midpoint``. Never present the midpoint alone —
    the bounds tell the reader what's real vs estimated. Gated: None (UNKNOWN)
    when coverage is ``none``.
    """
    if impression_data_coverage(ads) == "none":
        return None
    stats = _ads_with_stats(ads)
    if not stats:
        return None
    lower = sum(a.details.adStatistics.totalImpressions.from_ for a in stats)  # type: ignore[union-attr]
    upper = sum(a.details.adStatistics.totalImpressions.to for a in stats)  # type: ignore[union-attr]
    return {"lower": lower, "upper": upper, "midpoint": (lower + upper) / 2}


def eu_impressions_share_of_total(ad: AdElement) -> Optional[float]:
    """D7 / WE7 (Tier S, per-ad). Sum of the ad's country impression
    percentages — the EU/EEA-disclosed share of the ad's *total* impressions.

    DO NOT renormalize. A sum well below 100 means the rest of the ad's
    impressions were non-EU/EEA and therefore not disclosed per DSA rules.
    Returns None when the ad has no stats.
    """
    st = ad.details.adStatistics
    if st is None:
        return None
    return sum(e.impressionPercentage for e in st.impressionsDistributionByCountry)


# ════════════════════════════════════════════════════════════════════════════
# Tier T — needs non-empty details.adTargeting. Gated on coverage != none.
# ════════════════════════════════════════════════════════════════════════════

def _any_facet(
    ads: Sequence[AdElement], facet_name: str, *, included: bool = True
) -> bool:
    for a in _ads_with_targeting(ads):
        for f in a.details.adTargeting:
            if f.facetName == facet_name and (f.isIncluded if included else True):
                return True
    return False


def uses_retargeting(ads: Sequence[AdElement]) -> Optional[bool]:
    """B5 / E3 (Tier T). Any ad uses the ``Audience`` facet (retargeting /
    custom / lookalike proxy).

    Gated: None (UNKNOWN) when coverage is ``none`` — for US-only advertisers
    targeting is invisible, so the signal is unknown, not False.
    """
    if impression_data_coverage(ads) == "none":
        return None
    return _any_facet(ads, "Audience")


def targets_job_roles(ads: Sequence[AdElement]) -> Optional[bool]:
    """E1 (Tier T). Any ad targets the ``Job`` facet with ``isIncluded``.

    Gated: None (UNKNOWN) when coverage is ``none``.
    """
    if impression_data_coverage(ads) == "none":
        return None
    return _any_facet(ads, "Job")


def targets_specific_companies(ads: Sequence[AdElement]) -> Optional[bool]:
    """E2 / WE6 (Tier T). ABM signal — any ad targets the ``Company`` facet
    with ``isIncluded``.

    Gated: None (UNKNOWN) when coverage is ``none``.
    """
    if impression_data_coverage(ads) == "none":
        return None
    return _any_facet(ads, "Company")


def funnel_stage(ads: Sequence[AdElement]) -> Optional[FunnelStage]:
    """B3 / WE11 (Tier N + T). Classify awareness | consideration | conversion
    | mixed from the type distribution plus the retargeting (Audience) facet.

    The retargeting piece is Tier T, so the whole signal is gated: returns None
    (UNKNOWN) when coverage is ``none`` rather than defaulting to awareness.
    """
    if impression_data_coverage(ads) == "none":
        return None
    if not ads:
        return None
    counts = _type_counts(ads)
    n = sum(counts.values())

    def share(t: str) -> float:
        return counts.get(t, 0) / n if n else 0.0

    video_share = share("SPONSORED_VIDEO")
    carousel_share = share("SPONSORED_UPDATE_CAROUSEL")
    document_share = share("SPONSORED_UPDATE_NATIVE_DOCUMENT")
    message_share = share("SPONSORED_MESSAGE") + share("SPONSORED_INMAILS")
    retargeting = bool(uses_retargeting(ads))

    if video_share > 0.5 and not retargeting:
        return "awareness"
    if document_share > 0.3 or message_share > 0.2:
        return "conversion"
    if retargeting or carousel_share > 0.3:
        return "consideration"
    return "mixed"


# ════════════════════════════════════════════════════════════════════════════
# Geo — Tier S. Impression-weighted country share and primary market.
# ════════════════════════════════════════════════════════════════════════════

def country_impression_share_pct(
    ads: Sequence[AdElement],
) -> Optional[Dict[str, float]]:
    """D2 / WE1 (Tier S). Impression-weighted per-country share (percent).

    For each ad: ``mid = (from + to) / 2``; contribution to country ``c`` is
    ``mid * (impressionPercentage_c / 100)``. Sum across ads, then normalize to
    percentages. Describes the EU-visible portion only — do NOT equate with the
    "true target market" for non-EU advertisers. Gated: None (UNKNOWN) when
    coverage is ``none``.
    """
    if impression_data_coverage(ads) == "none":
        return None
    weighted: Dict[str, float] = defaultdict(float)
    for a in _ads_with_stats(ads):
        st = a.details.adStatistics
        assert st is not None
        mid = (st.totalImpressions.from_ + st.totalImpressions.to) / 2
        for entry in st.impressionsDistributionByCountry:
            code = entry.country.replace("urn:li:country:", "").upper()
            weighted[code] += mid * (entry.impressionPercentage / 100)
    total = sum(weighted.values())
    if total <= 0:
        return None
    return {code: v / total * 100 for code, v in weighted.items()}


def primary_market_country(
    ads: Sequence[AdElement],
) -> Optional[Dict[str, object]]:
    """D3 / WE1 (Tier S). Argmax of ``country_impression_share_pct``, with a
    coverage-dependent caveat.

    * coverage ``full``  → definitive primary market (``caveat: None``).
    * coverage ``partial`` → primary market of the EU-visible subset only
      (``caveat: "eu_visible_only"``). Real primary market may differ.
    * coverage ``none``  → no inference possible → returns None.

    Return shape: ``{"country": <ISO2>, "share_pct": <float>, "caveat": <str|None>}``.
    """
    coverage = impression_data_coverage(ads)
    if coverage == "none":
        return None
    shares = country_impression_share_pct(ads)
    if not shares:
        return None
    country = max(shares, key=lambda c: shares[c])
    caveat = None if coverage == "full" else "eu_visible_only"
    return {"country": country, "share_pct": shares[country], "caveat": caveat}


# ════════════════════════════════════════════════════════════════════════════
# Convenience — compute every signal with the coverage gate correctly applied.
# ════════════════════════════════════════════════════════════════════════════

def compute_company_signals(
    ads: Sequence[AdElement],
    now_ms: int,
    total_ads: Optional[int] = None,
) -> Dict[str, object]:
    """Compute all signals for an advertiser's ad set in one call.

    The coverage gate is applied throughout: Tier S / T entries are ``None``
    (UNKNOWN) when ``impression_data_coverage`` is ``none``. ``total_ads`` is
    the API-reported ``paging.total`` (A1) when known — it is passed through
    unchanged (may differ from ``len(ads)`` for keyword searches).

    Returns a flat dict keyed by signal name. Per-ad Tier S signals
    (midpoint / confidence / tier / duration / eu-share) are rolled up into
    per-ad lists so the caller can inspect distributions.
    """
    coverage = impression_data_coverage(ads)
    stats_ads = _ads_with_stats(ads)

    signals: Dict[str, object] = {
        # ── Tier N (always computable) ──
        "n_ads": len(ads),
        "total_ads": total_ads,
        "ad_types_used": ad_types_used(ads),
        "linkedin_maturity_score": linkedin_maturity_score(ads),
        "uses_video": uses_video(ads),
        "uses_carousel": uses_carousel(ads),
        "uses_document": uses_document(ads),
        "uses_message": uses_message(ads),
        "impression_data_coverage": coverage,
        # ── Tier S (company-level; each self-gates on coverage) ──
        "is_currently_advertising": is_currently_advertising(ads, now_ms),
        "is_new_advertiser": is_new_advertiser(ads, now_ms),
        "is_ramping_up": is_ramping_up(ads, now_ms),
        "is_dark_period": is_dark_period(ads, now_ms),
        "outreach_timing_score": outreach_timing_score(ads, now_ms),
        "active_ads_7d": active_ads_within(ads, now_ms, 7),
        "active_ads_30d": active_ads_within(ads, now_ms, 30),
        "active_ads_90d": active_ads_within(ads, now_ms, 90),
        "active_ads_180d": active_ads_within(ads, now_ms, 180),
        "total_impressions_est": total_impressions_est(ads),
        "country_impression_share_pct": country_impression_share_pct(ads),
        "primary_market_country": primary_market_country(ads),
        # ── Tier T (self-gate on coverage) ──
        "uses_retargeting": uses_retargeting(ads),
        "targets_job_roles": targets_job_roles(ads),
        "targets_specific_companies": targets_specific_companies(ads),
        "funnel_stage": funnel_stage(ads),
    }

    # Per-ad Tier S rollups — only meaningful when coverage != none; otherwise
    # UNKNOWN. Each per-ad value is itself None for ads without stats.
    if coverage == "none":
        signals["impressions_midpoint_per_ad"] = None
        signals["impression_range_confidence_per_ad"] = None
        signals["campaign_size_tier_per_ad"] = None
        signals["campaign_duration_days_per_ad"] = None
        signals["eu_impressions_share_of_total_per_ad"] = None
        signals["eu_disclosed_share_mean"] = None
    else:
        signals["impressions_midpoint_per_ad"] = [
            impressions_midpoint(a) for a in stats_ads
        ]
        signals["impression_range_confidence_per_ad"] = [
            impression_range_confidence(a) for a in stats_ads
        ]
        signals["campaign_size_tier_per_ad"] = [
            campaign_size_tier(a) for a in stats_ads
        ]
        signals["campaign_duration_days_per_ad"] = [
            campaign_duration_days(a) for a in stats_ads
        ]
        eu_shares = [eu_impressions_share_of_total(a) for a in stats_ads]
        signals["eu_impressions_share_of_total_per_ad"] = eu_shares
        clean = [s for s in eu_shares if s is not None]
        signals["eu_disclosed_share_mean"] = (
            statistics.mean(clean) if clean else None
        )

    return signals

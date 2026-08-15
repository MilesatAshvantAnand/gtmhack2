"""You-vs-them comparison logic — Task B2.

Pure functions only; no I/O, no clock reads (now_ms passed in).

The main entry point is ``build_comparison``, which takes own LinkedIn metrics,
own creatives, and a list of per-competitor profile dicts (as produced by
``core.signals.compute_company_signals`` wrapped in the entry script) and
returns a structured comparison dict.

Golden rule
-----------
A competitor with ``impression_data_coverage == "none"`` has UNKNOWN reach and
momentum. Never treat unknown as zero. Such competitors are still counted for
Tier N signals (ad counts, formats, SOV) but are **excluded** from any
reach/scale claims that depend on impression data.

Format normalization
--------------------
Own creatives carry human-readable ``format`` strings like "Single Image",
"Thought Leader Ad", "Video", "Carousel Ad".  Competitor profile ``formats``
dicts use snake_case keys like ``single_image``, ``video``, ``carousel``,
``document``, ``message``.  The normalizer converts both sides to a common
snake_case so comparisons are reliable.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Set

from core.zenabm_models import Creative, LinkedInMetrics


# ── Format normalization ───────────────────────────────────────────────────────

def _normalize_format(fmt: str) -> str:
    """Convert a human-readable or snake_case format string to canonical snake_case.

    Examples:
        "Single Image"      -> "single_image"
        "Thought Leader Ad" -> "thought_leader_ad"
        "Carousel Ad"       -> "carousel"
        "Video"             -> "video"
        "document"          -> "document"
        "single_image"      -> "single_image"
    """
    if not fmt:
        return ""
    # Lower, replace spaces/hyphens/dots with underscore
    s = fmt.strip().lower()
    s = re.sub(r"[\s\-\.]+", "_", s)
    # Collapse repeated underscores
    s = re.sub(r"_+", "_", s)
    # Strip trailing "_ad" or "_ads" suffix for common cases:
    # "carousel_ad" -> "carousel", "thought_leader_ad" -> "thought_leader"
    # BUT keep "single_image_ad" -> "single_image" (strip), "video_ad" -> "video"
    # We strip the trailing "_ad" suffix when it is redundant (i.e. the base is
    # already a recognized canonical name). Simpler: always strip "_ad" suffix.
    if s.endswith("_ad") and len(s) > 3:
        s = s[:-3]
    return s.strip("_")


def _own_format_set(creatives: List[Creative]) -> Set[str]:
    """Return the set of normalized format strings for all own creatives."""
    result: Set[str] = set()
    for c in creatives:
        if c.format:
            normalized = _normalize_format(c.format)
            if normalized:
                result.add(normalized)
    return result


def _competitor_format_set(profile: dict) -> Set[str]:
    """Return all formats a single competitor uses (already snake_case keys)."""
    formats: dict = profile.get("formats") or {}
    return {k for k, v in formats.items() if v and v > 0}


def _all_competitor_formats(profiles: List[dict]) -> Set[str]:
    """Union of all competitor format sets."""
    result: Set[str] = set()
    for p in profiles:
        result |= _competitor_format_set(p)
    return result


# ── Head-to-head: activity ─────────────────────────────────────────────────────

def _build_activity(
    own_creatives: List[Creative],
    profiles: List[dict],
) -> dict:
    """Compare own serving ad count vs competitors' ad counts.

    ``own_serving_ads`` = count of creatives with ``is_serving is True``.
    ``own_vs_field`` = "fewer" / "more" / "similar" relative to the mean
    competitor ad count on the keyword.  "similar" = within ±25% of the mean.
    """
    own_serving = sum(1 for c in own_creatives if c.is_serving is True)

    competitor_entries = [
        {"name": p["name"], "n_ads": p.get("n_ads_on_keyword", 0)}
        for p in profiles
    ]

    if not profiles:
        own_vs_field = "similar"
    else:
        competitor_counts = [p.get("n_ads_on_keyword", 0) for p in profiles]
        mean_competitor_ads = sum(competitor_counts) / len(competitor_counts)
        if mean_competitor_ads == 0:
            own_vs_field = "more" if own_serving > 0 else "similar"
        else:
            ratio = own_serving / mean_competitor_ads
            if ratio < 0.75:
                own_vs_field = "fewer"
            elif ratio > 1.25:
                own_vs_field = "more"
            else:
                own_vs_field = "similar"

    return {
        "own_serving_ads": own_serving,
        "competitors": competitor_entries,
        "own_vs_field": own_vs_field,
    }


# ── Head-to-head: formats ──────────────────────────────────────────────────────

def _build_formats(
    own_creatives: List[Creative],
    profiles: List[dict],
) -> dict:
    """Identify format gaps between own and competitor sets.

    Returns:
        own_formats: sorted list of own normalized format strings
        competitor_only_formats: formats competitors use that we don't
        own_only_formats: formats we use that no competitor uses
        per_competitor: per-competitor format details
    """
    own_fmts = _own_format_set(own_creatives)
    all_comp_fmts = _all_competitor_formats(profiles)

    competitor_only = sorted(all_comp_fmts - own_fmts)
    own_only = sorted(own_fmts - all_comp_fmts)

    per_competitor = [
        {
            "name": p["name"],
            "formats": _competitor_format_set(p),
            "gaps_vs_you": sorted(_competitor_format_set(p) - own_fmts),
            "coverage": p.get("impression_data_coverage", "none"),
        }
        for p in profiles
    ]

    return {
        "own_formats": sorted(own_fmts),
        "competitor_only_formats": competitor_only,
        "own_only_formats": own_only,
        "per_competitor": per_competitor,
    }


# ── Head-to-head: share of voice ──────────────────────────────────────────────

def _build_share_of_voice(
    own_creatives: List[Creative],
    profiles: List[dict],
) -> dict:
    """Approximate SOV position if own ads were in the combined field.

    Uses ad counts (Tier N — always available regardless of coverage) so the
    golden rule is never violated here.
    """
    own_serving = sum(1 for c in own_creatives if c.is_serving is True)
    field_total_ads = sum(p.get("n_ads_on_keyword", 0) for p in profiles)
    combined_total = own_serving + field_total_ads
    own_sov_pct = (own_serving / combined_total * 100) if combined_total > 0 else 0.0

    # Rank competitors by their reported SOV
    ranked = sorted(
        [{"name": p["name"], "sov_pct": p.get("sov_pct", 0.0)} for p in profiles],
        key=lambda x: x["sov_pct"],
        reverse=True,
    )

    return {
        "own_serving_ads": own_serving,
        "field_total_ads": field_total_ads,
        "own_sov_pct": round(own_sov_pct, 1),
        "competitor_sov_ranking": ranked,
    }


# ── Scale vs efficiency: competitor scale ─────────────────────────────────────

def _build_competitor_scale(profiles: List[dict]) -> dict:
    """Summarize competitor reach and activity.

    Golden rule: competitors with ``impression_data_coverage == "none"`` have
    UNKNOWN reach -- never treat as zero in reach sums.  Their ad counts are
    still counted.
    """
    if not profiles:
        return {
            "loudest_by_ads": None,
            "total_reach_low": None,
            "total_reach_high": None,
            "reach_eligible_competitors": [],
            "coverage_none_competitors": [],
        }

    # Tier N: loudest by ad count (all competitors counted)
    loudest = max(profiles, key=lambda p: p.get("n_ads_on_keyword", 0))
    loudest_by_ads = {"name": loudest["name"], "n_ads": loudest.get("n_ads_on_keyword", 0)}

    # Tier S gate: only count reach for competitors with coverage != "none"
    reach_eligible = [
        p for p in profiles
        if p.get("impression_data_coverage") != "none"
        and p.get("reach_low") is not None
    ]
    coverage_none = [
        p["name"] for p in profiles
        if p.get("impression_data_coverage") == "none"
    ]

    if reach_eligible:
        total_reach_low: Optional[int] = sum(p["reach_low"] for p in reach_eligible)
        total_reach_high: Optional[int] = sum(
            p.get("reach_high") or p["reach_low"] for p in reach_eligible
        )
        # Loudest by reach among eligible
        loudest_reach = max(reach_eligible, key=lambda p: p["reach_low"])
        loudest_by_reach: Optional[str] = loudest_reach["name"]
    else:
        # All coverage-none: reach is UNKNOWN, not zero
        total_reach_low = None
        total_reach_high = None
        loudest_by_reach = None

    return {
        "loudest_by_ads": loudest_by_ads,
        "loudest_by_reach": loudest_by_reach,
        "total_reach_low": total_reach_low,
        "total_reach_high": total_reach_high,
        "reach_eligible_competitors": [p["name"] for p in reach_eligible],
        "coverage_none_competitors": coverage_none,
    }


# ── Scale vs efficiency: your efficiency ─────────────────────────────────────

def _build_your_efficiency(own_metrics: LinkedInMetrics) -> dict:
    return {
        "ctr": own_metrics.ctr,
        "cpc": own_metrics.cpc,
        "spend": own_metrics.cost_in_usd,
        "conversions": own_metrics.conversions,
        "impressions": own_metrics.impressions,
        "clicks": own_metrics.clicks,
    }


# ── Moves (actionable next steps) ─────────────────────────────────────────────

_FORMAT_LABELS: Dict[str, str] = {
    "video": "video",
    "document": "document (thought leadership)",
    "carousel": "carousel",
    "message": "message / InMail",
    "thought_leader": "thought leader",
    "spotlight": "spotlight",
    "conversation": "conversation ad",
}


def _build_moves(
    activity: dict,
    formats: dict,
    sov: dict,
    scale: dict,
    efficiency: dict,
) -> List[str]:
    """Derive 2-4 plain-English, hyphens-not-em-dashes actionable next steps.

    Derived deterministically from computed gaps.
    """
    moves: List[str] = []

    # 1. Format gaps - highest priority, most actionable
    competitor_only = formats.get("competitor_only_formats", [])
    # Report the most impactful gaps first (video > document > carousel > others)
    priority_order = ["video", "document", "carousel", "message", "thought_leader", "spotlight"]
    gap_moves: List[str] = []
    other_gaps: List[str] = []
    for fmt in priority_order:
        if fmt in competitor_only:
            label = _FORMAT_LABELS.get(fmt, fmt)
            gap_moves.append(label)
    for fmt in competitor_only:
        if fmt not in priority_order:
            label = _FORMAT_LABELS.get(fmt, fmt)
            other_gaps.append(label)

    all_gap_labels = gap_moves + other_gaps
    if all_gap_labels:
        if len(all_gap_labels) == 1:
            moves.append(
                f"Competitors run {all_gap_labels[0]} ads - you don't - test one {all_gap_labels[0]} creative to close the gap."
            )
        else:
            top_two = all_gap_labels[:2]
            moves.append(
                f"Competitors use formats you don't: {', '.join(top_two)} - test one creative in each to close the gap."
            )

    # 2. Activity gap - if we're running fewer ads
    own_vs_field = activity.get("own_vs_field")
    if own_vs_field == "fewer":
        own_count = activity.get("own_serving_ads", 0)
        loudest = scale.get("loudest_by_ads")
        if loudest:
            moves.append(
                f"You are running {own_count} active ad(s) - the field leader has {loudest['n_ads']} - consider adding more ad variations to compete on volume."
            )
        else:
            moves.append(
                "You are running fewer active ads than the field average - consider adding more ad variations to compete on volume."
            )

    # 3. Efficiency advantage - if we have good CTR/CPC, lean into it
    ctr = efficiency.get("ctr")
    cpc = efficiency.get("cpc")
    if ctr is not None and ctr > 1.5:
        moves.append(
            f"Your CTR of {ctr:.1f}% is above average - increase budget on your best-performing ads to scale what's working."
        )
    elif cpc is not None and cpc < 5.0 and efficiency.get("clicks", 0) > 0:
        moves.append(
            f"Your CPC of ${cpc:.2f} is efficient - use this as the benchmark when testing new formats."
        )

    # 4. SOV awareness - if our SOV is very low
    own_sov = sov.get("own_sov_pct", 0.0)
    if own_sov < 10.0 and len(moves) < 3:
        moves.append(
            "Your share of voice on this keyword is low - focus spend on the highest-intent audience segments to punch above your weight."
        )

    # 5. Fallback: ensure at least 2 moves
    if len(moves) < 2:
        if not competitor_only:
            moves.append(
                "You match competitors on format - differentiate through copy, targeting, and creative refresh cadence."
            )
        if len(moves) < 2:
            moves.append(
                "Review which creatives drive conversions and pause those that don't to improve overall campaign efficiency."
            )

    return moves[:4]


# ── Main entry point ──────────────────────────────────────────────────────────

def build_comparison(
    own_metrics: LinkedInMetrics,
    own_creatives: List[Creative],
    competitor_profiles: List[dict],
    now_ms: int,
) -> dict:
    """Build the you-vs-them comparison dict.

    Parameters
    ----------
    own_metrics:
        Own LinkedIn campaign metrics (spend, impressions, clicks, etc.).
    own_creatives:
        List of own Creative objects (format, is_serving, status).
    competitor_profiles:
        List of per-competitor signal dicts as produced by the entry script /
        compute_company_signals.  Expected keys: name, n_ads_on_keyword,
        sov_pct, impression_data_coverage, formats, momentum_status,
        reach_low, reach_high, is_currently_advertising.
    now_ms:
        Current epoch milliseconds (no clock reads inside this function).

    Returns
    -------
    dict with structure::

        {
          "head_to_head": {
             "activity": {...},
             "formats": {...},
             "share_of_voice": {...}
          },
          "scale_vs_efficiency": {
             "competitor_scale": {...},
             "your_efficiency": {...}
          },
          "moves": [...]
        }
    """
    activity = _build_activity(own_creatives, competitor_profiles)
    formats = _build_formats(own_creatives, competitor_profiles)
    sov = _build_share_of_voice(own_creatives, competitor_profiles)
    scale = _build_competitor_scale(competitor_profiles)
    efficiency = _build_your_efficiency(own_metrics)
    moves = _build_moves(activity, formats, sov, scale, efficiency)

    return {
        "head_to_head": {
            "activity": activity,
            "formats": formats,
            "share_of_voice": sov,
        },
        "scale_vs_efficiency": {
            "competitor_scale": scale,
            "your_efficiency": efficiency,
        },
        "moves": moves,
    }

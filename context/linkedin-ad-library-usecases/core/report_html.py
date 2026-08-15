"""Self-contained, ZenABM-branded HTML report renderer for the keyword-competitor skill.

Turns a plain :class:`dict` (the ``report_data`` contract documented below) into a
single, fully self-contained HTML document - everything inlined, NO external
CSS/JS/fonts/images - so the file opens offline and survives a strict CSP.

Design constraints (deliberate):
  * **No pydantic / no third-party deps.** This module takes a plain ``dict`` and
    only uses the standard library, so it can be imported anywhere without dragging
    in the rest of ``core``.
  * **Charts are pure CSS/HTML bars + hand-drawn inline SVG.** No chart libraries.
  * **Print-to-PDF friendly.** ``@page`` margins, ``@media print`` tweaks,
    ``break-inside: avoid`` on cards, and a repeating ``<thead>`` on the table.
  * **Honest rendering (see CLAUDE.md hard-rule #2 and ``core.zenabm``).** Tier S/T
    signals that are ``None`` (limited-visibility advertiser, no detailed reach)
    render as the literal word "unknown" - never "no"/"0". The Tier N maturity
    score is always valid and always renders as ``<n>/10`` even when coverage is
    "none".

Entry points:
  * :func:`build_report_html`          - single keyword; ``dict -> str`` (a complete
    ``<!doctype html>`` doc).
  * :func:`write_report`               - single keyword; build + write to a path.
  * :func:`build_combined_report_html` - COMBINED multi-keyword (up to 3 keywords);
    ``dict -> str`` (one report covering every theme). See the combined contract
    below.
  * :func:`write_combined_report`      - combined; build + write to a path.

Combined input contract (multi-keyword ``data`` dict)::

    {
      "generated_at": str,
      "geographies": "Global",
      "free_tier_note": str,                # single top-of-report free-tier line
      "cross_keyword_summary": [str, ...],  # lead exec summary across all themes
      "keywords": [ <per-keyword dict, the v4 shape above>, ... ],  # 1-3 of them
      "cross_theme_rivals": [               # advertisers on 2+ of the themes
        {"name": str, "company_id": str|None, "advertiser_url": str,
         "keywords": [str, ...], "n_keywords": int}, ...
      ],
      "method_note": str,
      "upgrade_teaser": str,
    }

Input contract (``report_data`` dict), v4::

    {
      "keyword": str,
      "geographies": str,                 # e.g. "Global"
      "total_matching_ads": int,          # paging.total for the keyword (whole library)
      "n_ads_scanned": int,
      "n_individuals": int,               # individual advertisers itemised separately
      "generated_at": str,                # ISO date
      "exec_summary": [str, ...],         # the "5 that matter" + a thought-leader line

      # ---- v2 report-level additions ----
      "coverage_breakdown": {"full": int, "partial": int, "none": int},
      "pct_us_only": float,
      "field_format_distribution": {"video": int, "single_image": int,
                                    "carousel": int, "document": int, "message": int},
      "n_agency_run": int,
      "n_thought_leaders": int,
      "thought_leaders": [{"name": str, "advertiser_url": str,   # /in/ profile
                           "n_ads_on_keyword": int,
                           "promoted_by": str|None,              # paying company, if known
                           "sample_ad_url": str|None}, ...],
      "n_currently_advertising": int|None,
      "n_long_runners": int|None,

      "competitors": [                    # already ranked
        {"rank": int, "name": str, "company_id": str|None,
         "advertiser_type": "company"|"individual",
         "advertiser_url": str,                    # /company/<id> or /in/<slug> (Tier N)
         "n_ads_on_keyword": int,
         "impression_data_coverage": "full"|"partial"|"none",

         # ---- Tier N: ALWAYS rendered, even for coverage == "none" ----
         "linkedin_maturity_score": int,          # 0-10, ALWAYS <n>/10 (never unknown)
         "ad_types_used": [str, ...],
         "format_diversity_count": int,
         "agency_run": bool,                       # -> "Agency-run" / "In-house"
         "ad_payer_name": str|None,
         "formats": {"video": int, "single_image": int, "carousel": int,
                     "document": int, "message": int},

         # ---- Tier S: gated on coverage; None -> literal "unknown" ----
         "is_currently_advertising": bool|None,
         "momentum_status": "new"|"ramping"|"steady"|"cooling"|"dark"|"unknown",
         "outreach_timing_score": int|None,
         "reach_low": int|None, "reach_high": int|None,   # RANGE, never a point number
         "reach_tier": "micro".."enterprise"|None,        # REACH, not spend
         "reach_confidence": str,
         "ad_longevity_days": int|None,
         "is_long_runner": bool|None,              # badge "Long-runner (>90d)"
         "cadence_shape": "steady"|"bursty"|"one-off"|None,
         "eu_disclosed_share_pct": float|None,
         "primary_eu_market": {"country": str, "share_pct": float, "caveat": str}|None,
         # Where they advertise (plain regions/countries; None -> "not available")
         "top_regions": [{"region"|"country": str, "pct": float}, ...]|None,
         "geo_summary": str|None,
         "sov_pct": float,

         # ---- Tier T: targeting/intent; None -> literal "unknown" ----
         "funnel_stage": str|None,
         "targets_specific_companies": bool|None,  # -> "ABM / account-based"
         "targets_job_roles": bool|None,
         "uses_retargeting": bool|None,
         "targeting_dimensions_count": int|None,

         "read": str,                              # one-line "Our read:" per competitor
         "sample_ad_url": str},
      ],
      "whitespace": [str, ...],           # openings (opinion-labeled)
      "threats": [str, ...],              # threats to watch (opinion-labeled)
      "method_note": str,                 # consolidated honest caveat
      "upgrade_teaser": str,
    }
"""
from __future__ import annotations

import html
import urllib.parse
from typing import Any, Dict, List, Mapping, Optional, Sequence

__all__ = [
    "build_report_html",
    "write_report",
    "build_combined_report_html",
    "write_combined_report",
    "select_delivery",
]

UNKNOWN = "unknown"

# ZenABM brand accent (real). Used for buttons + inline CTAs so they survive as a
# standalone / emailed file (inline styles, not classes).
_BRAND_ACCENT = "#0f8a5f"
_BRAND_ACCENT_TEXT = "#ffffff"

# ZenABM funnel URLs (the four contextual CTAs land here).
_URL_SIGNUP = "https://app.zenabm.com/signup"
_URL_DEMO = "https://zenabm.com/book-a-demo"
_URL_HOME = "https://zenabm.com"

# Standard external-link attributes (new tab, no referrer leakage).
_EXT_ATTRS = 'target="_blank" rel="noopener noreferrer"'

# Ordered format keys → human labels for the format-mix stacked bars/legend.
_FORMAT_ORDER: Sequence[tuple] = (
    ("video", "Video"),
    ("single_image", "Single image"),
    ("carousel", "Carousel"),
    ("document", "Document"),
    ("message", "Message"),
)
# Distinct green→mint family colours for each format segment (brand-consistent).
_FORMAT_COLORS: Dict[str, str] = {
    "video": "#004737",
    "single_image": "#0f8a5f",
    "carousel": "#3fb98a",
    "document": "#87ffc0",
    "message": "#b5a642",
}

# Momentum status → (label, chip css class). Unknown/dark are muted grey.
_MOMENTUM_META: Dict[str, tuple] = {
    "new": ("New", "chip-accent"),
    "ramping": ("Ramping", "chip-accent"),
    "steady": ("Steady", "chip-muted"),
    "cooling": ("Cooling", "chip-warn"),
    "dark": ("Dark", "chip-grey"),
    "unknown": ("Unknown", "chip-grey"),
}

# Reach tier → human label. Framed as REACH (audience size), never spend. None ->
# "unknown" (limited visibility), handled by the formatter, not this map.
_REACH_TIER_LABELS: Dict[str, str] = {
    "micro": "Micro reach",
    "small": "Small reach",
    "mid": "Mid reach",
    "large": "Large reach",
    "enterprise": "Enterprise reach",
}

# Plain-English explanation shown wherever estimated reach appears.
_REACH_EXPLAINER = (
    "How many times their ads were shown, as an estimated range - a rough proxy "
    "for audience size. We never show spend; it is not public."
)

# Cadence shape → human label.
_CADENCE_LABELS: Dict[str, str] = {
    "steady": "Steady cadence",
    "bursty": "Bursty cadence",
    "one-off": "One-off",
}


# --------------------------------------------------------------------------- #
# Delivery environment detection                                              #
# --------------------------------------------------------------------------- #
def select_delivery(env: str) -> str:
    """Return the delivery mechanism string for the given environment name.

    Mapping:
      cowork*          -> "cowork_artifact"   (Cowork create_artifact + WeasyPrint)
      claude.ai*       -> "claude_artifact"   (claude.ai Artifact panel)
      claude-code*     -> "claude_artifact"   (Claude Code Artifact)
      anything else    -> "file"              (write self-contained HTML file)

    The match is case-insensitive and prefix-based so minor suffixes don't break it.
    """
    s = str(env or "").strip().lower()
    if s.startswith("cowork"):
        return "cowork_artifact"
    if s.startswith("claude.ai") or s.startswith("claude-code"):
        return "claude_artifact"
    return "file"


# --------------------------------------------------------------------------- #
# Inline ZenABM logo SVG (wordmark only, ~28 px, self-contained)              #
# --------------------------------------------------------------------------- #
# Extracted from zenabm-logo.svg (skills/abm-campaign-execution/assets/).
# Only the six lettermark <path> elements are embedded; the decorative leaf
# graphic is omitted to keep the snippet compact.  The viewBox is cropped to
# the lettermark region (x 164-1000, y 0-151 of the original 1000x151 canvas).
_ZENABM_LOGO_SVG = (
    '<svg style="height:28px;width:auto;display:block;flex:0 0 auto" '
    'viewBox="164 0 836 151" role="img" aria-label="ZenABM" '
    'xmlns="http://www.w3.org/2000/svg"><title>ZenABM</title>'
    '<path d="M836.479 146.434V0H881.972L918.237 69.0319L954.507 0H1000V146.434H966.039'
    "V46.6483L917.816 135.975L869.598 46.2324V146.434H836.475H836.479Z\" fill=\"#87ffc0\"/>"
    '<path d="M695.514 146.434V0H765.847C775.577 0 784.088 1.74562 791.389 5.23203'
    "C798.815 8.71844 804.629 13.5975 808.817 19.874C813.009 26.0103 815.101 33.1233 "
    "815.101 41.2131C815.101 47.2092 813.614 52.8571 810.642 58.1568C807.805 63.3163 "
    "803.889 67.7118 798.883 71.3384C805.234 74.8248 810.235 79.3557 813.881 84.9359"
    "C817.667 90.5161 819.555 96.6524 819.555 103.345C819.555 111.85 817.463 119.384 "
    "813.276 125.936C809.083 132.353 803.206 137.372 795.639 140.999C788.068 144.626 "
    "779.286 146.439 769.284 146.439H695.504L695.514 146.434ZM730.375 58.3647H763.62"
    "C768.756 58.3647 772.808 57.0398 775.781 54.3899C778.758 51.7401 780.244 48.2537 "
    "780.244 43.9307C780.244 39.6077 778.758 35.9811 775.781 33.4715C772.808 30.8216 "
    "768.756 29.4967 763.62 29.4967H730.375V58.3647ZM730.375 116.937H766.655C772.063 "
    "116.937 776.323 115.545 779.431 112.755C782.67 109.965 784.291 106.203 784.291 "
    "101.459C784.291 96.7152 782.67 92.9532 779.431 90.1631C776.323 87.373 772.063 "
    "85.9804 766.655 85.9804H730.375V116.942V116.937Z\" fill=\"#87ffc0\"/>"
    '<path d="M526.348 146.434L587.536 0H629.538L689.869 146.434H650.215L636.572 '
    "111.082H578.372L564.511 146.434H526.348ZM589.458 82.4214H625.699L607.792 35.5604"
    "L589.458 82.4214Z\" fill=\"#87ffc0\"/>"
    '<path d="M397.365 145.902V66.5948C397.365 47.2624 413.055 31.5856 432.415 31.5856'
    "V39.366C441.071 32.7365 451.31 29.4241 463.137 29.4241C472.084 29.4241 479.941 "
    "31.368 486.723 35.2606C493.646 39.1484 499.049 44.5545 502.951 51.4693C506.843 "
    "58.3841 508.794 66.382 508.794 75.4583V145.907H473.739V80.2116C473.739 73.8722 "
    "471.871 68.8288 468.119 65.0861C464.367 61.3386 459.322 59.4672 452.971 59.4672"
    "C448.497 59.4672 444.532 60.2603 441.071 61.8463C437.75 63.4324 434.869 65.6664 "
    "432.415 68.5435V145.907H397.365V145.902Z\" fill=\"#87ffc0\"/>"
    '<path d="M330.159 148.064C318.478 148.064 307.875 145.472 298.353 140.283'
    "C288.975 134.955 281.549 127.822 276.069 118.891C270.589 109.96 267.849 99.9454 "
    "267.849 88.8527C267.849 77.76 270.443 67.7456 275.638 58.8144C280.973 49.8832 "
    "288.186 42.8234 297.273 37.6349C306.36 32.3061 316.459 29.6369 327.565 29.6369"
    "C338.67 29.6369 348.769 32.3738 357.42 37.8476C366.076 43.1764 372.854 50.5263 "
    "377.758 59.8879C382.807 69.2543 385.33 79.9843 385.33 92.0876C385.33 96.8603 "
    "381.457 100.734 376.673 100.734H303.76C305.348 104.336 307.44 107.503 310.035 "
    "110.24C312.775 112.977 316.018 115.139 319.77 116.725C323.522 118.166 327.56 "
    "118.886 331.888 118.886C336.647 118.886 340.975 118.166 344.867 116.725C351.088 "
    "114.191 358.742 113.717 363.767 118.175L377.971 130.772C370.758 136.821 363.331 "
    "141.217 355.687 143.953C348.188 146.69 339.677 148.059 330.159 148.059V148.064Z"
    "M303.112 76.3142H350.928C349.776 72.5666 347.97 69.3994 345.52 66.8075C343.211 "
    "64.0706 340.471 61.9817 337.3 60.5407C334.129 58.9547 330.668 58.1616 326.916 "
    "58.1616C323.164 58.1616 319.489 58.8821 316.314 60.3231C313.138 61.7641 310.398 "
    "63.853 308.093 66.5899C305.929 69.1818 304.269 72.4264 303.117 76.3142H303.112Z"
    '" fill="#87ffc0"/>'
    '<path d="M188.458 145.902C174.956 145.902 164.01 134.969 164.01 121.483L217.234 '
    "60.7583H164.441C164.441 44.6464 177.517 31.5856 193.648 31.5856H238.216C251.718 "
    "31.5856 262.664 42.5187 262.664 56.005L209.222 116.729H264.392C264.392 132.841 "
    "251.316 145.902 235.185 145.902H188.458Z\" fill=\"#87ffc0\"/>"
    "</svg>"
)


# --------------------------------------------------------------------------- #
# Small honest-formatting helpers (mirror src/report.py semantics)            #
# --------------------------------------------------------------------------- #
def _esc(value: Any) -> str:
    """HTML-escape any value (also quotes, for safe attribute use)."""
    return html.escape("" if value is None else str(value), quote=True)


def _fmt_int(value: Optional[int]) -> str:
    return UNKNOWN if value is None else f"{int(value):,}"


def _fmt_bool(value: Optional[bool]) -> str:
    """Optional[bool] -> 'yes' / 'no' / 'unknown' (None is unknown, never 'no')."""
    if value is None:
        return UNKNOWN
    return "yes" if value else "no"


def _fmt_text(value: Optional[str]) -> str:
    """Free-text optional (e.g. funnel_stage): None/'' -> 'unknown'."""
    if value is None or str(value).strip() == "":
        return UNKNOWN
    return str(value)


def _fmt_maturity(score: Any) -> str:
    """Tier N - ALWAYS known, valid for 100% of ads, NOT gated on coverage.

    Only a genuinely-missing value renders as unknown; otherwise ``<n>/10``.
    """
    if score is None:
        return UNKNOWN
    try:
        return f"{int(score)}/10"
    except (TypeError, ValueError):
        return UNKNOWN


def _fmt_coverage(coverage: Optional[str]) -> str:
    return coverage if coverage else "none"


def _fmt_reach(low: Optional[int], high: Optional[int]) -> str:
    """Reach as an honest RANGE. Never a single fabricated number.

    Both None -> "not available". Otherwise "25,000-50,000" (an equal low==high
    collapses to a single formatted number, which is a real bound, not a guess).
    """
    if low is None and high is None:
        return "not available"
    if low is not None and high is not None:
        if low == high:
            return f"{int(low):,}"
        return f"{int(low):,}-{int(high):,}"
    # Only one bound known - show it as an open range rather than inventing the other.
    if low is not None:
        return f"≥{int(low):,}"
    return f"≤{int(high):,}"


def _reach_confidence(coverage: Optional[str]) -> str:
    """A short confidence hint tied to impression-data coverage."""
    cov = _fmt_coverage(coverage)
    return {
        "full": "higher confidence",
        "partial": "partial coverage",
        "none": "not available",
    }.get(cov, "partial coverage")


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# --------------------------------------------------------------------------- #
# v2 honest-formatting helpers                                                 #
# --------------------------------------------------------------------------- #
def _fmt_reach_tier(tier: Optional[str]) -> str:
    """Reach tier as an audience-size band. None -> "unknown" (Tier S, gated).

    Deliberately framed as REACH (how many times ads were shown), never as spend -
    spend is not public.
    """
    if tier is None or str(tier).strip() == "":
        return UNKNOWN
    return _REACH_TIER_LABELS.get(str(tier).strip().lower(), str(tier))


def _fmt_cadence(shape: Optional[str]) -> str:
    if shape is None or str(shape).strip() == "":
        return UNKNOWN
    return _CADENCE_LABELS.get(str(shape).strip().lower(), str(shape))


def _fmt_pct(value: Optional[float], digits: int = 0) -> str:
    """Optional percentage -> 'NN%' / 'NN.N%', or 'unknown' when None."""
    if value is None:
        return UNKNOWN
    try:
        return f"{float(value):.{digits}f}%"
    except (TypeError, ValueError):
        return UNKNOWN


def _agency_label(agency_run: Any) -> str:
    """Tier N (ALWAYS shown). True -> 'Agency-run', anything else -> 'In-house'.

    Derived upstream from ad_payer_differs_normalized; here we render only.
    """
    return "Agency-run" if bool(agency_run) else "In-house"


def _ext_link(href: Optional[str], text: str, *, escaped_text: bool = False) -> str:
    """Subtle accent-green external link with a trailing arrow, safe target/rel.

    ``text`` is escaped unless ``escaped_text`` is True (caller pre-escaped markup).
    Falls back to plain (escaped) text when there is no usable href.
    """
    label = text if escaped_text else _esc(text)
    if not href or not str(href).strip():
        return label
    return (
        f'<a class="ext-link" href="{_esc(href)}" {_EXT_ATTRS}>'
        f'{label}<span class="ext-arrow" aria-hidden="true">↗</span></a>'
    )


def _company_slug(name: Any) -> str:
    """URL-encode an advertiser name for the ad-library search affordance."""
    return urllib.parse.quote(str(name or "").strip())


def _account_owner_search_url(name: Any) -> Optional[str]:
    """Global, unrestricted advertiser search URL by name.

    No geography filter and no date filter, so it resolves to the advertiser
    everywhere they run - the URL-encoded name is the only parameter.
    """
    slug = _company_slug(name)
    if not slug:
        return None
    return f"https://www.linkedin.com/ad-library/search?accountOwner={slug}"


def _see_ads_url(competitor: Mapping[str, Any]) -> Optional[str]:
    """Build the "See their ads" advertiser-search URL (global, no geo filter).

    Uses ``accountOwner=<quoted name>`` when we have a usable name; if the name is
    empty/uncertain, FALL BACK to the competitor's ``sample_ad_url``.
    """
    url = _account_owner_search_url(competitor.get("name"))
    if url:
        return url
    sample = competitor.get("sample_ad_url")
    return str(sample) if sample else None


def _see_ads_link(competitor: Mapping[str, Any]) -> str:
    """A compact "See their ads" affordance (external link), or empty string."""
    url = _see_ads_url(competitor)
    if not url:
        return ""
    return _ext_link(url, "See their ads")


def _name_link(competitor: Mapping[str, Any]) -> str:
    """Advertiser name hyperlinked to its advertiser_url (company or /in/ profile).

    Only names are linked - never numbers/signals. Falls back to plain escaped
    name when advertiser_url is missing.
    """
    return _ext_link(competitor.get("advertiser_url"), competitor.get("name") or "")


def _read_line(text: Optional[str]) -> str:
    """Render the per-competitor "Our read:" one-liner, badged, or empty string."""
    if not text or not str(text).strip():
        return ""
    return (
        '<div class="read-line">'
        '<span class="opinion-badge">Our read:</span>'
        f'<span class="read-text">{_esc(text)}</span>'
        "</div>"
    )


def _cta(text: str, *, primary: str = "", secondary: str = "", extra: str = "") -> str:
    """A contextual ZenABM CTA block: on-brand copy + inline-styled button(s).

    ``primary`` / ``secondary`` / ``extra`` are pre-built anchor HTML (see
    :func:`_cta_btn` / :func:`_cta_textlink`). Inline styles are used throughout so
    the CTA survives when the file is emailed or opened standalone.
    """
    buttons = "".join(b for b in (primary, secondary, extra) if b)
    return (
        '<div class="zen-cta">'
        f'<p class="zen-cta-copy">{_esc(text)}</p>'
        f'<div class="zen-cta-actions">{buttons}</div>'
        "</div>"
    )


def _cta_btn(label: str, href: str, *, kind: str = "primary") -> str:
    """An inline-styled CTA button (survives standalone/emailed). Real brand accent."""
    if kind == "primary":
        style = (
            f"display:inline-block;background:{_BRAND_ACCENT};color:{_BRAND_ACCENT_TEXT};"
            "border:1px solid " + _BRAND_ACCENT + ";border-radius:10px;"
            "padding:10px 18px;font-weight:600;text-decoration:none;font-size:14px;"
        )
    else:  # secondary: green outline, transparent fill
        style = (
            f"display:inline-block;background:transparent;color:{_BRAND_ACCENT};"
            f"border:1px solid {_BRAND_ACCENT};border-radius:10px;"
            "padding:10px 18px;font-weight:600;text-decoration:none;font-size:14px;"
        )
    return f'<a href="{_esc(href)}" {_EXT_ATTRS} style="{style}">{_esc(label)}</a>'


def _cta_textlink(label: str, href: str) -> str:
    """A small plain text link (used for the footer 'zenabm.com' affordance)."""
    style = f"color:{_BRAND_ACCENT};text-decoration:none;font-size:13px;font-weight:600;"
    return f'<a href="{_esc(href)}" {_EXT_ATTRS} style="{style}">{_esc(label)}</a>'


def _esc_or_unknown(value: str) -> str:
    """Escape a formatted string; render the literal 'unknown' with the muted style."""
    if value == UNKNOWN:
        return f'<span class="val-unknown">{UNKNOWN}</span>'
    return _esc(value)


def _fmt_ad_types(ad_types: Any) -> str:
    """Tier N: creative formats used (list[str]) -> comma list, or 'unknown'."""
    if not ad_types:
        return f'<span class="val-unknown">{UNKNOWN}</span>'
    try:
        items = [str(t).strip() for t in ad_types if str(t).strip()]
    except TypeError:
        return f'<span class="val-unknown">{UNKNOWN}</span>'
    if not items:
        return f'<span class="val-unknown">{UNKNOWN}</span>'
    return _esc(", ".join(items))


def _momentum_text(status: Optional[str]) -> Optional[str]:
    """Momentum status -> human label. 'unknown'/'dark'-with-no-signal -> None so
    the caller renders the literal 'unknown' rather than a fabricated 'no'.
    """
    s = str(status or "").strip().lower()
    if s == "" or s == "unknown":
        return None
    label, _cls = _MOMENTUM_META.get(s, (None, None))
    return label


# --------------------------------------------------------------------------- #
# Inline assets: full stylesheet                                               #
# --------------------------------------------------------------------------- #
_STYLE = """
:root{
  --zen-primary:#004737; --zen-primary-fg:#fafafa; --zen-accent:#0f8a5f;
  --zen-accent-mint:#87ffc0; --zen-mint-tint:#d4ffe8;
  --zen-surface:#ffffff; --zen-surface-cream:#f4f1e8; --zen-surface-beige:#f7f6f1; --zen-muted:#f5f5f5;
  --zen-ink:#004737; --zen-muted-fg:#737373; --zen-border:#e5e5e5; --zen-ring:#a1a1a1;
  --zen-success:#00bb7f; --zen-warn:#f99c00; --zen-danger:#ff6568; --zen-info:#1447e6;
  --zen-radius:.625rem; --zen-radius-lg:1rem;
  --zen-font-heading:"Poppins","Segoe UI",system-ui,-apple-system,"Helvetica Neue",Arial,sans-serif;
  --zen-font-body:"Montserrat",ui-sans-serif,system-ui,-apple-system,"Segoe UI","Helvetica Neue",Arial,sans-serif;
  --zen-gradient-cta:linear-gradient(135deg,#0f8a5f 0%,#87ffc0 100%);
}
*{box-sizing:border-box;}
html{-webkit-text-size-adjust:100%;}
body{
  margin:0; padding:2rem 1rem 4rem;
  font-family:var(--zen-font-body);
  color:#1f2937; line-height:1.55;
  background:
    radial-gradient(1200px 500px at 50% -200px, var(--zen-mint-tint), transparent 60%),
    var(--zen-surface-beige);
  font-size:15px;
}
.zen-page{max-width:900px; margin:0 auto;}
h1,h2,h3{font-family:var(--zen-font-heading); color:var(--zen-ink); margin:0; line-height:1.2; font-weight:700;}
h2{font-size:1.15rem; letter-spacing:-.01em;}
h3{font-size:.95rem;}
p{margin:.4rem 0;}
a{color:var(--zen-accent); text-decoration:none;}
a:hover{text-decoration:underline;}
.tnum{font-variant-numeric:tabular-nums; font-feature-settings:"tnum" 1;}
.muted{color:var(--zen-muted-fg);}
.small{font-size:.8rem;}

/* Cards / sections */
.zen-section{
  background:var(--zen-surface);
  border:1px solid var(--zen-border);
  border-radius:var(--zen-radius-lg);
  padding:1.25rem 1.4rem;
  margin:1.1rem 0;
  box-shadow:0 1px 2px rgba(0,71,55,.04), 0 8px 24px rgba(0,71,55,.05);
}
.zen-section > .sec-head{
  display:flex; align-items:baseline; justify-content:space-between;
  gap:1rem; margin-bottom:.85rem; flex-wrap:wrap;
}
.zen-section > .sec-head .sec-sub{color:var(--zen-muted-fg); font-size:.8rem;}

/* Header */
.zen-header{
  display:flex; align-items:center; gap:1.1rem;
  background:linear-gradient(135deg, var(--zen-primary) 0%, #063f31 100%);
  color:var(--zen-primary-fg);
  border-radius:var(--zen-radius-lg);
  padding:1.35rem 1.6rem;
  box-shadow:0 10px 30px rgba(0,71,55,.18);
}
.zen-header .head-text{min-width:0;}
.zen-header h1{color:var(--zen-primary-fg); font-size:1.4rem; letter-spacing:-.015em;}
.zen-header .kw{color:var(--zen-accent-mint);}
.zen-header .head-sub{color:#cdeede; font-size:.82rem; margin-top:.15rem;}

/* Scope bar */
.zen-scope{
  display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
  gap:.75rem; margin:1.1rem 0;
}
.scope-item{
  background:var(--zen-surface-cream);
  border:1px solid var(--zen-border);
  border-radius:var(--zen-radius);
  padding:.7rem .85rem;
}
.scope-item .k{font-size:.7rem; text-transform:uppercase; letter-spacing:.05em; color:var(--zen-muted-fg);}
.scope-item .v{font-family:var(--zen-font-heading); font-weight:600; color:var(--zen-ink); font-size:1.05rem; margin-top:.15rem;}

/* Executive summary */
ul.exec{margin:.25rem 0 0; padding:0; list-style:none;}
ul.exec li{
  position:relative; padding:.5rem .75rem .5rem 2.1rem; margin:.4rem 0;
  background:var(--zen-mint-tint);
  border:1px solid #b8f0d3;
  border-radius:var(--zen-radius);
}
ul.exec li::before{
  content:""; position:absolute; left:.8rem; top:.95rem;
  width:.55rem; height:.55rem; border-radius:2px;
  background:var(--zen-gradient-cta);
}

/* SoV leaderboard bars */
.bars{display:flex; flex-direction:column; gap:.5rem;}
.bar-row{display:grid; grid-template-columns:minmax(130px,180px) 1fr auto; align-items:center; gap:.7rem;}
.bar-row .lbl{font-size:.85rem; color:var(--zen-ink); font-weight:500; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;}
.bar-track{background:var(--zen-muted); border-radius:999px; height:1.1rem; overflow:hidden; border:1px solid var(--zen-border);}
.bar-fill{height:100%; background:var(--zen-accent); border-radius:999px; min-width:2px;
  background-image:linear-gradient(90deg, var(--zen-accent), #14a56f);}
.bar-row .val{font-size:.82rem; color:var(--zen-ink); font-weight:600; min-width:3.4rem; text-align:right;}

/* Momentum board */
.momentum-grid{display:flex; flex-wrap:wrap; gap:.5rem .6rem;}
.momentum-cell{
  display:flex; align-items:center; gap:.55rem;
  border:1px solid var(--zen-border); border-radius:999px;
  padding:.3rem .3rem .3rem .8rem; background:var(--zen-surface);
}
.momentum-cell .mc-name{font-size:.83rem; color:var(--zen-ink);}
.chip{
  display:inline-flex; align-items:center; gap:.35rem;
  font-size:.72rem; font-weight:600; line-height:1;
  padding:.32rem .6rem; border-radius:999px; white-space:nowrap;
  font-family:var(--zen-font-heading);
}
.chip::before{content:""; width:.45rem; height:.45rem; border-radius:999px; background:currentColor; opacity:.85;}
.chip-accent{background:var(--zen-mint-tint); color:var(--zen-accent);}
.chip-muted{background:var(--zen-muted); color:var(--zen-muted-fg);}
.chip-warn{background:#fff2dc; color:#b56b00;}
.chip-grey{background:#eeeeee; color:#8a8a8a;}

/* Format mix */
.fmt-legend{display:flex; flex-wrap:wrap; gap:.35rem .9rem; margin-bottom:.85rem;}
.fmt-legend .lg{display:inline-flex; align-items:center; gap:.35rem; font-size:.75rem; color:var(--zen-muted-fg);}
.fmt-legend .sw{width:.7rem; height:.7rem; border-radius:3px; display:inline-block;}
.fmt-rows{display:flex; flex-direction:column; gap:.45rem;}
.fmt-row{display:grid; grid-template-columns:minmax(130px,180px) 1fr auto; align-items:center; gap:.7rem;}
.fmt-row .lbl{font-size:.85rem; color:var(--zen-ink); font-weight:500; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;}
.fmt-bar{display:flex; height:1.1rem; border-radius:6px; overflow:hidden; border:1px solid var(--zen-border); background:var(--zen-muted);}
.fmt-seg{height:100%;}
.fmt-row .cnt{font-size:.8rem; color:var(--zen-muted-fg); min-width:2.6rem; text-align:right;}
.fmt-row .empty{font-size:.78rem; color:var(--zen-muted-fg); font-style:italic;}

/* Reach list */
.reach-explainer{margin:0 0 .7rem; font-size:.8rem; color:var(--zen-muted-fg); line-height:1.45;}
.reach-rows{display:flex; flex-direction:column; gap:.4rem;}
.reach-row{display:grid; grid-template-columns:minmax(130px,180px) 1fr auto; gap:.7rem; align-items:baseline;
  padding:.35rem 0; border-bottom:1px dashed var(--zen-border);}
.reach-row:last-child{border-bottom:0;}
.reach-row .lbl{font-size:.85rem; color:var(--zen-ink); font-weight:500;}
.reach-row .rng{font-size:.9rem; color:var(--zen-ink); font-weight:600;}
.reach-row .conf{font-size:.72rem; color:var(--zen-muted-fg); text-align:right;}

/* Tables (shadcn-ish) */
.table-wrap{overflow-x:auto; border:1px solid var(--zen-border); border-radius:var(--zen-radius);}
table.zen-table{width:100%; border-collapse:collapse; font-size:.83rem;}
table.zen-table thead th{
  background:var(--zen-surface-cream); color:var(--zen-ink);
  text-align:left; font-family:var(--zen-font-heading); font-weight:600;
  padding:.6rem .7rem; border-bottom:1px solid var(--zen-border); white-space:nowrap;
}
table.zen-table td{padding:.55rem .7rem; border-bottom:1px solid var(--zen-border); vertical-align:top;}
table.zen-table tbody tr:nth-child(even){background:var(--zen-muted);}
table.zen-table tbody tr:last-child td{border-bottom:0;}
table.zen-table .num{text-align:right; font-variant-numeric:tabular-nums;}
.badge{display:inline-block; font-size:.68rem; font-weight:600; padding:.12rem .45rem; border-radius:999px;
  font-family:var(--zen-font-heading);}
.badge-cov-full{background:var(--zen-mint-tint); color:var(--zen-accent);}
.badge-cov-partial{background:#fff2dc; color:#b56b00;}
.badge-cov-none{background:#eeeeee; color:#8a8a8a;}
.val-unknown{color:var(--zen-muted-fg); font-style:italic;}
.val-yes{color:var(--zen-success); font-weight:600;}
.val-no{color:var(--zen-muted-fg);}

/* Whitespace / opinion */
.opinion-badge{
  display:inline-block; font-family:var(--zen-font-heading); font-weight:600;
  font-size:.68rem; letter-spacing:.04em; text-transform:uppercase;
  color:#fff; background:var(--zen-gradient-cta);
  padding:.15rem .5rem; border-radius:999px; margin-right:.5rem;
}
ul.whitespace{margin:.25rem 0 0; padding:0; list-style:none;}
ul.whitespace li{
  padding:.6rem .75rem; margin:.45rem 0;
  background:var(--zen-surface-cream); border:1px solid var(--zen-border);
  border-left:3px solid var(--zen-accent); border-radius:var(--zen-radius);
  font-size:.88rem;
}

/* Method note */
.method-note{
  background:var(--zen-muted); border:1px solid var(--zen-border);
  border-radius:var(--zen-radius); padding:.85rem 1rem;
  font-size:.82rem; color:var(--zen-muted-fg);
}

/* Upgrade teaser footer */
.upgrade{
  margin-top:1.3rem;
  background:var(--zen-gradient-cta);
  color:#03291f;
  border-radius:var(--zen-radius-lg);
  padding:1.2rem 1.4rem;
  box-shadow:0 10px 30px rgba(15,138,95,.22);
}
.upgrade h2{color:#03291f;}
.upgrade p{color:#0a3a2c; font-size:.92rem;}

.page-foot{margin-top:1.4rem; text-align:center; color:var(--zen-muted-fg); font-size:.72rem;}

/* External links (subtle accent-green, trailing arrow) */
a.ext-link{color:var(--zen-accent); text-decoration:none; font-weight:500;}
a.ext-link:hover{text-decoration:underline;}
a.ext-link .ext-arrow{font-size:.82em; margin-left:.12em; opacity:.85;}

/* Per-competitor "Our read:" line */
.read-line{margin-top:.45rem; font-size:.83rem; color:var(--zen-ink); line-height:1.45;}
.read-line .opinion-badge{margin-right:.45rem;}
.read-line .read-text{color:#2f4a41;}

/* Coverage breakdown line in the scope bar */
.coverage-line{
  grid-column:1/-1;
  display:flex; flex-wrap:wrap; align-items:center; gap:.5rem .9rem;
  background:var(--zen-surface-cream); border:1px solid var(--zen-border);
  border-radius:var(--zen-radius); padding:.55rem .85rem;
  font-size:.8rem; color:var(--zen-muted-fg);
}
.coverage-line .cov-k{font-family:var(--zen-font-heading); font-weight:600; color:var(--zen-ink);}
.coverage-line .cov-seg{display:inline-flex; align-items:center; gap:.35rem;}
.coverage-line .cov-dot{width:.55rem; height:.55rem; border-radius:2px; display:inline-block;}

/* Free-tier limit line in the scope bar */
.free-tier-line{
  grid-column:1/-1;
  background:var(--zen-mint-tint); border:1px solid #b8f0d3;
  border-left:3px solid var(--zen-accent); border-radius:var(--zen-radius);
  padding:.55rem .85rem; font-size:.8rem; color:#1f3d33;
}
.free-tier-line .cov-k{font-family:var(--zen-font-heading); font-weight:600; color:var(--zen-ink);}

/* Freemium teaser card (after the top-5 competitor cards) */
.comp-teaser{
  border:1px dashed var(--zen-accent); border-radius:var(--zen-radius);
  padding:1.1rem 1.15rem; background:var(--zen-surface-cream);
  text-align:center;
}
.comp-teaser .teaser-copy{margin:0 0 .8rem; font-size:.95rem; color:#1f3d33; line-height:1.5;}
.comp-teaser .teaser-copy strong{color:var(--zen-ink);}

/* Competitor detail cards (rich per-competitor view) */
.comp-cards{display:flex; flex-direction:column; gap:.85rem;}
.comp-card{
  border:1px solid var(--zen-border); border-radius:var(--zen-radius);
  padding:.85rem 1rem; background:var(--zen-surface);
}
.comp-card .cc-head{
  display:flex; align-items:baseline; justify-content:space-between;
  gap:.6rem; flex-wrap:wrap; margin-bottom:.5rem;
}
.comp-card .cc-title{display:flex; align-items:baseline; gap:.5rem; flex-wrap:wrap;}
.comp-card .cc-rank{font-family:var(--zen-font-heading); font-weight:700; color:var(--zen-muted-fg); font-size:.85rem;}
.comp-card .cc-name{font-family:var(--zen-font-heading); font-weight:700; color:var(--zen-ink); font-size:1rem;}
.comp-card .cc-actions{display:flex; align-items:center; gap:.7rem; font-size:.8rem;}
.comp-card .cc-signals{
  display:grid; grid-template-columns:repeat(auto-fill,minmax(160px,1fr));
  gap:.4rem .9rem; margin-top:.35rem;
}
.comp-card .sig{font-size:.8rem;}
.comp-card .sig .k{color:var(--zen-muted-fg); text-transform:uppercase; letter-spacing:.04em; font-size:.66rem;}
.comp-card .sig .v{color:var(--zen-ink); font-weight:500;}
.comp-card .cc-badges{display:flex; flex-wrap:wrap; gap:.35rem; margin-top:.15rem;}

/* Contextual ZenABM CTA blocks */
.zen-cta{
  margin:1.1rem 0;
  background:var(--zen-mint-tint);
  border:1px solid #b8f0d3;
  border-left:3px solid var(--zen-accent);
  border-radius:var(--zen-radius);
  padding:.9rem 1.1rem;
}
.zen-cta-copy{margin:0 0 .7rem; font-size:.9rem; color:#1f3d33; line-height:1.5;}
.zen-cta-actions{display:flex; flex-wrap:wrap; gap:.6rem; align-items:center;}

/* Whitespace / threats split lists */
ul.threats{margin:.25rem 0 0; padding:0; list-style:none;}
ul.threats li{
  padding:.6rem .75rem; margin:.45rem 0;
  background:#fff6f0; border:1px solid #ffd9c7;
  border-left:3px solid var(--zen-warn); border-radius:var(--zen-radius);
  font-size:.88rem;
}
.split-cols{display:grid; grid-template-columns:1fr 1fr; gap:1.1rem;}
.split-cols h3{margin-bottom:.15rem; font-size:.9rem;}

/* Itemized thought-leaders */
.tl-list{display:flex; flex-direction:column; gap:.4rem;}
.tl-row{
  display:flex; align-items:baseline; justify-content:space-between; gap:.7rem;
  padding:.4rem 0; border-bottom:1px dashed var(--zen-border);
}
.tl-row:last-child{border-bottom:0;}
.tl-row .tl-name{font-size:.88rem; color:var(--zen-ink); font-weight:500;}
.tl-row .tl-frame{color:var(--zen-muted-fg); font-weight:400;}
.tl-row .tl-meta{display:flex; align-items:baseline; gap:.9rem; white-space:nowrap;}
.tl-row .tl-count{font-size:.78rem; color:var(--zen-muted-fg); white-space:nowrap;}
.tl-row .tl-adlink{font-size:.8rem;}

/* Combined multi-keyword report: per-keyword divider + block */
.kw-divider{
  display:flex; align-items:center; gap:.9rem;
  margin:2.1rem 0 .4rem;
}
.kw-divider::before,.kw-divider::after{
  content:""; flex:1 1 auto; height:1px; background:var(--zen-border);
}
.kw-divider .kw-chip{
  font-family:var(--zen-font-heading); font-weight:700; color:var(--zen-primary-fg);
  background:linear-gradient(135deg, var(--zen-primary) 0%, #063f31 100%);
  border-radius:999px; padding:.35rem .95rem; font-size:.9rem; white-space:nowrap;
  box-shadow:0 6px 18px rgba(0,71,55,.16);
}
.kw-divider .kw-chip .kw-idx{color:var(--zen-accent-mint); margin-right:.4rem; font-weight:700;}
.kw-block{margin-bottom:.6rem;}
.kw-block > .kw-title{
  font-family:var(--zen-font-heading); font-weight:700; color:var(--zen-ink);
  font-size:1.25rem; letter-spacing:-.015em; margin:.2rem 0 .1rem;
}
.kw-block > .kw-scope-line{color:var(--zen-muted-fg); font-size:.85rem; margin:0 0 .4rem;}
.kw-block > .kw-scope-line .tnum{color:var(--zen-ink); font-weight:600;}

/* Cross-theme rivals roll-up */
.rivals-intro{margin:.1rem 0 .9rem; font-size:.9rem; color:#2f4a41;}
.rival-list{display:flex; flex-direction:column; gap:.4rem;}
.rival-row{
  display:flex; align-items:baseline; justify-content:space-between; gap:.8rem;
  padding:.5rem .1rem; border-bottom:1px dashed var(--zen-border);
}
.rival-row:last-child{border-bottom:0;}
.rival-row .rv-name{font-size:.92rem; color:var(--zen-ink); font-weight:600;}
.rival-row .rv-themes{color:var(--zen-muted-fg); font-weight:400; font-size:.83rem;}
.rival-row .rv-count{
  font-family:var(--zen-font-heading); font-weight:700; font-size:.78rem;
  background:var(--zen-mint-tint); color:var(--zen-accent);
  border-radius:999px; padding:.22rem .6rem; white-space:nowrap;
}
.rivals-empty{
  background:var(--zen-surface-cream); border:1px solid var(--zen-border);
  border-radius:var(--zen-radius); padding:.85rem 1rem;
  font-size:.88rem; color:var(--zen-muted-fg);
}

@media (max-width:640px){
  .split-cols{grid-template-columns:1fr;}
  .bar-row,.fmt-row,.reach-row{grid-template-columns:1fr; gap:.25rem;}
  .bar-row .val,.reach-row .conf{text-align:left;}
  .zen-header{flex-direction:column; align-items:flex-start;}
  .rival-row{flex-direction:column; align-items:flex-start; gap:.2rem;}
}

/* Print / PDF */
@page{margin:14mm;}
@media print{
  body{background:#fff; padding:0; font-size:11.5px;}
  .zen-page{max-width:none;}
  .zen-section,.zen-header,.upgrade{box-shadow:none;}
  .zen-section,.scope-item,.momentum-cell,.bar-row,.fmt-row,.reach-row,ul.exec li,ul.whitespace li,tr{
    break-inside:avoid; page-break-inside:avoid;
  }
  table.zen-table thead{display:table-header-group;}
  a{color:inherit;}
  .upgrade{color:#03291f;}
}
""".strip()


# --------------------------------------------------------------------------- #
# Section builders                                                            #
# --------------------------------------------------------------------------- #
def _download_pdf_btn() -> str:
    """A visible Download-PDF button that triggers window.print()."""
    style = (
        "display:inline-block;background:rgba(255,255,255,.15);color:#fff;"
        "border:1px solid rgba(255,255,255,.4);border-radius:8px;"
        "padding:6px 14px;font-size:13px;font-weight:600;cursor:pointer;"
        "font-family:inherit;line-height:1.4;"
    )
    return (
        f'<button type="button" onclick="window.print()" style="{style}" '
        'aria-label="Download PDF">Download PDF</button>'
    )


def _header(data: Mapping[str, Any]) -> str:
    keyword = _esc(data.get("keyword", ""))
    generated = _esc(data.get("generated_at", ""))
    return (
        '<header class="zen-header">'
        + _ZENABM_LOGO_SVG
        + '<div class="head-text" style="flex:1;min-width:0">'
        + f'<h1>Competitors advertising on <span class="kw">&ldquo;{keyword}&rdquo;</span></h1>'
        + f'<div class="head-sub">Competitor scan &middot; generated {generated}</div>'
        + "</div>"
        + '<div class="head-actions" style="flex:0 0 auto;margin-left:auto">'
        + _download_pdf_btn()
        + "</div>"
        + "</header>"
    )


def _coverage_line(data: Mapping[str, Any]) -> str:
    """A compact "coverage breakdown" line so the reader sees how much is gated.

    Reads ``coverage_breakdown`` {full,partial,none}; falls back to counting the
    competitor list. Renders e.g. "8 full visibility, 5 limited visibility" plus a
    partial count.
    """
    cb = data.get("coverage_breakdown") or {}
    competitors = list(data.get("competitors", []) or [])
    if cb:
        n_full = int(_num(cb.get("full")))
        n_partial = int(_num(cb.get("partial")))
        n_none = int(_num(cb.get("none")))
    else:
        n_full = sum(1 for c in competitors if _fmt_coverage(c.get("impression_data_coverage")) == "full")
        n_partial = sum(1 for c in competitors if _fmt_coverage(c.get("impression_data_coverage")) == "partial")
        n_none = sum(1 for c in competitors if _fmt_coverage(c.get("impression_data_coverage")) == "none")
    if not (n_full or n_partial or n_none):
        return ""
    full_vis = n_full + n_partial
    segs = [
        f'<span class="cov-seg"><span class="cov-dot" style="background:{_FORMAT_COLORS["single_image"]}"></span>'
        f"{full_vis} full visibility</span>",
        f'<span class="cov-seg"><span class="cov-dot" style="background:#c9c9c9"></span>'
        f"{n_none} limited visibility</span>",
    ]
    if n_partial:
        segs.insert(
            1,
            f'<span class="cov-seg muted">({n_partial} partial coverage)</span>',
        )
    pct_us = data.get("pct_us_only")
    if pct_us is not None:
        segs.append(f'<span class="cov-seg muted">{_fmt_pct(pct_us)} of field is limited visibility</span>')
    return (
        '<div class="coverage-line">'
        '<span class="cov-k">Coverage breakdown:</span>'
        + "".join(segs)
        + "</div>"
    )


def _scope_bar(data: Mapping[str, Any]) -> str:
    items = [
        ("Keyword", _esc(data.get("keyword", ""))),
        ("Geographies", _esc(data.get("geographies", ""))),
        ("Total matching ads", f'<span class="tnum">{_fmt_int(data.get("total_matching_ads"))}</span>'),
        ("Ads scanned", f'<span class="tnum">{_fmt_int(data.get("n_ads_scanned"))}</span>'),
    ]
    cells = "".join(
        f'<div class="scope-item"><div class="k">{k}</div><div class="v">{v}</div></div>'
        for k, v in items
    )
    n_scanned = _fmt_int(data.get("n_ads_scanned"))
    free_line = (
        '<div class="free-tier-line">'
        '<span class="cov-k">Free version:</span> '
        f"up to 3 keywords, top 5 competitors each, top {n_scanned} ads scanned per "
        "keyword. Upgrade for the full library."
        "</div>"
    )
    return f'<div class="zen-scope">{cells}{_coverage_line(data)}{free_line}</div>'


def _exec_summary(data: Mapping[str, Any]) -> str:
    bullets = [b for b in data.get("exec_summary", []) if str(b).strip()]
    if not bullets:
        return ""
    lis = "".join(f"<li>{_esc(b)}</li>" for b in bullets)
    return (
        '<section class="zen-section">'
        '<div class="sec-head"><h2>Executive summary</h2>'
        '<span class="sec-sub">What matters, in plain English</span></div>'
        f'<ul class="exec">{lis}</ul>'
        "</section>"
    )


def _sov_leaderboard(competitors: Sequence[Mapping[str, Any]]) -> str:
    """Share-of-voice leaderboard rendered as inline <svg> bars.

    Uses inline SVG rather than CSS div bars so the chart survives PDF print
    (no CSS transforms; SVG rects are always rendered by print engines).
    """
    ranked = sorted(competitors, key=lambda c: _num(c.get("sov_pct")), reverse=True)
    ranked = [c for c in ranked if _num(c.get("sov_pct")) > 0] or ranked
    if not ranked:
        return ""
    top = _num(ranked[0].get("sov_pct")) or 1.0

    # SVG layout constants
    bar_h = 16          # bar height px
    row_h = 28          # row height px (bar + spacing)
    label_w = 160       # label column width px
    val_w = 46          # value column width px (right-aligned)
    bar_area_w = 440    # width of the bar track
    svg_w = label_w + bar_area_w + val_w + 16  # total SVG width
    svg_h = len(ranked) * row_h + 4

    rows_svg = []
    for i, c in enumerate(ranked):
        pct = _num(c.get("sov_pct"))
        fill_w = max(2.0, (pct / top) * bar_area_w) if top else 2.0
        y = i * row_h + 4
        name = str(c.get("name") or "")[:22]  # truncate long names for SVG
        rows_svg.append(
            f'<text x="{label_w - 6}" y="{y + bar_h - 3}" '
            f'text-anchor="end" font-size="12" fill="#004737" '
            f'font-family="Montserrat,sans-serif">{_esc(name)}</text>'
            f'<rect x="{label_w}" y="{y}" width="{bar_area_w}" height="{bar_h}" '
            f'rx="8" fill="#f0fdf7" stroke="#e5e5e5" stroke-width="1"/>'
            f'<rect x="{label_w}" y="{y}" width="{fill_w:.1f}" height="{bar_h}" '
            f'rx="8" fill="#0f8a5f"/>'
            f'<text x="{label_w + bar_area_w + 8}" y="{y + bar_h - 3}" '
            f'font-size="12" font-weight="600" fill="#004737" '
            f'font-family="Montserrat,sans-serif">{pct:.1f}%</text>'
        )

    svg_chart = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{svg_w}" height="{svg_h}" '
        f'style="width:100%;max-width:{svg_w}px;overflow:visible" '
        f'role="img" aria-label="Share-of-voice bar chart">'
        + "".join(rows_svg)
        + "</svg>"
    )

    return (
        '<section class="zen-section">'
        '<div class="sec-head"><h2>Share-of-voice leaderboard</h2>'
        '<span class="sec-sub">Estimated share of scanned ad volume</span></div>'
        f'<div style="overflow-x:auto">{svg_chart}</div>'
        "</section>"
    )


def _momentum_board(competitors: Sequence[Mapping[str, Any]]) -> str:
    if not competitors:
        return ""
    cells = []
    for c in competitors:
        status = str(c.get("momentum_status") or "unknown").lower()
        label, cls = _MOMENTUM_META.get(status, _MOMENTUM_META["unknown"])
        cells.append(
            '<div class="momentum-cell">'
            f'<span class="mc-name">{_name_link(c)}</span>'
            f'<span class="chip {cls}">{_esc(label)}</span>'
            "</div>"
        )
    return (
        '<section class="zen-section">'
        '<div class="sec-head"><h2>Momentum board</h2>'
        '<span class="sec-sub">new / ramping = building &middot; cooling = slowing &middot; '
        'dark / unknown = no signal</span></div>'
        f'<div class="momentum-grid">{"".join(cells)}</div>'
        "</section>"
    )


def _field_format_summary(dist: Any) -> str:
    """Field-wide creative-format distribution summary (one stacked bar).

    Reads the report-level ``field_format_distribution`` dict. Returns "" when
    absent so older callers/data still render fine.
    """
    if not dist or not isinstance(dist, Mapping):
        return ""
    total = sum(int(_num(dist.get(k))) for k, _ in _FORMAT_ORDER)
    if total <= 0:
        return ""
    segs = []
    for key, label in _FORMAT_ORDER:
        count = int(_num(dist.get(key)))
        if count <= 0:
            continue
        width = count / total * 100.0
        segs.append(
            f'<div class="fmt-seg" style="width:{width:.2f}%;background:{_FORMAT_COLORS[key]}" '
            f'title="{_esc(label)}: {count}"></div>'
        )
    return (
        '<div class="fmt-row" style="margin-bottom:.6rem">'
        '<div class="lbl" style="font-weight:600">Whole field</div>'
        f'<div class="fmt-bar">{"".join(segs)}</div>'
        f'<div class="cnt tnum">{total}</div>'
        "</div>"
    )


def _format_mix(data: Mapping[str, Any]) -> str:
    competitors = list(data.get("competitors", []) or [])
    if not competitors:
        return ""
    legend = "".join(
        f'<span class="lg"><span class="sw" style="background:{_FORMAT_COLORS[key]}"></span>{_esc(label)}</span>'
        for key, label in _FORMAT_ORDER
    )
    field_summary = _field_format_summary(data.get("field_format_distribution"))
    rows = []
    for c in competitors:
        formats = c.get("formats") or {}
        total = sum(int(_num(formats.get(k))) for k, _ in _FORMAT_ORDER)
        name = _esc(c.get("name"))
        name_html = _name_link(c)
        if total <= 0:
            rows.append(
                '<div class="fmt-row">'
                f'<div class="lbl" title="{name}">{name_html}</div>'
                '<div class="empty">no format data</div>'
                '<div class="cnt tnum">0</div>'
                "</div>"
            )
            continue
        segs = []
        for key, label in _FORMAT_ORDER:
            count = int(_num(formats.get(key)))
            if count <= 0:
                continue
            width = count / total * 100.0
            segs.append(
                f'<div class="fmt-seg" style="width:{width:.2f}%;background:{_FORMAT_COLORS[key]}" '
                f'title="{_esc(label)}: {count}"></div>'
            )
        rows.append(
            '<div class="fmt-row">'
            f'<div class="lbl" title="{name}">{name_html}</div>'
            f'<div class="fmt-bar">{"".join(segs)}</div>'
            f'<div class="cnt tnum">{total}</div>'
            "</div>"
        )
    return (
        '<section class="zen-section">'
        '<div class="sec-head"><h2>Format mix</h2>'
        '<span class="sec-sub">Creative formats per advertiser on this keyword</span></div>'
        f'<div class="fmt-legend">{legend}</div>'
        f'<div class="fmt-rows">{field_summary}{"".join(rows)}</div>'
        "</section>"
    )


def _reach_section(competitors: Sequence[Mapping[str, Any]]) -> str:
    if not competitors:
        return ""
    rows = []
    for c in competitors:
        low = c.get("reach_low")
        high = c.get("reach_high")
        rng = _fmt_reach(low, high)
        conf = _reach_confidence(c.get("impression_data_coverage"))
        rng_cls = "rng" if (low is not None or high is not None) else "rng val-unknown"
        rows.append(
            '<div class="reach-row">'
            f'<div class="lbl">{_name_link(c)}</div>'
            f'<div class="{rng_cls} tnum">{_esc(rng)}</div>'
            f'<div class="conf">{_esc(conf)}</div>'
            "</div>"
        )
    return (
        '<section class="zen-section">'
        '<div class="sec-head"><h2>Estimated reach (times shown)</h2>'
        '<span class="sec-sub">Estimated ranges &middot; never a single fabricated number</span></div>'
        f'<p class="reach-explainer">{_esc(_REACH_EXPLAINER)}</p>'
        f'<div class="reach-rows">{"".join(rows)}</div>'
        "</section>"
    )


def _coverage_badge(coverage: Optional[str]) -> str:
    cov = _fmt_coverage(coverage)
    cls = {"full": "badge-cov-full", "partial": "badge-cov-partial"}.get(cov, "badge-cov-none")
    label = {
        "full": "full visibility",
        "partial": "partial visibility",
        "none": "limited visibility",
    }.get(cov, "limited visibility")
    return f'<span class="badge {cls}">{_esc(label)}</span>'


def _bool_cell(value: Optional[bool]) -> str:
    label = _fmt_bool(value)
    cls = {"yes": "val-yes", "no": "val-no", "unknown": "val-unknown"}[label]
    return f'<span class="{cls}">{label}</span>'


def _text_cell(value: Optional[str]) -> str:
    label = _fmt_text(value)
    if label == UNKNOWN:
        return f'<span class="val-unknown">{UNKNOWN}</span>'
    return _esc(label)


def _sig(key: str, value_html: str) -> str:
    """One labelled signal cell inside a competitor card."""
    return f'<div class="sig"><div class="k">{key}</div><div class="v">{value_html}</div></div>'


def _unknown_html() -> str:
    return f'<span class="val-unknown">{UNKNOWN}</span>'


def _text_or_unknown(value: Optional[str]) -> str:
    """Escaped text, or the italic 'unknown' marker when None/empty."""
    if value is None or str(value).strip() == "":
        return _unknown_html()
    return _esc(value)


def _int_or_unknown(value: Optional[int]) -> str:
    if value is None:
        return _unknown_html()
    return f'<span class="tnum">{_fmt_int(value)}</span>'


def _reach_range_html(c: Mapping[str, Any]) -> str:
    """Reach as an honest RANGE or 'not available' - never a point number."""
    low, high = c.get("reach_low"), c.get("reach_high")
    rng = _fmt_reach(low, high)
    if low is None and high is None:
        return f'<span class="val-unknown">{_esc(rng)}</span>'
    return f'<span class="tnum">{_esc(rng)}</span>'


def _geo_split_html(c: Mapping[str, Any]) -> str:
    """Where an advertiser runs: a plain regions/countries split.

    Prefers an explicit ``geo_summary`` string; otherwise builds one from
    ``top_regions`` (a list of {"region"/"country": str, "pct": number}).
    Limited-visibility advertisers (no data) render "not available".
    Region/country names are shown plainly - no source or framework names.
    """
    summary = c.get("geo_summary")
    if summary and str(summary).strip():
        return _esc(summary)

    regions = c.get("top_regions")
    if regions and isinstance(regions, (list, tuple)):
        parts = []
        for r in regions:
            if not isinstance(r, Mapping):
                continue
            place = str(r.get("region") or r.get("country") or "").strip()
            if not place:
                continue
            pct = r.get("pct")
            if pct is not None:
                parts.append(f"{_esc(place)} {_fmt_pct(pct)}")
            else:
                parts.append(_esc(place))
        if parts:
            return ", ".join(parts)

    return f'<span class="val-unknown">not available</span>'


def _primary_eu_market_html(market: Any) -> str:
    """Render primary_eu_market {country, share_pct, caveat} or 'unknown'."""
    if not market or not isinstance(market, Mapping):
        return _unknown_html()
    country = str(market.get("country") or "").strip()
    if not country:
        return _unknown_html()
    share = market.get("share_pct")
    parts = [_esc(country)]
    if share is not None:
        parts.append(f"({_fmt_pct(share)})")
    caveat = market.get("caveat")
    txt = " ".join(parts)
    if caveat and str(caveat).strip():
        txt += f' <span class="muted">- {_esc(caveat)}</span>'
    return txt


def _competitor_badges(c: Mapping[str, Any]) -> str:
    """Small badges for long-runner / ABM / targeting flags (only when known-true)."""
    badges = []
    if c.get("is_long_runner") is True:
        badges.append('<span class="chip chip-accent">Long-runner (&gt;90d)</span>')
    if c.get("targets_specific_companies") is True:
        badges.append('<span class="chip chip-accent">Account-based</span>')
    if c.get("targets_job_roles") is True:
        badges.append('<span class="chip chip-muted">Targets job roles</span>')
    if c.get("uses_retargeting") is True:
        badges.append('<span class="chip chip-muted">Retargeting</span>')
    if not badges:
        return ""
    return f'<div class="cc-badges">{"".join(badges)}</div>'


def _competitor_card(c: Mapping[str, Any]) -> str:
    """Rich per-competitor card with progressive disclosure.

    Default (surfaced) view shows: advertising now, activity level, SoV,
    format mix, momentum - enough to make a quick call.

    ABM-depth detail (reach scale/ranges, geo split, targeting posture,
    longevity/cadence) lives inside a <details> block - present but not in
    the way unless the reader wants it.

    Tier N fields (agency_run, formats/diversity, maturity, ads-on-keyword,
    advertiser_url) ALWAYS render, so US-only (coverage="none") rows are rich,
    not empty. Tier S/T fields render "unknown" when None - never "no"/"0".
    """
    coverage = _fmt_coverage(c.get("impression_data_coverage"))

    # --- Compact default view: activity + format mix + momentum ---
    default_sigs = [
        _sig("Advertising now", _bool_cell(c.get("is_currently_advertising"))),
        _sig("Momentum", _text_or_unknown(_momentum_text(c.get("momentum_status")))),
        _sig("Share-of-voice", _esc(f"{_num(c.get('sov_pct')):.1f}%")),
        _sig("Formats used", _fmt_ad_types(c.get("ad_types_used"))),
        _sig("Run by", _esc(_agency_label(c.get("agency_run")))),
        _sig("Ads on keyword", _int_or_unknown(c.get("n_ads_on_keyword"))),
    ]
    payer = c.get("ad_payer_name")
    if c.get("agency_run") and payer:
        default_sigs.append(_sig("Paid for by", _esc(payer)))

    # --- ABM depth: Tier S + Tier T - inside <details> ---
    depth_sigs = [
        # Tier S - reach and cadence
        _sig("Estimated reach (times shown)", _reach_range_html(c)),
        _sig("Reach band", _esc_or_unknown(_fmt_reach_tier(c.get("reach_tier")))),
        _sig("Reach confidence", _esc(_reach_confidence(coverage))),
        _sig("Ad longevity (days)", _int_or_unknown(c.get("ad_longevity_days"))),
        _sig("Cadence", _esc_or_unknown(_fmt_cadence(c.get("cadence_shape")))),
        _sig("Where they advertise", _geo_split_html(c)),
        _sig("Primary market", _primary_eu_market_html(c.get("primary_eu_market"))),
        _sig("Outreach timing score", _int_or_unknown(c.get("outreach_timing_score"))),
        # Tier T - targeting posture
        _sig("Targeting posture", _text_or_unknown(c.get("funnel_stage"))),
        _sig("Targets specific companies (ABM)", _bool_cell(c.get("targets_specific_companies"))),
        _sig("Targets job roles", _bool_cell(c.get("targets_job_roles"))),
        _sig("Retargeting", _bool_cell(c.get("uses_retargeting"))),
        _sig("Targeting dimensions", _int_or_unknown(c.get("targeting_dimensions_count"))),
        # Tier N extras
        _sig("Maturity score", f'<span class="tnum">{_fmt_maturity(c.get("linkedin_maturity_score"))}</span>'),
        _sig("Format diversity", _int_or_unknown(c.get("format_diversity_count"))),
    ]

    depth_html = (
        '<details style="margin-top:.6rem">'
        '<summary style="cursor:pointer;font-size:.82rem;color:var(--zen-accent);'
        'font-weight:600;list-style:none;display:inline-flex;align-items:center;gap:.35rem">'
        '&#9656; ABM detail</summary>'
        f'<div class="cc-signals" style="margin-top:.5rem">{"".join(depth_sigs)}</div>'
        "</details>"
    )

    see_ads = _see_ads_link(c)
    actions = []
    if see_ads:
        actions.append(see_ads)
    actions_html = (
        f'<div class="cc-actions">{"".join(actions)}</div>' if actions else ""
    )

    return (
        '<div class="comp-card">'
        '<div class="cc-head">'
        '<div class="cc-title">'
        f'<span class="cc-rank">#{_esc(c.get("rank"))}</span>'
        f'<span class="cc-name">{_name_link(c)}</span>'
        f"{_coverage_badge(coverage)}"
        "</div>"
        f"{actions_html}"
        "</div>"
        f"{_competitor_badges(c)}"
        f'<div class="cc-signals">{"".join(default_sigs)}</div>'
        f"{depth_html}"
        f"{_read_line(c.get('read'))}"
        "</div>"
    )


_FREE_TIER_CARD_LIMIT = 5


def _competitor_teaser(n_more: int, keyword: str) -> str:
    """Free-tier teaser card shown after the top-5 full competitor cards."""
    noun = "company" if n_more == 1 else "companies"
    copy = (
        f'<strong>{n_more}</strong> more {noun} are advertising on '
        f'&ldquo;{_esc(keyword)}&rdquo;. ZenABM gives you the full picture: '
        "every keyword, all competitors, and their real ad creative, tracked every "
        "week with alerts - plus which companies are engaging with your own ads, "
        "tied to pipeline and revenue."
    )
    button = _cta_btn("See all competitors", _URL_SIGNUP, kind="primary")
    return (
        '<div class="comp-teaser">'
        f'<p class="teaser-copy">{copy}</p>'
        f"{button}"
        "</div>"
    )


def _detail_table(data: Mapping[str, Any]) -> str:
    """Rich per-competitor detail (cards). Tier N always shown; honest unknowns.

    Free-tier gating: only the top ``_FREE_TIER_CARD_LIMIT`` competitors render as
    full cards; the remainder collapse into a single upgrade teaser card. All
    competitors stay in the data - the gating is display-only.
    """
    competitors = list(data.get("competitors", []) or [])
    keyword = data.get("keyword", "")
    if not competitors:
        cards = f'<p class="val-unknown">No competitors found.</p>'
    else:
        shown = competitors[:_FREE_TIER_CARD_LIMIT]
        n_more = len(competitors) - len(shown)
        card_html = "".join(_competitor_card(c) for c in shown)
        if n_more > 0:
            card_html += _competitor_teaser(n_more, keyword)
        cards = f'<div class="comp-cards">{card_html}</div>'

    n_ind = int(_num(data.get("n_individuals")))
    foot_bits = []
    if n_ind:
        noun = "individual" if n_ind == 1 else "individuals"
        foot_bits.append(
            f"{n_ind} {noun} (running sponsored posts) itemised separately."
        )
    foot_bits.append(
        '&ldquo;unknown&rdquo; means the advertiser has limited visibility - detailed '
        "reach is not publicly available - not that they are inactive. Maturity, "
        "run-by (agency vs in-house) and format mix are always valid, even for "
        "limited-visibility advertisers."
    )
    foot = f'<p class="small muted" style="margin-top:.75rem">{" ".join(foot_bits)}</p>'

    return (
        '<section class="zen-section">'
        '<div class="sec-head"><h2>Competitor detail</h2>'
        '<span class="sec-sub">Top 5 shown; honest &ldquo;unknown&rdquo; where detail is not publicly available</span></div>'
        + cards
        + foot
        + "</section>"
    )


def _thought_leader_ad_url(t: Mapping[str, Any]) -> Optional[str]:
    """The ad to view for a thought-leader: their sample ad, else a name search."""
    sample = t.get("sample_ad_url")
    if sample and str(sample).strip():
        return str(sample)
    return _account_owner_search_url(t.get("name"))


def _thought_leaders_section(data: Mapping[str, Any]) -> str:
    """People's posts that a company paid to promote.

    Each row links the person's name to their profile and a "See the ad" link to
    the ad. Framed as "[Person]'s post, promoted by [Company]" when the payer is
    known; otherwise "promoted post". We do NOT say the person is advertising.
    """
    leaders = [t for t in (data.get("thought_leaders") or []) if isinstance(t, Mapping)]
    if not leaders:
        return ""
    rows = []
    for t in leaders:
        # Name -> the person's profile (advertiser_url is their /in/ slug).
        name_html = _name_link(t)
        promoted_by = str(t.get("promoted_by") or "").strip()
        if promoted_by:
            frame = f"post, promoted by {_esc(promoted_by)}"
        else:
            frame = "promoted post"
        ad_link = _ext_link(_thought_leader_ad_url(t), "See the ad")
        n = t.get("n_ads_on_keyword")
        count = (
            f'<span class="tl-count tnum">{_fmt_int(n)} ad{"" if n == 1 else "s"} on keyword</span>'
            if n is not None else '<span class="tl-count val-unknown">unknown</span>'
        )
        rows.append(
            '<div class="tl-row">'
            '<span class="tl-name">'
            f'{name_html}<span class="tl-frame"> - {frame}</span>'
            "</span>"
            '<span class="tl-meta">'
            f"{count}"
            f'<span class="tl-adlink">{ad_link}</span>'
            "</span>"
            "</div>"
        )
    return (
        '<section class="zen-section">'
        '<div class="sec-head"><h2>Thought-leader ads (people, promoted)</h2>'
        '<span class="sec-sub">A person wrote the post; a company paid to promote it</span></div>'
        f'<div class="tl-list">{"".join(rows)}</div>'
        "</section>"
    )


def _whitespace_section(data: Mapping[str, Any]) -> str:
    """Split closing section into two labelled lists: whitespace + threats."""
    whitespace = [w for w in (data.get("whitespace") or []) if str(w).strip()]
    threats = [t for t in (data.get("threats") or []) if str(t).strip()]
    if not whitespace and not threats:
        return ""

    ws_html = ""
    if whitespace:
        lis = "".join(
            f'<li><span class="opinion-badge">Our read:</span>{_esc(w)}</li>'
            for w in whitespace
        )
        ws_html = (
            '<div><h3>Where you can win</h3>'
            f'<ul class="whitespace">{lis}</ul></div>'
        )

    th_html = ""
    if threats:
        lis = "".join(
            f'<li><span class="opinion-badge">Watch:</span>{_esc(t)}</li>'
            for t in threats
        )
        th_html = (
            '<div><h3>What to watch out for</h3>'
            f'<ul class="threats">{lis}</ul></div>'
        )

    body = (
        f'<div class="split-cols">{ws_html}{th_html}</div>'
        if (ws_html and th_html) else (ws_html + th_html)
    )
    return (
        '<section class="zen-section">'
        '<div class="sec-head"><h2>Where you can win and what to watch</h2>'
        '<span class="sec-sub">Our take, clearly marked - not a hard fact</span></div>'
        f"{body}"
        "</section>"
    )


def _you_vs_them_section(comparison: Mapping[str, Any]) -> str:
    """You-vs-them section rendered when a 'comparison' block is present.

    Renders a progressive-disclosure friendly breakdown covering:
    - Head-to-head: activity (own vs field), format gaps, SOV position
    - Scale vs efficiency: competitor scale vs own CTR/CPC/spend/conversions
    - Moves: 2-4 plain-English actionable next steps (deep numbers in <details>)

    Also accepts the legacy flat format (activity_match / format_gaps / sov /
    moves) so existing callers keep working.

    No emoji.  Hyphens only (not em-dashes).
    """
    head = comparison.get("head_to_head") or {}
    sve = comparison.get("scale_vs_efficiency") or {}
    moves = [str(m).strip() for m in (comparison.get("moves") or []) if str(m).strip()]

    parts: List[str] = []

    # ── Activity ──────────────────────────────────────────────────────────────
    activity = head.get("activity") or {}
    own_serving = activity.get("own_serving_ads")
    own_vs_field = activity.get("own_vs_field")
    comp_entries = activity.get("competitors") or []

    if own_vs_field or own_serving is not None:
        field_summary = ""
        if comp_entries:
            field_n = sum(e.get("n_ads", 0) for e in comp_entries)
            field_summary = f" The field has {field_n} ads combined across {len(comp_entries)} competitor(s)."
        activity_line = ""
        if own_vs_field == "fewer":
            activity_line = (
                f"You are running {own_serving if own_serving is not None else 'an unknown number of'} "
                f"active ad(s) - fewer than the field average.{field_summary}"
            )
        elif own_vs_field == "more":
            activity_line = (
                f"You are running {own_serving if own_serving is not None else 'an unknown number of'} "
                f"active ad(s) - more than the field average.{field_summary}"
            )
        else:
            activity_line = (
                f"You are running {own_serving if own_serving is not None else 'an unknown number of'} "
                f"active ad(s) - in line with the field average.{field_summary}"
            )
        parts.append(f'<p style="margin-bottom:.5rem">{_esc(activity_line)}</p>')

    # ── Format gaps ───────────────────────────────────────────────────────────
    fmt = head.get("formats") or {}
    own_fmts = sorted(str(f) for f in (fmt.get("own_formats") or []))
    comp_only = sorted(str(f) for f in (fmt.get("competitor_only_formats") or []))
    own_only = sorted(str(f) for f in (fmt.get("own_only_formats") or []))

    # Also support legacy flat format (list of strings)
    legacy_gaps = [g for g in (comparison.get("format_gaps") or []) if str(g).strip()]

    if comp_only:
        gap_labels = ", ".join(comp_only)
        parts.append(
            '<p style="font-weight:600;margin:.6rem 0 .25rem">Format gaps:</p>'
            f'<p style="margin:0 0 .4rem">Competitors use formats you do not: '
            f'<strong>{_esc(gap_labels)}</strong>. '
            'Consider testing one of these to close the gap.</p>'
        )
    elif legacy_gaps:
        gap_lis = "".join(f"<li>{_esc(g)}</li>" for g in legacy_gaps)
        parts.append(
            '<p style="font-weight:600;margin:.6rem 0 .25rem">Format gaps:</p>'
            f'<ul style="margin:.1rem 0 .7rem;padding-left:1.4rem">{gap_lis}</ul>'
        )

    if own_only:
        own_labels = ", ".join(own_only)
        parts.append(
            f'<p style="margin:.2rem 0 .5rem;font-size:.88rem;color:var(--zen-muted-fg)">'
            f'You use format(s) no competitor does: <em>{_esc(own_labels)}</em> - a differentiation signal.</p>'
        )

    # ── Share of voice ────────────────────────────────────────────────────────
    sov_data = head.get("share_of_voice") or {}
    own_sov = sov_data.get("own_sov_pct")
    comp_sov_ranking = sov_data.get("competitor_sov_ranking") or []

    # Legacy flat sov string
    legacy_sov = comparison.get("sov")

    if own_sov is not None:
        sov_line = f"Your share-of-voice position in the field: {own_sov:.1f}%."
        if comp_sov_ranking:
            top = comp_sov_ranking[0]
            sov_line += f" The field leader ({_esc(top['name'])}) holds {top.get('sov_pct', 0):.1f}%."
        parts.append(f'<p style="margin-bottom:.5rem">{sov_line}</p>')
    elif legacy_sov:
        parts.append(f'<p style="margin-bottom:.5rem">{_esc(legacy_sov)}</p>')

    # ── Scale vs efficiency ───────────────────────────────────────────────────
    comp_scale = sve.get("competitor_scale") or {}
    own_eff = sve.get("your_efficiency") or {}

    scale_loudest = comp_scale.get("loudest_by_ads")
    reach_low = comp_scale.get("total_reach_low")
    reach_high = comp_scale.get("total_reach_high")
    coverage_none = comp_scale.get("coverage_none_competitors") or []

    ctr = own_eff.get("ctr")
    cpc = own_eff.get("cpc")
    spend = own_eff.get("spend")
    impressions = own_eff.get("impressions")
    conversions = own_eff.get("conversions")

    if scale_loudest or own_eff:
        sve_summary_parts: List[str] = []
        if scale_loudest:
            sve_summary_parts.append(
                f'Field leader by volume: <strong>{_esc(scale_loudest["name"])}</strong> '
                f'({scale_loudest.get("n_ads", 0)} ads).'
            )
        if ctr is not None:
            sve_summary_parts.append(f"Your CTR: {ctr:.2f}%.")
        if cpc is not None:
            sve_summary_parts.append(f"Your CPC: ${cpc:.2f}.")

        sve_summary_html = " ".join(sve_summary_parts)

        # Deep numbers go in a <details> block for progressive disclosure
        depth_rows: List[str] = []
        if impressions is not None:
            depth_rows.append(f"<li>Impressions (last 30 days): {int(impressions):,}</li>")
        if spend is not None:
            depth_rows.append(f"<li>Spend (last 30 days): ${float(spend):,.2f}</li>")
        if conversions is not None:
            depth_rows.append(f"<li>Conversions: {int(conversions):,}</li>")
        if reach_low is not None or reach_high is not None:
            reach_str = _fmt_reach(reach_low, reach_high)
            depth_rows.append(f"<li>Combined field reach (times shown): {_esc(reach_str)}</li>")
        if coverage_none:
            depth_rows.append(
                f"<li>Reach note: {len(coverage_none)} competitor(s) have limited visibility "
                "(reach not publicly available, not zero).</li>"
            )
        if own_only:
            pass  # already shown above

        depth_html = ""
        if depth_rows:
            depth_html = (
                '<details style="margin-top:.4rem">'
                '<summary style="cursor:pointer;font-size:.82rem;color:var(--zen-accent);'
                'font-weight:600;list-style:none;display:inline-flex;align-items:center;gap:.35rem">'
                "&#9656; Efficiency detail</summary>"
                f'<ul style="margin:.4rem 0 .2rem;padding-left:1.4rem;font-size:.85rem">{"".join(depth_rows)}</ul>'
                "</details>"
            )

        parts.append(
            '<div style="margin:.7rem 0 .4rem">'
            f'<p style="font-weight:600;margin-bottom:.25rem">Scale vs efficiency:</p>'
            f'<p style="margin:0 0 .2rem">{sve_summary_html}</p>'
            f"{depth_html}"
            "</div>"
        )

    # ── Moves ─────────────────────────────────────────────────────────────────
    if moves:
        move_lis = "".join(f"<li style='margin:.3rem 0'>{_esc(m)}</li>" for m in moves)
        parts.append(
            '<p style="font-weight:600;margin:.7rem 0 .25rem">Suggested moves:</p>'
            f'<ul style="margin:.1rem 0 .7rem;padding-left:1.4rem">{move_lis}</ul>'
        )

    # ── Legacy activity_match fallback ────────────────────────────────────────
    legacy_activity = comparison.get("activity_match")
    if legacy_activity and not activity:
        parts.insert(0, f'<p style="margin-bottom:.5rem">{_esc(legacy_activity)}</p>')

    if not parts:
        parts.append(
            '<p class="val-unknown">Own-data comparison will appear here once '
            "LinkedIn is connected in ZenABM.</p>"
        )

    body = "".join(parts)
    return (
        '<section class="zen-section">'
        '<div class="sec-head"><h2>You vs them</h2>'
        '<span class="sec-sub">How your advertising compares to the field</span></div>'
        f"{body}"
        "</section>"
    )


def _comparison_upsell_note(data: Mapping[str, Any]) -> str:
    """Subtle one-liner rendered when comparison_upsell is present but no comparison.

    Framed as a warm invitation - never a hard cap or error message.
    """
    upsell = data.get("comparison_upsell")
    if not upsell or not str(upsell).strip():
        return ""
    return (
        '<div class="zen-cta">'
        f'<p class="zen-cta-copy muted" style="font-size:.85rem">{_esc(upsell)}</p>'
        "</div>"
    )


def _method_section(data: Mapping[str, Any]) -> str:
    note = data.get("method_note")
    if not note or not str(note).strip():
        return ""
    return (
        '<section class="zen-section">'
        '<div class="sec-head"><h2>Method &amp; coverage note</h2></div>'
        f'<div class="method-note">{_esc(note)}</div>'
        "</section>"
    )


def _upgrade_footer(data: Mapping[str, Any]) -> str:
    """CTA E (footer, strong): dual buttons + a small text link, on-brand copy.

    Retains the v1 gradient 'upgrade' panel; renders the optional upgrade_teaser
    above the strong CTA when present.
    """
    teaser = data.get("upgrade_teaser")
    teaser_html = (
        f"<p>{_esc(teaser)}</p>" if teaser and str(teaser).strip() else ""
    )
    cta_copy = (
        "ZenABM shows which companies are engaging with your ads, even the ones you "
        "cannot name yet, and ties that to real pipeline and revenue. It runs your "
        "account-based campaigns and gives you the full competitor picture: every "
        "keyword, all competitors, their real ad creative, tracked every week with "
        "alerts."
    )
    buttons = (
        _cta_btn("Start free", _URL_SIGNUP, kind="primary")
        + _cta_btn("Book a demo", _URL_DEMO, kind="secondary")
    )
    textlink = _cta_textlink("zenabm.com", _URL_HOME)
    return (
        '<section class="upgrade">'
        "<h2>Go deeper with ZenABM</h2>"
        f"{teaser_html}"
        f'<p style="margin-top:.6rem">{_esc(cta_copy)}</p>'
        '<div style="display:flex;flex-wrap:wrap;gap:.6rem;align-items:center;margin-top:.9rem">'
        f"{buttons}"
        f'<span style="margin-left:.15rem">{textlink}</span>'
        "</div>"
        "</section>"
    )


# --------------------------------------------------------------------------- #
# Combined multi-keyword report: per-keyword section + roll-up                 #
# --------------------------------------------------------------------------- #
def _keyword_scope_line(kw: Mapping[str, Any]) -> str:
    """The compact per-keyword scope line (total matching + ads scanned).

    In the combined report the free-tier note is rendered once at the top, so the
    per-keyword block only needs this short "how much we looked at" line.
    """
    total = _fmt_int(kw.get("total_matching_ads"))
    scanned = _fmt_int(kw.get("n_ads_scanned"))
    geo = _esc(kw.get("geographies", "")) or "Global"
    return (
        '<p class="kw-scope-line">'
        f'<span class="tnum">{total}</span> matching ads &middot; '
        f'top <span class="tnum">{scanned}</span> scanned &middot; {geo}'
        "</p>"
    )


def _render_keyword_section(kw: Mapping[str, Any]) -> str:
    """Render ONE keyword's block for the combined multi-keyword report.

    Contains, top to bottom: the keyword title + scope line (total matching +
    ads scanned), the share-of-voice leaderboard (top 5), the top-5 competitor
    cards + "N more" teaser + the mid-report CTA, the format-mix and reach geo
    views, the per-keyword "Where you can win" / "What to watch out for", and the
    thought-leader ads.

    Every section reuses the exact single-keyword builders, so honest rendering,
    branding, gating and links are identical to the single-keyword report.
    """
    kw = kw or {}
    competitors: List[Mapping[str, Any]] = list(kw.get("competitors", []) or [])
    title = _esc(kw.get("keyword", ""))

    parts = [
        '<div class="kw-block">',
        f'<h2 class="kw-title">Advertising on &ldquo;{title}&rdquo;</h2>',
        _keyword_scope_line(kw),
        "</div>",
        _sov_leaderboard(competitors),     # top 5 + CTA B
        _detail_table(kw),                 # top-5 cards + "N more" teaser + mid CTA
        _format_mix(kw),                   # per-advertiser creative mix
        _reach_section(competitors),       # estimated reach (times shown)
        _whitespace_section(kw),           # per-keyword win / watch
        _thought_leaders_section(kw),      # people, promoted
    ]
    return "\n".join(p for p in parts if p)


def _combined_header(data: Mapping[str, Any]) -> str:
    """Header for the combined report: wordmark + the scanned keywords + date."""
    keywords = [str(k.get("keyword", "")).strip()
                for k in (data.get("keywords") or []) if isinstance(k, Mapping)]
    keywords = [k for k in keywords if k]
    joined = ", ".join(keywords) if keywords else ""
    generated = _esc(data.get("generated_at", ""))
    return (
        '<header class="zen-header">'
        + _ZENABM_LOGO_SVG
        + '<div class="head-text" style="flex:1;min-width:0">'
        + f'<h1>Competitor scan: <span class="kw">{_esc(joined)}</span></h1>'
        + f'<div class="head-sub">Multi-keyword competitor scan &middot; generated {generated}</div>'
        + "</div>"
        + '<div class="head-actions" style="flex:0 0 auto;margin-left:auto">'
        + _download_pdf_btn()
        + "</div>"
        + "</header>"
    )


def _combined_free_tier_bar(data: Mapping[str, Any]) -> str:
    """The single free-tier note line (rendered once, at the top)."""
    note = data.get("free_tier_note")
    if not note or not str(note).strip():
        return ""
    return (
        '<div class="zen-scope">'
        '<div class="free-tier-line">'
        '<span class="cov-k">Free version:</span> '
        f"{_esc(note)}"
        "</div>"
        "</div>"
    )


def _cross_keyword_summary(data: Mapping[str, Any]) -> str:
    """Lead exec summary across all themes (Zena-authored) -> "What matters"."""
    bullets = [b for b in (data.get("cross_keyword_summary") or []) if str(b).strip()]
    if not bullets:
        return ""
    lis = "".join(f"<li>{_esc(b)}</li>" for b in bullets)
    return (
        '<section class="zen-section">'
        '<div class="sec-head"><h2>What matters across your themes</h2>'
        '<span class="sec-sub">The big picture, in plain English</span></div>'
        f'<ul class="exec">{lis}</ul>'
        "</section>"
    )


def _kw_divider(index: int, keyword: str) -> str:
    """A clear divider announcing the next keyword block."""
    return (
        '<div class="kw-divider">'
        f'<span class="kw-chip"><span class="kw-idx">Theme {index}</span>'
        f'{_esc(keyword)}</span>'
        "</div>"
    )


def _cross_theme_rivals(data: Mapping[str, Any]) -> str:
    """Roll-up of competitors that advertise on 2+ of the scanned themes.

    Each rival's name is linked to its advertiser_url; the row shows which themes
    it appears on and the theme count. An empty list renders a neutral note.
    Closes with a ZenABM CTA to track all rivals across themes.
    """
    rivals = [r for r in (data.get("cross_theme_rivals") or []) if isinstance(r, Mapping)]
    intro = (
        '<p class="rivals-intro">These companies advertise on more than one of your '
        "themes - they are your biggest overall rivals.</p>"
    )
    if not rivals:
        body = (
            intro
            + '<div class="rivals-empty">No company advertises across more than one '
            "of these themes yet.</div>"
        )
    else:
        # Most-cross-cutting first, so the widest-spanning rival leads.
        rivals = sorted(rivals, key=lambda r: int(_num(r.get("n_keywords"))), reverse=True)
        rows = []
        for r in rivals:
            name_html = _ext_link(r.get("advertiser_url"), r.get("name") or "")
            themes = [str(t).strip() for t in (r.get("keywords") or []) if str(t).strip()]
            themes_txt = ", ".join(themes)
            n = int(_num(r.get("n_keywords"))) or len(themes)
            rows.append(
                '<div class="rival-row">'
                '<span class="rv-name">'
                f'{name_html}<span class="rv-themes"> - {_esc(themes_txt)}</span>'
                "</span>"
                f'<span class="rv-count">{n} themes</span>'
                "</div>"
            )
        body = intro + f'<div class="rival-list">{"".join(rows)}</div>'

    cta = _cta(
        "A rival on several of your themes at once is worth watching closely. ZenABM "
        "keeps an eye on all of them for you and flags the moment one moves onto a new "
        "theme.",
        primary=_cta_btn("Track rivals across themes", _URL_SIGNUP, kind="primary"),
    )
    return (
        '<section class="zen-section">'
        '<div class="sec-head"><h2>Who shows up across your themes</h2>'
        '<span class="sec-sub">Rivals advertising on more than one theme</span></div>'
        f"{body}"
        f"{cta}"
        "</section>"
    )


# --------------------------------------------------------------------------- #
# Public API                                                                  #
# --------------------------------------------------------------------------- #
def build_report_html(report_data: Dict[str, Any]) -> str:
    """Render ``report_data`` (a plain dict) to a complete, self-contained HTML doc.

    Returns a full ``<!doctype html> ... </html>`` string with all CSS inlined,
    no external resources, safe to open offline and under a strict CSP.
    """
    data: Mapping[str, Any] = report_data or {}
    competitors: List[Mapping[str, Any]] = list(data.get("competitors", []) or [])
    keyword = _esc(data.get("keyword", ""))

    comparison = data.get("comparison")
    you_vs_them = _you_vs_them_section(comparison) if isinstance(comparison, Mapping) else ""

    body_sections = [
        _header(data),
        _scope_bar(data),
        _exec_summary(data),
        _sov_leaderboard(competitors),
        _momentum_board(competitors),
        _format_mix(data),
        _detail_table(data),
        you_vs_them,                       # conditional: only when comparison key present
        _reach_section(competitors),
        _thought_leaders_section(data),
        _whitespace_section(data),
        _method_section(data),
        _upgrade_footer(data),             # CTA E: strong footer
        '<div class="page-foot">Generated by ZenABM &middot; built from public advertising '
        "activity &middot; figures are estimates, not billing-grade.</div>",
    ]

    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>Competitors advertising on “{keyword}” - ZenABM</title>\n"
        '<meta name="description" content="ZenABM keyword competitor scan report.">\n'
        f"<style>\n{_STYLE}\n</style>\n"
        "</head>\n"
        "<body>\n"
        '<main class="zen-page">\n'
        + "\n".join(s for s in body_sections if s)
        + "\n</main>\n"
        "</body>\n"
        "</html>\n"
    )


def write_report(report_data: Dict[str, Any], path: str) -> str:
    """Build the report and write it to ``path`` (UTF-8). Returns ``path``."""
    html_doc = build_report_html(report_data)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html_doc)
    return path


def build_combined_report_html(data: Dict[str, Any]) -> str:
    """Render a COMBINED multi-keyword report (up to 3 keywords) to one HTML doc.

    Consumes the combined data contract (see module docstring / task spec):
    ``generated_at``, ``geographies``, ``free_tier_note``, ``cross_keyword_summary``,
    ``keywords`` (1-3 per-keyword dicts in the single-keyword shape),
    ``cross_theme_rivals``, ``method_note`` and ``upgrade_teaser``.

    Layout, top to bottom:
      1. Header (wordmark + scanned keywords + date + free-tier note).
      2. "What matters across your themes" (the lead cross-keyword summary).
      3. For each keyword: a divider + :func:`_render_keyword_section`.
      4. "Who shows up across your themes" (cross-theme rivals roll-up + CTA).
      5. Method & coverage note.
      6. Footer CTA (ZenABM value prop).

    Returns a full, self-contained ``<!doctype html> ... </html>`` string (all CSS
    inlined, no external resources), safe offline and under a strict CSP.
    """
    data: Mapping[str, Any] = data or {}
    keywords = [k for k in (data.get("keywords") or []) if isinstance(k, Mapping)]

    kw_titles = [str(k.get("keyword", "")).strip() for k in keywords]
    kw_titles = [t for t in kw_titles if t]
    title_join = ", ".join(kw_titles) if kw_titles else "your themes"

    kw_blocks = []
    for i, kw in enumerate(keywords, start=1):
        kw_blocks.append(_kw_divider(i, kw.get("keyword", "")))
        kw_blocks.append(_render_keyword_section(kw))

    comparison = data.get("comparison")
    you_vs_them = _you_vs_them_section(comparison) if isinstance(comparison, Mapping) else ""

    # Subtle upsell note when own data is not connected (plan/auth gate).
    upsell_note = _comparison_upsell_note(data) if not comparison else ""

    body_sections = [
        _combined_header(data),
        _combined_free_tier_bar(data),
        _cross_keyword_summary(data),      # the lead "What matters" list
        *kw_blocks,                        # per-keyword divider + section
        _cross_theme_rivals(data),         # roll-up + CTA
        you_vs_them,                       # conditional: only when comparison key present
        upsell_note,                       # subtle note when comparison not available
        _method_section(data),
        _upgrade_footer(data),             # strong footer CTA
        '<div class="page-foot">Generated by ZenABM &middot; built from public advertising '
        "activity &middot; figures are estimates, not billing-grade.</div>",
    ]

    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>Competitor scan: {_esc(title_join)} - ZenABM</title>\n"
        '<meta name="description" content="ZenABM combined multi-keyword competitor scan report.">\n'
        f"<style>\n{_STYLE}\n</style>\n"
        "</head>\n"
        "<body>\n"
        '<main class="zen-page">\n'
        + "\n".join(s for s in body_sections if s)
        + "\n</main>\n"
        "</body>\n"
        "</html>\n"
    )


def write_combined_report(data: Dict[str, Any], path: str) -> str:
    """Build the combined report and write it to ``path`` (UTF-8). Returns ``path``."""
    html_doc = build_combined_report_html(data)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html_doc)
    return path

"""Realistic sample ``report_data`` dict (v4) for the keyword-competitor renderer.

Mirrors the shape produced by skill-01 (``projects/skill-01-keyword-competitors``)
for a "product analytics" keyword scan. It is intentionally hand-crafted so the
renderer can be exercised and eyeballed without any live data fetch.

v3 richness (same theme, same company set for continuity):
  * 8 full-visibility companies (ClickHouse leader + long-runner + ramping, IQVIA,
    SeoProfy, SQUAD, Uncountable, ChannelSight cooling, Bolt, Senswise) - populated
    reach ranges/bands, momentum, ad_longevity/is_long_runner on a few,
    account-based/targeting flags on some, cadence, disclosed share, primary
    market, and a per-competitor ``read``.
  * 5 limited-visibility companies (``coverage: "none"``: Heretto, CS Analytical,
    Storylane, Definitive Healthcare, RxLogix) that are still RICH via Tier N
    (agency vs in-house, formats + format_diversity_count, maturity <n>/10,
    ads-on-keyword, advertiser_url, a ``read`` that leans on what IS known) - with
    "unknown" ONLY on the genuinely-gated Tier S/T fields.
  * Heretto (limited visibility) is deliberately ranked into the TOP 5 with a high
    ad count, so the freemium view still surfaces a rich limited-visibility card.
  * 5 itemised ``thought_leaders``.
  * Report-level: coverage_breakdown, pct_us_only, field_format_distribution,
    n_agency_run, n_long_runners, split whitespace[] + threats[].

v4 changes (same theme, same company set):
  * All advertiser name links resolve to the RIGHT company: verified real
    ``/company/<slug>`` where confirmed, else a global advertiser search by name.
  * Every advertiser has a "where they advertise" geo split (top_regions /
    geo_summary) for full-visibility rows; limited-visibility rows show
    "not available".
  * Thought-leaders are reframed as people's posts a company paid to promote:
    each has ``promoted_by`` (payer, or None) and a ``sample_ad_url``.
  * Plainer, shorter, 5th-grade copy in the summary + openings/watch lists.
  * n_ads_scanned set to the free-tier cap (200 ads scanned per keyword).

Honest-rendering invariants this sample exercises (see CLAUDE.md hard-rule #2):
  * Tier S/T ``None`` -> renders the literal "unknown", never "no"/"0".
  * ``linkedin_maturity_score`` is a Tier N signal: ALWAYS a real number -> "<n>/10".
  * Tier N ``agency_run`` and ``format_diversity_count`` ALWAYS render, so the
    limited-visibility rows are rich rather than empty.
  * No competitor spend/CTR/clicks anywhere. Reach is a RANGE or "not available".

This module is import-light (a single dict literal); it does NOT import the
renderer, so importing it never pulls in report generation.
"""
from __future__ import annotations

from typing import Any, Dict

SAMPLE: Dict[str, Any] = {
    "keyword": "product analytics",
    "geographies": "Global",
    "total_matching_ads": 57109,
    "n_ads_scanned": 200,
    "n_individuals": 5,
    "generated_at": "2026-07-06",

    # ---- v2 report-level additions ----
    "coverage_breakdown": {"full": 8, "partial": 0, "none": 5},
    "pct_us_only": 38.5,
    "field_format_distribution": {
        "video": 2, "single_image": 12, "carousel": 4, "document": 3, "message": 0,
    },
    "n_agency_run": 4,
    "n_thought_leaders": 5,
    "n_currently_advertising": 8,
    "n_long_runners": 2,
    "thought_leaders": [
        {"name": "Amanda Natividad", "advertiser_url": "https://www.linkedin.com/in/amandanat",
         "n_ads_on_keyword": 2, "promoted_by": "SparkToro",
         "sample_ad_url": "https://www.linkedin.com/ad-library/detail/691234520"},
        {"name": "Emily Kramer", "advertiser_url": "https://www.linkedin.com/in/emilyckramer",
         "n_ads_on_keyword": 1, "promoted_by": "MKT1",
         "sample_ad_url": "https://www.linkedin.com/ad-library/detail/691234521"},
        {"name": "Wes McKinney", "advertiser_url": "https://www.linkedin.com/in/wesmckinn",
         "n_ads_on_keyword": 1, "promoted_by": None,
         "sample_ad_url": "https://www.linkedin.com/ad-library/detail/691234522"},
        {"name": "April Dunford", "advertiser_url": "https://www.linkedin.com/in/aprildunford",
         "n_ads_on_keyword": 1, "promoted_by": "Pendo",
         "sample_ad_url": "https://www.linkedin.com/ad-library/detail/691234523"},
        {"name": "Peep Laja", "advertiser_url": "https://www.linkedin.com/in/peeplaja",
         "n_ads_on_keyword": 1, "promoted_by": "Wynter",
         "sample_ad_url": None},
    ],

    "exec_summary": [
        # PURE INSIGHT - no ZenABM plugs. Short words, short sentences, 5th-grade
        # English, expert substance. Each line links signals into one sharp read.
        "ClickHouse is the one to beat. They run the most ads here, keep winners live "
        "past four months, retarget, and name their target accounts. That is a proven, "
        "always-on program, not a test. Study their creative before you brief yours; "
        "out-angle them, do not out-spend them.",
        "IQVIA runs their ads through an agency and aims at a set list of companies, "
        "not the broad market. That is an account-based push - likely chasing the same "
        "named buyers you want. Agencies are slower to change, so a sharp direct offer "
        "can move faster than they can react.",
        "SeoProfy is a brand-new, funded push - it went from no ads to live in one "
        "month, still one plain picture only. That is an early test with no set message "
        "yet. This is your window to say something sharper first, while it is cheap.",
        "The whole field runs on one plain picture. Almost no one uses video, and only "
        "one advertiser runs how-to (document) ads. Teaching ads build trust cheaply. "
        "One good how-to here would stand out fast and own a lane nobody is fighting "
        "for.",
        "Five people have posts here that a company paid to boost. Real people, not "
        "just brands, carry this topic - so a trusted voice backing your message would "
        "land harder than another company logo.",
    ],

    "competitors": [
        # ------------------------------------------------------------------ #
        # Top 5 (freemium view). Ranks 1-3 + 5 have full visibility; rank 4  #
        # (Heretto) is limited visibility but ranked in via a high ad count. #
        # ------------------------------------------------------------------ #
        {
            "rank": 1, "name": "ClickHouse", "company_id": "18538494",
            "advertiser_type": "company",
            "advertiser_url": "https://www.linkedin.com/company/clickhouseinc",
            "n_ads_on_keyword": 3,
            "impression_data_coverage": "full",
            # Tier N (always shown)
            "linkedin_maturity_score": 8,
            "ad_types_used": ["Video", "Single image"],
            "format_diversity_count": 2,
            "agency_run": False, "ad_payer_name": None,
            "formats": {"video": 1, "single_image": 2, "carousel": 0, "document": 0, "message": 0},
            # Tier S
            "is_currently_advertising": True,
            "momentum_status": "ramping",
            "outreach_timing_score": 9,
            "reach_low": 50000, "reach_high": 100000,
            "reach_tier": "enterprise", "reach_confidence": "higher confidence",
            "ad_longevity_days": 128, "is_long_runner": True,
            "cadence_shape": "steady",
            "eu_disclosed_share_pct": 62.0,
            "primary_eu_market": {"country": "Germany", "share_pct": 24.0,
                                  "caveat": "of disclosed impressions"},
            "top_regions": [{"country": "United States", "pct": 41.0},
                            {"country": "Germany", "pct": 24.0},
                            {"country": "United Kingdom", "pct": 14.0}],
            "geo_summary": "Mostly United States and Germany, some United Kingdom",
            "sov_pct": 33.4,
            # Tier T
            "funnel_stage": "consideration",
            "targets_specific_companies": True, "targets_job_roles": True,
            "uses_retargeting": True, "targeting_dimensions_count": 4,
            "read": "Most ads on the theme, several live 90+ days, still ramping, plus "
                    "retargeting and named-account targeting - a proven, always-on "
                    "program that has found what works. Study their creative before you "
                    "brief yours; out-angle, do not out-spend.",
            "sample_ad_url": "https://www.linkedin.com/ad-library/detail/691234501",
        },
        {
            "rank": 2, "name": "IQVIA Commercial Solutions", "company_id": "163076",
            "advertiser_type": "company",
            "advertiser_url": "https://www.linkedin.com/company/iqvia",
            "n_ads_on_keyword": 2,
            "impression_data_coverage": "full",
            "linkedin_maturity_score": 7,
            "ad_types_used": ["Single image", "Carousel"],
            "format_diversity_count": 2,
            "agency_run": True, "ad_payer_name": "Merkle B2B",
            "formats": {"video": 0, "single_image": 1, "carousel": 1, "document": 0, "message": 0},
            "is_currently_advertising": True,
            "momentum_status": "steady",
            "outreach_timing_score": 6,
            "reach_low": 25000, "reach_high": 50000,
            "reach_tier": "large", "reach_confidence": "higher confidence",
            "ad_longevity_days": 74, "is_long_runner": False,
            "cadence_shape": "steady",
            "eu_disclosed_share_pct": 55.0,
            "primary_eu_market": {"country": "France", "share_pct": 19.0,
                                  "caveat": "of disclosed impressions"},
            "top_regions": [{"country": "United States", "pct": 45.0},
                            {"country": "France", "pct": 19.0},
                            {"country": "United Kingdom", "pct": 12.0}],
            "geo_summary": "Mostly United States, then France and United Kingdom",
            "sov_pct": 18.9,
            "funnel_stage": "mixed",
            "targets_specific_companies": True, "targets_job_roles": True,
            "uses_retargeting": False, "targeting_dimensions_count": 3,
            "read": "Agency-run and aimed at a named list of companies, not the broad "
                    "market - an account-based motion likely chasing the same buyers you "
                    "want. Agencies pivot slowly, so a sharp direct offer can out-move "
                    "them before they can react.",
            "sample_ad_url": "https://www.linkedin.com/ad-library/detail/691234502",
        },
        {
            "rank": 3, "name": "SeoProfy", "company_id": "18271011",
            "advertiser_type": "company",
            "advertiser_url": "https://www.linkedin.com/company/seoprofy",
            "n_ads_on_keyword": 1,
            "impression_data_coverage": "full",
            "linkedin_maturity_score": 4,
            "ad_types_used": ["Single image"],
            "format_diversity_count": 1,
            "agency_run": False, "ad_payer_name": None,
            "formats": {"video": 0, "single_image": 1, "carousel": 0, "document": 0, "message": 0},
            "is_currently_advertising": True,
            "momentum_status": "new",
            "outreach_timing_score": 7,
            "reach_low": 10000, "reach_high": 25000,
            "reach_tier": "mid", "reach_confidence": "higher confidence",
            "ad_longevity_days": 21, "is_long_runner": False,
            "cadence_shape": "one-off",
            "eu_disclosed_share_pct": 48.0,
            "primary_eu_market": {"country": "Poland", "share_pct": 31.0,
                                  "caveat": "of disclosed impressions"},
            "top_regions": [{"country": "Poland", "pct": 31.0},
                            {"country": "United States", "pct": 27.0},
                            {"country": "Germany", "pct": 15.0}],
            "geo_summary": "Split across Poland, United States and Germany",
            "sov_pct": 9.7,
            "funnel_stage": "consideration",
            "targets_specific_companies": False, "targets_job_roles": True,
            "uses_retargeting": False, "targeting_dimensions_count": 2,
            "read": "Brand-new, one plain picture, live only three weeks, broad targeting "
                    "- an early test with no locked-in message yet. Set the narrative "
                    "first, while it is cheap; expect them to get louder next month.",
            "sample_ad_url": "https://www.linkedin.com/ad-library/detail/691234503",
        },
        {
            # Limited visibility, but ranked into the top 5 on ad volume so the
            # freemium view still shows a rich limited-visibility card.
            "rank": 4, "name": "Heretto", "company_id": "1656248",
            "advertiser_type": "company",
            "advertiser_url": "https://www.linkedin.com/company/heretto",
            "n_ads_on_keyword": 4,
            "impression_data_coverage": "none",
            # Tier N still fully rendered:
            "linkedin_maturity_score": 6,
            "ad_types_used": ["Single image"],
            "format_diversity_count": 1,
            "agency_run": False, "ad_payer_name": None,
            "formats": {"video": 0, "single_image": 4, "carousel": 0, "document": 0, "message": 0},
            # Tier S -> unknown (genuinely gated):
            "is_currently_advertising": None,
            "momentum_status": "unknown",
            "outreach_timing_score": None,
            "reach_low": None, "reach_high": None,
            "reach_tier": None, "reach_confidence": "not available",
            "ad_longevity_days": None, "is_long_runner": None,
            "cadence_shape": None,
            "eu_disclosed_share_pct": None,
            "primary_eu_market": None,
            "sov_pct": 0.0,
            # Tier T -> unknown:
            "funnel_stage": None,
            "targets_specific_companies": None, "targets_job_roles": None,
            "uses_retargeting": None, "targeting_dimensions_count": None,
            "read": "Four ads but all one plain picture, run in-house - a committed but "
                    "narrow presence. Reach and momentum are not public here, not zero. "
                    "Beatable on creative range: bring video or a how-to and you out-do "
                    "them on the same theme.",
            "sample_ad_url": "https://www.linkedin.com/ad-library/detail/691234509",
        },
        {
            "rank": 5, "name": "SQUAD", "company_id": "10998744",
            "advertiser_type": "company",
            # No verifiable company page for this name -> global advertiser search,
            # which always resolves to the right advertiser by name.
            "advertiser_url": "https://www.linkedin.com/ad-library/search?accountOwner=SQUAD",
            "n_ads_on_keyword": 1,
            "impression_data_coverage": "full",
            "linkedin_maturity_score": 3,
            "ad_types_used": ["Single image"],
            "format_diversity_count": 1,
            "agency_run": False, "ad_payer_name": None,
            "formats": {"video": 0, "single_image": 1, "carousel": 0, "document": 0, "message": 0},
            "is_currently_advertising": True,
            "momentum_status": "steady",
            "outreach_timing_score": 5,
            "reach_low": 10000, "reach_high": 25000,
            "reach_tier": "mid", "reach_confidence": "higher confidence",
            "ad_longevity_days": 40, "is_long_runner": False,
            "cadence_shape": "steady",
            "eu_disclosed_share_pct": 51.0,
            "primary_eu_market": {"country": "Netherlands", "share_pct": 22.0,
                                  "caveat": "of disclosed impressions"},
            "top_regions": [{"country": "Netherlands", "pct": 22.0},
                            {"country": "United States", "pct": 20.0},
                            {"country": "Belgium", "pct": 16.0}],
            "geo_summary": "Netherlands 22%, United States 20%, Belgium 16%",
            "sov_pct": 7.2,
            "funnel_stage": "mixed",
            "targets_specific_companies": False, "targets_job_roles": None,
            "uses_retargeting": None, "targeting_dimensions_count": 1,
            "read": "Steady but one format only and mid maturity, with reach in the "
                    "10k-25k band - present, but not investing to win. A mid-pack name to "
                    "pass, not to fear; spend your effort on the leaders instead.",
            "sample_ad_url": "https://www.linkedin.com/ad-library/detail/691234504",
        },
        {
            "rank": 6, "name": "Uncountable Inc.", "company_id": "18098234",
            "advertiser_type": "company",
            "advertiser_url": "https://www.linkedin.com/company/uncountable-inc",
            "n_ads_on_keyword": 1,
            "impression_data_coverage": "full",
            "linkedin_maturity_score": 5,
            "ad_types_used": ["Document"],
            "format_diversity_count": 1,
            "agency_run": False, "ad_payer_name": None,
            "formats": {"video": 0, "single_image": 0, "carousel": 0, "document": 1, "message": 0},
            "is_currently_advertising": True,
            "momentum_status": "steady",
            "outreach_timing_score": 6,
            "reach_low": 5000, "reach_high": 10000,
            "reach_tier": "small", "reach_confidence": "higher confidence",
            "ad_longevity_days": 33, "is_long_runner": False,
            "cadence_shape": "bursty",
            "eu_disclosed_share_pct": 44.0,
            "primary_eu_market": {"country": "Germany", "share_pct": 18.0,
                                  "caveat": "of disclosed impressions"},
            "top_regions": [{"country": "United States", "pct": 52.0},
                            {"country": "Germany", "pct": 18.0},
                            {"country": "Japan", "pct": 11.0}],
            "geo_summary": "Mostly United States, some Germany and Japan",
            "sov_pct": 6.1,
            "funnel_stage": "consideration",
            "targets_specific_companies": True, "targets_job_roles": False,
            "uses_retargeting": True, "targeting_dimensions_count": 3,
            "read": "The lone how-to advertiser - the only one running document ads, plus "
                    "retargeting and named-account targeting on modest reach. A small but "
                    "smart, conversion-minded play. Watch whether that teaching format "
                    "converts before you copy it - if it does, move fast.",
            "sample_ad_url": "https://www.linkedin.com/ad-library/detail/691234505",
        },
        {
            "rank": 7, "name": "ChannelSight", "company_id": "2073534",
            "advertiser_type": "company",
            "advertiser_url": "https://www.linkedin.com/company/channelsight",
            "n_ads_on_keyword": 1,
            "impression_data_coverage": "full",
            "linkedin_maturity_score": 6,
            "ad_types_used": ["Single image"],
            "format_diversity_count": 1,
            "agency_run": True, "ad_payer_name": "Digitas",
            "formats": {"video": 0, "single_image": 1, "carousel": 0, "document": 0, "message": 0},
            "is_currently_advertising": True,
            "momentum_status": "cooling",
            "outreach_timing_score": 4,
            "reach_low": 5000, "reach_high": 10000,
            "reach_tier": "small", "reach_confidence": "higher confidence",
            "ad_longevity_days": 96, "is_long_runner": True,
            "cadence_shape": "steady",
            "eu_disclosed_share_pct": 58.0,
            "primary_eu_market": {"country": "Ireland", "share_pct": 27.0,
                                  "caveat": "of disclosed impressions"},
            "top_regions": [{"country": "Ireland", "pct": 27.0},
                            {"country": "United Kingdom", "pct": 24.0},
                            {"country": "United States", "pct": 21.0}],
            "geo_summary": "Ireland 27%, United Kingdom 24%, United States 21%",
            "sov_pct": 5.4,
            "funnel_stage": "consideration",
            "targets_specific_companies": False, "targets_job_roles": True,
            "uses_retargeting": True, "targeting_dimensions_count": 2,
            "read": "A long-runner (96 days) now cooling, agency-run and coasting on old "
                    "winners. A cooling leader is a soft moment - if they keep pulling "
                    "back, there is share here to take. Line up your push now so you are "
                    "ready when they fade.",
            "sample_ad_url": "https://www.linkedin.com/ad-library/detail/691234506",
        },
        {
            "rank": 8, "name": "Bolt", "company_id": "10424833",
            "advertiser_type": "company",
            "advertiser_url": "https://www.linkedin.com/company/bolt-com",
            "n_ads_on_keyword": 1,
            "impression_data_coverage": "full",
            "linkedin_maturity_score": 6,
            "ad_types_used": ["Carousel"],
            "format_diversity_count": 1,
            "agency_run": False, "ad_payer_name": None,
            "formats": {"video": 0, "single_image": 0, "carousel": 1, "document": 0, "message": 0},
            "is_currently_advertising": True,
            "momentum_status": "steady",
            "outreach_timing_score": 5,
            "reach_low": 5000, "reach_high": 10000,
            "reach_tier": "small", "reach_confidence": "higher confidence",
            "ad_longevity_days": 52, "is_long_runner": False,
            "cadence_shape": "steady",
            "eu_disclosed_share_pct": 49.0,
            "primary_eu_market": {"country": "Estonia", "share_pct": 20.0,
                                  "caveat": "of disclosed impressions"},
            "top_regions": [{"country": "United States", "pct": 58.0},
                            {"country": "Estonia", "pct": 20.0},
                            {"country": "United Kingdom", "pct": 9.0}],
            "geo_summary": "Mostly United States, then Estonia and United Kingdom",
            "sov_pct": 4.8,
            "funnel_stage": "mixed",
            "targets_specific_companies": False, "targets_job_roles": None,
            "uses_retargeting": None, "targeting_dimensions_count": 2,
            "read": "Carousel only and steady, small reach - competent but narrow, and "
                    "not pushing to grow. Format range is the obvious edge: add video or "
                    "a how-to and you out-do them without spending more.",
            "sample_ad_url": "https://www.linkedin.com/ad-library/detail/691234507",
        },
        {
            "rank": 9, "name": "Senswise", "company_id": "71234598",
            "advertiser_type": "company",
            "advertiser_url": "https://www.linkedin.com/company/senswiseco",
            "n_ads_on_keyword": 1,
            "impression_data_coverage": "full",
            "linkedin_maturity_score": 2,
            "ad_types_used": ["Single image"],
            "format_diversity_count": 1,
            "agency_run": False, "ad_payer_name": None,
            "formats": {"video": 0, "single_image": 1, "carousel": 0, "document": 0, "message": 0},
            "is_currently_advertising": True,
            "momentum_status": "new",
            "outreach_timing_score": 8,
            "reach_low": 2500, "reach_high": 5000,
            "reach_tier": "micro", "reach_confidence": "higher confidence",
            "ad_longevity_days": 9, "is_long_runner": False,
            "cadence_shape": "one-off",
            "eu_disclosed_share_pct": 41.0,
            "primary_eu_market": {"country": "Sweden", "share_pct": 35.0,
                                  "caveat": "of disclosed impressions"},
            "top_regions": [{"country": "Sweden", "pct": 35.0},
                            {"country": "Turkey", "pct": 22.0},
                            {"country": "United States", "pct": 12.0}],
            "geo_summary": "Sweden 35%, Turkey 22%, United States 12%",
            "sov_pct": 4.1,
            "funnel_stage": "mixed",
            "targets_specific_companies": None, "targets_job_roles": None,
            "uses_retargeting": None, "targeting_dimensions_count": 1,
            "read": "Brand-new, one ad, micro reach (2.5k-5k) - the earliest ramp on the "
                    "board. Tiny today, but new entrants compound fast. Cheap to pre-empt "
                    "now with a sharper message; far harder to displace once it sticks.",
            "sample_ad_url": "https://www.linkedin.com/ad-library/detail/691234508",
        },

        # ------------------------------------------------------------------ #
        # Remaining limited-visibility (coverage == "none"). Tier S/T = None #
        # -> "unknown". Tier N (agency_run, formats, maturity) STILL RICH.   #
        # ------------------------------------------------------------------ #
        {
            "rank": 10, "name": "CS Analytical", "company_id": "42718903",
            "advertiser_type": "company",
            "advertiser_url": "https://www.linkedin.com/company/cs-analytical",
            "n_ads_on_keyword": 1,
            "impression_data_coverage": "none",
            "linkedin_maturity_score": 3,
            "ad_types_used": ["Single image"],
            "format_diversity_count": 1,
            "agency_run": True, "ad_payer_name": "Ironpaper",
            "formats": {"video": 0, "single_image": 1, "carousel": 0, "document": 0, "message": 0},
            "is_currently_advertising": None,
            "momentum_status": "unknown",
            "outreach_timing_score": None,
            "reach_low": None, "reach_high": None,
            "reach_tier": None, "reach_confidence": "not available",
            "ad_longevity_days": None, "is_long_runner": None,
            "cadence_shape": None,
            "eu_disclosed_share_pct": None,
            "primary_eu_market": None,
            "sov_pct": 0.0,
            "funnel_stage": None,
            "targets_specific_companies": None, "targets_job_roles": None,
            "uses_retargeting": None, "targeting_dimensions_count": None,
            "read": "Agency-run and one plain picture only, low maturity - a conventional, "
                    "outsourced motion with no format range. Reach and momentum are not "
                    "public, not zero. Beatable on creative: any richer format beats them "
                    "here.",
            "sample_ad_url": "https://www.linkedin.com/ad-library/detail/691234510",
        },
        {
            "rank": 11, "name": "Storylane", "company_id": "76543210",
            "advertiser_type": "company",
            "advertiser_url": "https://www.linkedin.com/company/storylane-io",
            "n_ads_on_keyword": 1,
            "impression_data_coverage": "none",
            "linkedin_maturity_score": 5,
            "ad_types_used": ["Carousel"],
            "format_diversity_count": 1,
            "agency_run": False, "ad_payer_name": None,
            "formats": {"video": 0, "single_image": 0, "carousel": 1, "document": 0, "message": 0},
            "is_currently_advertising": None,
            "momentum_status": "unknown",
            "outreach_timing_score": None,
            "reach_low": None, "reach_high": None,
            "reach_tier": None, "reach_confidence": "not available",
            "ad_longevity_days": None, "is_long_runner": None,
            "cadence_shape": None,
            "eu_disclosed_share_pct": None,
            "primary_eu_market": None,
            "sov_pct": 0.0,
            "funnel_stage": None,
            "targets_specific_companies": None, "targets_job_roles": None,
            "uses_retargeting": None, "targeting_dimensions_count": None,
            "read": "In-house with decent maturity but carousel only - they know how to "
                    "advertise yet lean on one format. Reach signals are not public here. "
                    "Creative range is the opening: video or a how-to would out-do them.",
            "sample_ad_url": "https://www.linkedin.com/ad-library/detail/691234511",
        },
        {
            "rank": 12, "name": "Definitive Healthcare", "company_id": "2649234",
            "advertiser_type": "company",
            "advertiser_url": "https://www.linkedin.com/company/definitive-healthcare",
            "n_ads_on_keyword": 1,
            "impression_data_coverage": "none",
            "linkedin_maturity_score": 4,
            "ad_types_used": ["Single image"],
            "format_diversity_count": 1,
            "agency_run": True, "ad_payer_name": "New North",
            "formats": {"video": 0, "single_image": 1, "carousel": 0, "document": 0, "message": 0},
            "is_currently_advertising": None,
            "momentum_status": "unknown",
            "outreach_timing_score": None,
            "reach_low": None, "reach_high": None,
            "reach_tier": None, "reach_confidence": "not available",
            "ad_longevity_days": None, "is_long_runner": None,
            "cadence_shape": None,
            "eu_disclosed_share_pct": None,
            "primary_eu_market": None,
            "sov_pct": 0.0,
            "funnel_stage": None,
            "targets_specific_companies": None, "targets_job_roles": None,
            "uses_retargeting": None, "targeting_dimensions_count": None,
            "read": "Agency-run and one plain picture only - a conventional, outsourced "
                    "motion with no format range. Reach is not public here, not zero. "
                    "Beatable on creative; an agency will also be slower to answer a "
                    "sharper offer.",
            "sample_ad_url": "https://www.linkedin.com/ad-library/detail/691234512",
        },
        {
            "rank": 13, "name": "RxLogix Corporation", "company_id": "3419087",
            "advertiser_type": "company",
            "advertiser_url": "https://www.linkedin.com/company/rxlogix-corporation",
            "n_ads_on_keyword": 1,
            "impression_data_coverage": "none",
            "linkedin_maturity_score": 4,
            "ad_types_used": ["Document"],
            "format_diversity_count": 1,
            "agency_run": False, "ad_payer_name": None,
            "formats": {"video": 0, "single_image": 0, "carousel": 0, "document": 1, "message": 0},
            "is_currently_advertising": None,
            "momentum_status": "unknown",
            "outreach_timing_score": None,
            "reach_low": None, "reach_high": None,
            "reach_tier": None, "reach_confidence": "not available",
            "ad_longevity_days": None, "is_long_runner": None,
            "cadence_shape": None,
            "eu_disclosed_share_pct": None,
            "primary_eu_market": None,
            "sov_pct": 0.0,
            "funnel_stage": None,
            "targets_specific_companies": None, "targets_job_roles": None,
            "uses_retargeting": None, "targeting_dimensions_count": None,
            "read": "In-house and how-to (document) only - a niche compliance-analytics "
                    "play that bets on teaching, not reach. Reach signals are not public "
                    "here. They own the how-to angle in their niche; match it with a "
                    "broader format mix to stand out.",
            "sample_ad_url": "https://www.linkedin.com/ad-library/detail/691234513",
        },
    ],

    "whitespace": [
        "Only Uncountable runs how-to (document) ads here, and they are small. That "
        "teaching format builds trust cheaply - move in and you own it at scale.",
        "The leaders (ClickHouse, IQVIA) lean into the United States and Germany; "
        "mid-size firms elsewhere in Europe are barely reached. That space is open.",
        "Only ClickHouse uses video; the rest run one plain picture. One good video "
        "would stand out fast against a field of static ads.",
        "No one runs chat (message) ads on this theme. It is cheap and completely "
        "untried - a low-risk way to reach buyers directly.",
    ],
    "threats": [
        "ClickHouse keeps adding ads, keeps winners live past four months, and is "
        "still ramping. Wait too long and their proven creative locks in the theme.",
        "ClickHouse and IQVIA both name the same kind of accounts. Account-based is "
        "becoming the norm here - say something sharper or you blend in.",
        "IQVIA runs an agency-led, account-based push - they may be chasing the exact "
        "buyers you want. Get your own named-account message out before they do.",
        "SeoProfy is brand-new and funded, adding ads fast. Set your narrative before "
        "they lock theirs in and get hard to catch.",
    ],

    "method_note": (
        "This report is built from public advertising activity. For some advertisers "
        "we can see full detail; for others (marked 'limited visibility') detailed "
        "reach is not publicly available, so we show what we can and never guess. "
        "Limited visibility does not mean a company is inactive. ZenABM fills these "
        "gaps with data you cannot get from public sources alone."
    ),
    "upgrade_teaser": (
        "This is the free keyword snapshot. It covers 3 keywords, the top 5 rivals "
        "each, and the top 200 ads. The paid version opens the full library."
    ),
}


# --------------------------------------------------------------------------- #
# COMBINED multi-keyword sample (up to 3 keywords in ONE report).             #
#                                                                             #
# Keyword 1 reuses the rich SAMPLE above ("product analytics"). Keywords 2-3  #
# ("data warehouse", "feature flags") are smaller (4-6 competitors) but follow #
# the same per-keyword contract. ClickHouse deliberately appears on BOTH      #
# "product analytics" and "data warehouse" so the cross-theme roll-up has a   #
# rival spanning 2 themes. Insights (cross_keyword_summary, per-keyword       #
# win/watch, per-competitor reads) are strong EXAMPLE copy - they stand in    #
# for what Zena will author: expert, plain-English and ACTIONABLE, each tied  #
# back to a concrete ZenABM move.                                             #
# --------------------------------------------------------------------------- #

# ---- Keyword 2: "data warehouse" (5 competitors) ------------------------- #
_KW_DATA_WAREHOUSE: Dict[str, Any] = {
    "keyword": "data warehouse",
    "geographies": "Global",
    "total_matching_ads": 41230,
    "n_ads_scanned": 200,
    "n_individuals": 2,
    "generated_at": "2026-07-06",

    "coverage_breakdown": {"full": 3, "partial": 0, "none": 2},
    "pct_us_only": 44.0,
    "field_format_distribution": {
        "video": 4, "single_image": 9, "carousel": 3, "document": 2, "message": 0,
    },
    "n_agency_run": 1,
    "n_thought_leaders": 2,
    "n_currently_advertising": 3,
    "n_long_runners": 2,
    "thought_leaders": [
        {"name": "Benn Stancil", "advertiser_url": "https://www.linkedin.com/in/benn-stancil",
         "n_ads_on_keyword": 1, "promoted_by": "Mode",
         "sample_ad_url": "https://www.linkedin.com/ad-library/detail/691244501"},
        {"name": "Zhamak Dehghani", "advertiser_url": "https://www.linkedin.com/in/zhamak-dehghani",
         "n_ads_on_keyword": 1, "promoted_by": None,
         "sample_ad_url": "https://www.linkedin.com/ad-library/detail/691244502"},
    ],

    "exec_summary": [
        "Snowflake owns this theme: the biggest reach (100k-250k), ads live over 200 "
        "days, video, retargeting, and named accounts. That is a mature, always-on "
        "machine. Do not out-shout it - pick one buyer it under-serves and win there.",
        "ClickHouse is here too, not just on product analytics, and ramping on both. "
        "One rival pushing on two of your themes is the one to beat everywhere - watch "
        "this theme weekly and do not let them compound a lead.",
        "Below the top two it is mostly one plain picture and no how-to ads. Firebolt "
        "just started with a single image. A short how-to video would stand out fast in "
        "a field this flat.",
    ],

    "competitors": [
        {
            "rank": 1, "name": "Snowflake", "company_id": "3653845",
            "advertiser_type": "company",
            "advertiser_url": "https://www.linkedin.com/company/snowflake-computing",
            "n_ads_on_keyword": 4,
            "impression_data_coverage": "full",
            "linkedin_maturity_score": 9,
            "ad_types_used": ["Video", "Single image", "Carousel"],
            "format_diversity_count": 3,
            "agency_run": False, "ad_payer_name": None,
            "formats": {"video": 2, "single_image": 1, "carousel": 1, "document": 0, "message": 0},
            "is_currently_advertising": True,
            "momentum_status": "steady",
            "outreach_timing_score": 5,
            "reach_low": 100000, "reach_high": 250000,
            "reach_tier": "enterprise", "reach_confidence": "higher confidence",
            "ad_longevity_days": 210, "is_long_runner": True,
            "cadence_shape": "steady",
            "eu_disclosed_share_pct": 51.0,
            "primary_eu_market": {"country": "United Kingdom", "share_pct": 16.0,
                                  "caveat": "of disclosed impressions"},
            "top_regions": [{"country": "United States", "pct": 54.0},
                            {"country": "United Kingdom", "pct": 16.0},
                            {"country": "Germany", "pct": 10.0}],
            "geo_summary": "Mostly United States, then United Kingdom and Germany",
            "sov_pct": 36.8,
            "funnel_stage": "mixed",
            "targets_specific_companies": True, "targets_job_roles": True,
            "uses_retargeting": True, "targeting_dimensions_count": 4,
            "read": "The heavyweight - biggest reach (100k-250k = their ads were shown "
                    "that many times), ads live 200+ days, video, retargeting and named "
                    "accounts. A mature machine, not a test. Do not fight on volume; pick "
                    "one buyer they under-serve and own that message.",
            "sample_ad_url": "https://www.linkedin.com/ad-library/detail/691244001",
        },
        {
            "rank": 2, "name": "ClickHouse", "company_id": "18538494",
            "advertiser_type": "company",
            "advertiser_url": "https://www.linkedin.com/company/clickhouseinc",
            "n_ads_on_keyword": 3,
            "impression_data_coverage": "full",
            "linkedin_maturity_score": 8,
            "ad_types_used": ["Single image", "Carousel"],
            "format_diversity_count": 2,
            "agency_run": False, "ad_payer_name": None,
            "formats": {"video": 0, "single_image": 2, "carousel": 1, "document": 0, "message": 0},
            "is_currently_advertising": True,
            "momentum_status": "ramping",
            "outreach_timing_score": 8,
            "reach_low": 50000, "reach_high": 100000,
            "reach_tier": "large", "reach_confidence": "higher confidence",
            "ad_longevity_days": 140, "is_long_runner": True,
            "cadence_shape": "steady",
            "eu_disclosed_share_pct": 60.0,
            "primary_eu_market": {"country": "Germany", "share_pct": 22.0,
                                  "caveat": "of disclosed impressions"},
            "top_regions": [{"country": "United States", "pct": 43.0},
                            {"country": "Germany", "pct": 22.0},
                            {"country": "United Kingdom", "pct": 13.0}],
            "geo_summary": "Mostly United States and Germany, some United Kingdom",
            "sov_pct": 27.5,
            "funnel_stage": "consideration",
            "targets_specific_companies": True, "targets_job_roles": True,
            "uses_retargeting": True, "targeting_dimensions_count": 4,
            "read": "The same rival from product analytics, now ramping here too, with ads "
                    "live 140+ days, retargeting and named accounts - they are pushing "
                    "hard on both fronts at once. That makes them your top overall threat. "
                    "Watch this theme weekly; do not let them compound a two-theme lead.",
            "sample_ad_url": "https://www.linkedin.com/ad-library/detail/691244002",
        },
        {
            "rank": 3, "name": "Firebolt", "company_id": "18927110",
            "advertiser_type": "company",
            "advertiser_url": "https://www.linkedin.com/company/firebolt-analytics",
            "n_ads_on_keyword": 2,
            "impression_data_coverage": "full",
            "linkedin_maturity_score": 5,
            "ad_types_used": ["Single image"],
            "format_diversity_count": 1,
            "agency_run": False, "ad_payer_name": None,
            "formats": {"video": 0, "single_image": 2, "carousel": 0, "document": 0, "message": 0},
            "is_currently_advertising": True,
            "momentum_status": "new",
            "outreach_timing_score": 7,
            "reach_low": 10000, "reach_high": 25000,
            "reach_tier": "mid", "reach_confidence": "higher confidence",
            "ad_longevity_days": 18, "is_long_runner": False,
            "cadence_shape": "one-off",
            "eu_disclosed_share_pct": 47.0,
            "primary_eu_market": {"country": "Israel", "share_pct": 24.0,
                                  "caveat": "of disclosed impressions"},
            "top_regions": [{"country": "United States", "pct": 49.0},
                            {"country": "Israel", "pct": 24.0},
                            {"country": "United Kingdom", "pct": 11.0}],
            "geo_summary": "Mostly United States, then Israel and United Kingdom",
            "sov_pct": 18.3,
            "funnel_stage": "consideration",
            "targets_specific_companies": False, "targets_job_roles": True,
            "uses_retargeting": False, "targeting_dimensions_count": 2,
            "read": "A fresh challenger - live under three weeks, one plain picture, "
                    "targeting roles not accounts. An early test with no set message yet. "
                    "Cheap to out-do on creative range now: bring video and name accounts "
                    "before they do.",
            "sample_ad_url": "https://www.linkedin.com/ad-library/detail/691244003",
        },
        {
            # Limited visibility, but ranked in on ad volume.
            "rank": 4, "name": "Panoply", "company_id": "10419876",
            "advertiser_type": "company",
            "advertiser_url": "https://www.linkedin.com/company/panoply-io",
            "n_ads_on_keyword": 2,
            "impression_data_coverage": "none",
            "linkedin_maturity_score": 4,
            "ad_types_used": ["Single image"],
            "format_diversity_count": 1,
            "agency_run": True, "ad_payer_name": "Walk West",
            "formats": {"video": 0, "single_image": 2, "carousel": 0, "document": 0, "message": 0},
            "is_currently_advertising": None,
            "momentum_status": "unknown",
            "outreach_timing_score": None,
            "reach_low": None, "reach_high": None,
            "reach_tier": None, "reach_confidence": "not available",
            "ad_longevity_days": None, "is_long_runner": None,
            "cadence_shape": None,
            "eu_disclosed_share_pct": None,
            "primary_eu_market": None,
            "sov_pct": 0.0,
            "funnel_stage": None,
            "targets_specific_companies": None, "targets_job_roles": None,
            "uses_retargeting": None, "targeting_dimensions_count": None,
            "read": "Two ads but both one plain picture, run by an agency - a conventional, "
                    "outsourced motion with no format range. Reach and momentum are not "
                    "public, not zero. Beatable on creative; an agency is slower to answer "
                    "a sharper offer.",
            "sample_ad_url": "https://www.linkedin.com/ad-library/detail/691244004",
        },
        {
            "rank": 5, "name": "Yellowbrick Data", "company_id": "18234567",
            "advertiser_type": "company",
            "advertiser_url": "https://www.linkedin.com/company/yellowbrick-data",
            "n_ads_on_keyword": 1,
            "impression_data_coverage": "none",
            "linkedin_maturity_score": 3,
            "ad_types_used": ["Document"],
            "format_diversity_count": 1,
            "agency_run": False, "ad_payer_name": None,
            "formats": {"video": 0, "single_image": 0, "carousel": 0, "document": 1, "message": 0},
            "is_currently_advertising": None,
            "momentum_status": "unknown",
            "outreach_timing_score": None,
            "reach_low": None, "reach_high": None,
            "reach_tier": None, "reach_confidence": "not available",
            "ad_longevity_days": None, "is_long_runner": None,
            "cadence_shape": None,
            "eu_disclosed_share_pct": None,
            "primary_eu_market": None,
            "sov_pct": 0.0,
            "funnel_stage": None,
            "targets_specific_companies": None, "targets_job_roles": None,
            "uses_retargeting": None, "targeting_dimensions_count": None,
            "read": "In-house and how-to (document) only - one advertiser betting on "
                    "teaching, at a low tempo. Reach signals are not public here. They own "
                    "a small how-to lane; a broader format mix would out-do them.",
            "sample_ad_url": "https://www.linkedin.com/ad-library/detail/691244005",
        },
    ],

    "whitespace": [
        "Only Snowflake runs video here; everyone else runs one plain picture. A "
        "second strong video would stand out fast against a flat field.",
        "No one runs how-to (document) ads that teach on this theme. Snowflake talks "
        "scale, not cost - a clear cost story for mid-size teams is wide open.",
        "No one uses chat (message) ads here. It is cheap and untried - a direct line "
        "to buyers no rival is using.",
    ],
    "threats": [
        "ClickHouse is ramping here and on product analytics, with ads live 140+ days "
        "on both. One rival on two themes can crowd you out - act before their lead "
        "compounds across both.",
        "Snowflake keeps the same ads running past 200 days - their message is "
        "sticking and their reach dwarfs the field. Say something sharper and narrower "
        "or you blend into their shadow.",
    ],

    "method_note": (
        "This report is built from public advertising activity. For some advertisers "
        "we can see full detail; for others (marked 'limited visibility') detailed "
        "reach is not publicly available, so we show what we can and never guess. "
        "Limited visibility does not mean a company is inactive."
    ),
    "upgrade_teaser": (
        "Free snapshot of this theme: top 5 rivals, top 200 ads. The paid version "
        "opens the full library."
    ),
}

# ---- Keyword 3: "feature flags" (4 competitors) -------------------------- #
_KW_FEATURE_FLAGS: Dict[str, Any] = {
    "keyword": "feature flags",
    "geographies": "Global",
    "total_matching_ads": 12840,
    "n_ads_scanned": 200,
    "n_individuals": 1,
    "generated_at": "2026-07-06",

    "coverage_breakdown": {"full": 3, "partial": 0, "none": 1},
    "pct_us_only": 61.0,
    "field_format_distribution": {
        "video": 3, "single_image": 6, "carousel": 2, "document": 1, "message": 0,
    },
    "n_agency_run": 0,
    "n_thought_leaders": 1,
    "n_currently_advertising": 3,
    "n_long_runners": 1,
    "thought_leaders": [
        {"name": "Edith Harbaugh", "advertiser_url": "https://www.linkedin.com/in/edithharbaugh",
         "n_ads_on_keyword": 1, "promoted_by": "LaunchDarkly",
         "sample_ad_url": "https://www.linkedin.com/ad-library/detail/691254501"},
    ],

    "exec_summary": [
        "LaunchDarkly owns this theme - five ads, half the share of voice, ads live "
        "165 days, the widest format mix (video, image, carousel), plus retargeting and "
        "named accounts. A category owner, not a test. Do not copy them head-on; find "
        "the developer pain they skip.",
        "This theme is the smallest but heating up. Statsig is ramping and already runs "
        "video; Flagsmith just started. New entrants compound fast - get in now, while "
        "attention is still cheap.",
        "Everyone here chases developers by job title; only LaunchDarkly names the "
        "accounts it wants. If you can list your target accounts, account-based "
        "targeting is an easy edge nobody else is using.",
    ],

    "competitors": [
        {
            "rank": 1, "name": "LaunchDarkly", "company_id": "10906099",
            "advertiser_type": "company",
            "advertiser_url": "https://www.linkedin.com/company/launchdarkly",
            "n_ads_on_keyword": 5,
            "impression_data_coverage": "full",
            "linkedin_maturity_score": 8,
            "ad_types_used": ["Video", "Single image", "Carousel"],
            "format_diversity_count": 3,
            "agency_run": False, "ad_payer_name": None,
            "formats": {"video": 2, "single_image": 2, "carousel": 1, "document": 0, "message": 0},
            "is_currently_advertising": True,
            "momentum_status": "steady",
            "outreach_timing_score": 6,
            "reach_low": 25000, "reach_high": 50000,
            "reach_tier": "large", "reach_confidence": "higher confidence",
            "ad_longevity_days": 165, "is_long_runner": True,
            "cadence_shape": "steady",
            "eu_disclosed_share_pct": 38.0,
            "primary_eu_market": {"country": "United Kingdom", "share_pct": 14.0,
                                  "caveat": "of disclosed impressions"},
            "top_regions": [{"country": "United States", "pct": 66.0},
                            {"country": "United Kingdom", "pct": 14.0},
                            {"country": "Canada", "pct": 7.0}],
            "geo_summary": "Mostly United States, some United Kingdom and Canada",
            "sov_pct": 52.1,
            "funnel_stage": "consideration",
            "targets_specific_companies": True, "targets_job_roles": True,
            "uses_retargeting": True, "targeting_dimensions_count": 4,
            "read": "The category owner - most ads, half the share of voice, widest format "
                    "mix, winners live 165 days, plus retargeting and named accounts. A "
                    "proven, always-on program. Do not copy them head-on; find the "
                    "developer pain they skip and own that message.",
            "sample_ad_url": "https://www.linkedin.com/ad-library/detail/691254001",
        },
        {
            "rank": 2, "name": "Statsig", "company_id": "71234511",
            "advertiser_type": "company",
            "advertiser_url": "https://www.linkedin.com/company/statsig",
            "n_ads_on_keyword": 2,
            "impression_data_coverage": "full",
            "linkedin_maturity_score": 5,
            "ad_types_used": ["Single image", "Video"],
            "format_diversity_count": 2,
            "agency_run": False, "ad_payer_name": None,
            "formats": {"video": 1, "single_image": 1, "carousel": 0, "document": 0, "message": 0},
            "is_currently_advertising": True,
            "momentum_status": "ramping",
            "outreach_timing_score": 8,
            "reach_low": 10000, "reach_high": 25000,
            "reach_tier": "mid", "reach_confidence": "higher confidence",
            "ad_longevity_days": 34, "is_long_runner": False,
            "cadence_shape": "steady",
            "eu_disclosed_share_pct": 33.0,
            "primary_eu_market": {"country": "United Kingdom", "share_pct": 11.0,
                                  "caveat": "of disclosed impressions"},
            "top_regions": [{"country": "United States", "pct": 71.0},
                            {"country": "United Kingdom", "pct": 11.0},
                            {"country": "India", "pct": 6.0}],
            "geo_summary": "Mostly United States, some United Kingdom and India",
            "sov_pct": 21.4,
            "funnel_stage": "consideration",
            "targets_specific_companies": False, "targets_job_roles": True,
            "uses_retargeting": True, "targeting_dimensions_count": 3,
            "read": "The ramping challenger - already running video and retargeting after "
                    "just a month, building fast toward LaunchDarkly. The one to watch "
                    "here; move before they add named accounts and harden into a second "
                    "leader.",
            "sample_ad_url": "https://www.linkedin.com/ad-library/detail/691254002",
        },
        {
            "rank": 3, "name": "Flagsmith", "company_id": "42711987",
            "advertiser_type": "company",
            "advertiser_url": "https://www.linkedin.com/company/flagsmith",
            "n_ads_on_keyword": 1,
            "impression_data_coverage": "full",
            "linkedin_maturity_score": 3,
            "ad_types_used": ["Single image"],
            "format_diversity_count": 1,
            "agency_run": False, "ad_payer_name": None,
            "formats": {"video": 0, "single_image": 1, "carousel": 0, "document": 0, "message": 0},
            "is_currently_advertising": True,
            "momentum_status": "new",
            "outreach_timing_score": 7,
            "reach_low": 2500, "reach_high": 5000,
            "reach_tier": "micro", "reach_confidence": "higher confidence",
            "ad_longevity_days": 12, "is_long_runner": False,
            "cadence_shape": "one-off",
            "eu_disclosed_share_pct": 57.0,
            "primary_eu_market": {"country": "United Kingdom", "share_pct": 29.0,
                                  "caveat": "of disclosed impressions"},
            "top_regions": [{"country": "United Kingdom", "pct": 29.0},
                            {"country": "United States", "pct": 26.0},
                            {"country": "Germany", "pct": 10.0}],
            "geo_summary": "United Kingdom 29%, United States 26%, Germany 10%",
            "sov_pct": 14.2,
            "funnel_stage": "consideration",
            "targets_specific_companies": False, "targets_job_roles": True,
            "uses_retargeting": False, "targeting_dimensions_count": 2,
            "read": "Brand-new, one ad, micro reach (2.5k-5k), leaning on an open-source "
                    "angle. Tiny now, but a community push can compound fast. Cheap to "
                    "pre-empt today with a sharper message; harder to displace later.",
            "sample_ad_url": "https://www.linkedin.com/ad-library/detail/691254003",
        },
        {
            "rank": 4, "name": "Unleash", "company_id": "18654321",
            "advertiser_type": "company",
            "advertiser_url": "https://www.linkedin.com/company/unleash-oss",
            "n_ads_on_keyword": 1,
            "impression_data_coverage": "none",
            "linkedin_maturity_score": 3,
            "ad_types_used": ["Carousel"],
            "format_diversity_count": 1,
            "agency_run": False, "ad_payer_name": None,
            "formats": {"video": 0, "single_image": 0, "carousel": 1, "document": 0, "message": 0},
            "is_currently_advertising": None,
            "momentum_status": "unknown",
            "outreach_timing_score": None,
            "reach_low": None, "reach_high": None,
            "reach_tier": None, "reach_confidence": "not available",
            "ad_longevity_days": None, "is_long_runner": None,
            "cadence_shape": None,
            "eu_disclosed_share_pct": None,
            "primary_eu_market": None,
            "sov_pct": 0.0,
            "funnel_stage": None,
            "targets_specific_companies": None, "targets_job_roles": None,
            "uses_retargeting": None, "targeting_dimensions_count": None,
            "read": "In-house and carousel only - a light, open-source presence with one "
                    "format. Reach and momentum are not public here, not zero. Beatable on "
                    "creative range: video or a how-to would out-do them.",
            "sample_ad_url": "https://www.linkedin.com/ad-library/detail/691254004",
        },
    ],

    "whitespace": [
        "No one runs how-to (document) ads on feature flags. That format builds trust "
        "cheaply - move first and show a flag rollout live to own the lane.",
        "Only LaunchDarkly names its target accounts; Statsig, Flagsmith and the rest "
        "chase job titles. Name your accounts and you get an edge nobody else has.",
        "Everyone here is heavy on the United States; Europe is thinly covered. A "
        "localised message would stand out where the leaders barely show up.",
    ],
    "threats": [
        "LaunchDarkly owns half the share of voice, keeps winners live 165 days, and "
        "runs the widest format mix. Wait too long and their proven creative locks the "
        "theme in.",
        "Statsig is ramping fast and already runs video and retargeting after one "
        "month. Act before they add named accounts and become a second leader.",
    ],

    "method_note": (
        "This report is built from public advertising activity. For some advertisers "
        "we can see full detail; for others (marked 'limited visibility') detailed "
        "reach is not publicly available, so we show what we can and never guess. "
        "Limited visibility does not mean a company is inactive."
    ),
    "upgrade_teaser": (
        "Free snapshot of this theme: top 5 rivals, top 200 ads. The paid version "
        "opens the full library."
    ),
}


COMBINED_SAMPLE: Dict[str, Any] = {
    "generated_at": "2026-07-06",
    "geographies": "Global",
    "free_tier_note": (
        "Free version: up to 3 keywords, top 5 competitors each, top 200 ads scanned "
        "per keyword. Upgrade for the full picture."
    ),

    # Lead exec summary across ALL themes. PURE INSIGHT - no ZenABM plugs; the
    # analysis is the value. Expert substance in plain 5th-grade English: each
    # bullet links several signals into one sharp, non-obvious read + a move. This
    # stands in for what Zena will write.
    "cross_keyword_summary": [
        "ClickHouse is the one rival you see twice - product analytics and data "
        "warehouse. On both they are ramping, keep ads live past four months, and "
        "retarget. That mix means a proven, always-on program, not a test. Do not try "
        "to out-spend it. Out-angle it: pick the buyer their ads talk past.",
        "Each theme already has one clear owner - ClickHouse, Snowflake, LaunchDarkly. "
        "All three run winners for months, use video, retarget, and name their target "
        "accounts. They have found what works. Copy them head-on and you lose; find the "
        "one buyer each under-serves and own that message instead.",
        "The whole field runs on one plain picture. Almost no one uses video, and no "
        "one runs how-to (document) ads that teach. Teaching ads build trust cheaply. "
        "Ship one good how-to on each theme and you own a lane nobody is fighting for.",
        "Feature flags is your soft spot to hit. It is the smallest theme but heating "
        "up - LaunchDarkly leads, yet Statsig is ramping and two more just started. "
        "Everyone there chases developers by job title; only LaunchDarkly names "
        "accounts. Name your accounts and get in now, while attention is still cheap.",
        "Fresh money is entering every theme - SeoProfy, Firebolt, Statsig all started "
        "in the last month. New and single-format today, any one could be the next "
        "ClickHouse. Watch the ramps: it is far cheaper to pre-empt a challenger now "
        "than to displace them once their message sticks.",
        "Everyone crowds the United States; Europe is thinly covered on all three "
        "themes. A message built for a European buyer would stand out fast where the "
        "leaders are barely showing up.",
    ],

    # Keyword 1 reuses the rich single-keyword SAMPLE verbatim.
    "keywords": [SAMPLE, _KW_DATA_WAREHOUSE, _KW_FEATURE_FLAGS],

    # Roll-up: advertisers appearing on 2+ themes. ClickHouse spans two.
    "cross_theme_rivals": [
        {
            "name": "ClickHouse", "company_id": "18538494",
            "advertiser_url": "https://www.linkedin.com/company/clickhouseinc",
            "keywords": ["product analytics", "data warehouse"],
            "n_keywords": 2,
        },
    ],

    "method_note": (
        "This report is built from public advertising activity. For some advertisers "
        "we can see full detail; for others (marked 'limited visibility') detailed "
        "reach is not publicly available, so we show what we can and never guess. "
        "Limited visibility does not mean a company is inactive. ZenABM fills these "
        "gaps with data you cannot get from public sources alone."
    ),
    "upgrade_teaser": (
        "This is the free multi-keyword snapshot. It covers 3 keywords, the top 5 "
        "rivals each, and the top 200 ads per keyword. The paid version opens the "
        "full library and tracks every rival across every theme."
    ),
}

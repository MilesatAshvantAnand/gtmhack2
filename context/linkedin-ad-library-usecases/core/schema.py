"""Pydantic v2 models for the LinkedIn Ad Library API response envelope.

Every field, type, and coverage constraint below is validated against the
captured fixture corpus (see tests/knowledge_base/). Any drift (LinkedIn
adds/removes/renames a field) makes the pytest suite fail immediately.

Reference: docs/api-knowledge-base/response-fields.md
"""
from __future__ import annotations

from typing import Optional, List, Literal
from pydantic import BaseModel, Field, ConfigDict


# ── Nested types ──────────────────────────────────────────────────────────

class AdvertiserInfo(BaseModel):
    """`details.advertiser` — 100% present as container.

    Sub-field presence (verified across 1,563-ad corpus, 2026-07-03):
      advertiserName : 100%
      advertiserUrl  : 100%
      adPayer        : 99.8% (3/1,563 ads had it missing — extremely rare)
    """
    model_config = ConfigDict(extra="forbid")
    advertiserName: str
    advertiserUrl: str
    adPayer: Optional[str] = None


class TotalImpressions(BaseModel):
    """`details.adStatistics.totalImpressions` — 12 distinct (from,to) buckets."""
    model_config = ConfigDict(extra="forbid")
    from_: int = Field(alias="from")
    to: int


class ImpressionCountryEntry(BaseModel):
    """`details.adStatistics.impressionsDistributionByCountry[]` — one entry per country.

    NOTE: `impressionPercentage` can exceed 100 in rare cases (observed values up to ~104
    on deep-Personio fixtures). LinkedIn's percentage math is not strict — do not assume
    normalization to 100. The sum across all entries also does NOT sum to 100 in ~59% of
    ads (see WE7 in inferable-signals.md — this is the DSA-hidden-share indicator).
    """
    model_config = ConfigDict(extra="forbid")
    country: str = Field(description="URN form, e.g. 'urn:li:country:DE'")
    impressionPercentage: float = Field(ge=0.0, description="Can exceed 100 in rare cases")


class AdStatistics(BaseModel):
    """`details.adStatistics` — 64.3% coverage; absent for non-EU/EEA ads."""
    model_config = ConfigDict(extra="forbid")
    firstImpressionAt: int = Field(description="Epoch milliseconds")
    latestImpressionAt: int = Field(description="Epoch milliseconds")
    totalImpressions: TotalImpressions
    impressionsDistributionByCountry: List[ImpressionCountryEntry]


class TargetingFacet(BaseModel):
    """`details.adTargeting[]` — one entry per targeting facet used."""
    model_config = ConfigDict(extra="forbid")
    facetName: str = Field(description="Location | Language | Job | Company | Audience | Demographic | Member Interests and Traits | Education")
    isIncluded: bool
    isExcluded: bool
    includedSegments: List[str] = Field(description="Empty for Job/Company/Audience/Demographic/Interests/Education")
    excludedSegments: List[str]


class AdDetails(BaseModel):
    """`details` — always present."""
    model_config = ConfigDict(extra="forbid")
    advertiser: AdvertiserInfo
    type: str = Field(description="SPONSORED_STATUS_UPDATE | SPONSORED_VIDEO | ... | $UNKNOWN")
    adTargeting: List[TargetingFacet] = Field(description="Always present as list; may be [] for non-EU ads")
    adStatistics: Optional[AdStatistics] = Field(default=None, description="Absent for non-EU/EEA ads (~35% of ads)")


# ── Ad element ────────────────────────────────────────────────────────────

class AdElement(BaseModel):
    """One element in the `elements` list of a successful response."""
    model_config = ConfigDict(extra="forbid")
    adUrl: str = Field(description="Points to LinkedIn's public ad preview page")
    isRestricted: bool = Field(description="Always False in our corpus; True case unobserved")
    details: AdDetails


# ── Paging ────────────────────────────────────────────────────────────────

class PagingLink(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rel: str
    href: str
    type: str


class Paging(BaseModel):
    model_config = ConfigDict(extra="forbid")
    count: int
    start: int
    total: int = Field(description="True count of matching ads for the query")
    links: Optional[List[PagingLink]] = Field(default=None, description="Absent on last page")


# ── Top-level response envelopes ──────────────────────────────────────────

class AdLibraryResponse(BaseModel):
    """Successful 200 response."""
    model_config = ConfigDict(extra="forbid")
    elements: List[AdElement]
    paging: Paging


# ── Error envelope ────────────────────────────────────────────────────────

class InputErrorPath(BaseModel):
    model_config = ConfigDict(extra="allow")
    fieldPath: str


class InputErrorLocation(BaseModel):
    model_config = ConfigDict(extra="allow")
    inputPath: InputErrorPath


class InputError(BaseModel):
    model_config = ConfigDict(extra="allow")
    code: str = Field(description="QUERY_PARAM_NOT_ALLOWED | FIELD_INVALID")
    input: Optional[InputErrorLocation] = None
    description: Optional[str] = None


class ErrorDetails(BaseModel):
    model_config = ConfigDict(extra="allow")
    inputErrors: List[InputError]


class ApiError(BaseModel):
    """Error response — 400/401/404/426/429."""
    model_config = ConfigDict(extra="allow")
    status: int
    message: Optional[str] = None
    code: Optional[str] = Field(default=None, description="EXPIRED_ACCESS_TOKEN | NONEXISTENT_VERSION | RESOURCE_NOT_FOUND | ILLEGAL_ARGUMENT | ...")
    serviceErrorCode: Optional[int] = Field(default=None, description="e.g. 65602 for EXPIRED_ACCESS_TOKEN")
    errorDetailType: Optional[str] = None
    errorDetails: Optional[ErrorDetails] = None


# ── Convenience helpers ───────────────────────────────────────────────────

AdType = Literal[
    "SPONSORED_STATUS_UPDATE",
    "SPONSORED_VIDEO",
    "SPONSORED_UPDATE_CAROUSEL",
    "SPONSORED_UPDATE_NATIVE_DOCUMENT",
    "SPONSORED_MESSAGE",
    "SPONSORED_INMAILS",
    "TEXT_AD",
    "SPONSORED_UPDATE_EVENT",
    "SPONSORED_UPDATE_JOB_POSTING",
    "JOBS_V2",
    "FOLLOW_COMPANY_V2",
    "SPOTLIGHT_V2",  # theoretical — not observed in corpus
    "$UNKNOWN",
]

# Facets that DO expose their segment values (Location, Language) vs those that don't.
FACETS_WITH_SEGMENTS = {"Location", "Language"}
FACETS_OPAQUE = {"Company", "Job", "Audience", "Demographic", "Member Interests and Traits", "Education"}

"""Pydantic models for the normalized ZenABM API responses (v1)."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class Advertiser(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    url: str
    company_id: Optional[str] = Field(default=None, alias="companyId")
    payer: Optional[str] = None


class ImpressionsRange(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: int = Field(alias="from")
    to: int


class CountryShare(BaseModel):
    country: str  # plain ISO, e.g. "DE"
    percentage: float


class Statistics(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    first_impression_at: int = Field(alias="firstImpressionAt")
    latest_impression_at: int = Field(alias="latestImpressionAt")
    total_impressions: ImpressionsRange = Field(alias="totalImpressions")
    impressions_by_country: List[CountryShare] = Field(
        default_factory=list, alias="impressionsByCountry"
    )


class TargetingFacet(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    facet: str
    is_included: bool = Field(alias="isIncluded")
    is_excluded: bool = Field(alias="isExcluded")
    included_segments: List[str] = Field(default_factory=list, alias="includedSegments")
    excluded_segments: List[str] = Field(default_factory=list, alias="excludedSegments")


class Ad(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    ad_id: str = Field(alias="adId")
    ad_url: str = Field(alias="adUrl")
    is_restricted: bool = Field(default=False, alias="isRestricted")
    type: str
    advertiser: Advertiser
    statistics: Optional[Statistics] = None
    targeting: List[TargetingFacet] = Field(default_factory=list)


class AdvertiserRollup(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    url: str
    company_id: Optional[str] = Field(default=None, alias="companyId")
    ad_count: int = Field(alias="adCount")


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
    model_config = ConfigDict(populate_by_name=True)

    cost_in_usd: float = Field(default=0.0, alias="costInUsd")
    impressions: int = 0
    clicks: int = 0
    engagements: int = 0
    conversions: int = 0  # live API also returns this field

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
    model_config = ConfigDict(populate_by_name=True)

    linkedin_id: Optional[str] = Field(default=None, alias="linkedInId")
    name: Optional[str] = None
    format: Optional[str] = None
    status: Optional[str] = None
    is_serving: Optional[bool] = Field(default=None, alias="isServing")

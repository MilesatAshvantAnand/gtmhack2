"""Client for the deployed ZenABM API (https://app.zenabm.com/api/v1).

Usage:
    from core.zenabm_api import ZenABMClient, ZenABMAuthError, ZenABMPlanError

    client = ZenABMClient()  # reads ZENABM_TOKEN + ZENABM_API_BASE_URL from env
    result = client.search_by_advertiser(company_id="27027108", limit=25)
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

import requests

from core.zenabm_models import AdLibraryResult, Creative, LinkedInMetrics


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ZenABMError(Exception):
    """Base error for non-200 ZenABM API responses."""

    def __init__(self, status: int, body: Any = None) -> None:
        self.status = status
        self.body = body
        super().__init__(f"ZenABM API HTTP {status}")


class ZenABMAuthError(ZenABMError):
    """401 - token expired or invalid."""


class ZenABMPlanError(ZenABMError):
    """402/403 - trial ended or feature gate."""


class ZenABMRateLimit(ZenABMError):
    """429 - too many requests."""


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class ZenABMClient:
    DEFAULT_BASE_URL = "https://app.zenabm.com/api/v1"

    def __init__(
        self,
        token: Optional[str] = None,
        base_url: Optional[str] = None,
        session: Optional[Any] = None,
        timeout: float = 30.0,
    ) -> None:
        self._token = token or os.environ.get("ZENABM_TOKEN")
        self.base_url = (
            base_url
            or os.environ.get("ZENABM_API_BASE_URL")
            or self.DEFAULT_BASE_URL
        ).rstrip("/")
        self.session = session if session is not None else requests.Session()
        self.timeout = timeout

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _headers(self) -> Dict[str, str]:
        if not self._token:
            raise ZenABMAuthError(
                0, "No ZENABM_TOKEN configured. Get one at https://app.zenabm.com/api-keys."
            )
        return {"Authorization": f"Bearer {self._token}"}

    def _get(self, path: str, params: Dict[str, Any]) -> dict:
        # Drop params whose value is None so they are not sent on the wire.
        params = {k: v for k, v in params.items() if v is not None}
        resp = self.session.get(
            self.base_url + path,
            headers=self._headers(),
            params=params,
            timeout=self.timeout,
        )
        status = resp.status_code
        if status == 200:
            return resp.json()
        # Try to parse error body for caller context.
        body = None
        try:
            body = resp.json()
        except Exception:
            pass
        if status == 401:
            raise ZenABMAuthError(status, body)
        if status in (402, 403):
            raise ZenABMPlanError(status, body)
        if status == 429:
            raise ZenABMRateLimit(status, body)
        raise ZenABMError(status, body)

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    def search_by_advertiser(
        self,
        company: Optional[str] = None,
        company_id: Optional[str] = None,
        countries: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 25,
    ) -> AdLibraryResult:
        """Return ads matching an advertiser name or company ID."""
        return AdLibraryResult.from_response(
            self._get(
                "/ad-library/by-advertiser",
                {
                    "company": company,
                    "companyId": company_id,
                    "countries": countries,
                    "startDate": start_date,
                    "endDate": end_date,
                    "limit": limit,
                },
            )
        )

    def search_by_keyword(
        self,
        keyword: str,
        advertiser: Optional[str] = None,
        countries: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 25,
    ) -> AdLibraryResult:
        """Return ads matching a keyword."""
        return AdLibraryResult.from_response(
            self._get(
                "/ad-library/by-keyword",
                {
                    "keyword": keyword,
                    "advertiser": advertiser,
                    "countries": countries,
                    "startDate": start_date,
                    "endDate": end_date,
                    "limit": limit,
                },
            )
        )

    def linkedin_metrics(self, start_date: str, end_date: str) -> LinkedInMetrics:
        """Return own LinkedIn ad metrics for the given date range."""
        return LinkedInMetrics.from_response(
            self._get(
                "/linkedin-metrics",
                {"startDate": start_date, "endDate": end_date},
            )
        )

    def list_creatives(
        self,
        page_size: int = 100,
        cursor: Optional[str] = None,
    ) -> Tuple[List[Creative], Optional[str]]:
        """Return a page of own creatives and the next-page cursor (or None)."""
        body = self._get(
            "/creatives",
            {"pageSize": page_size, "cursor": cursor},
        )
        data = (body or {}).get("data") or []
        next_cursor: Optional[str] = ((body or {}).get("pagination") or {}).get(
            "nextCursor"
        )
        creatives = [Creative.model_validate(c) for c in data]
        return creatives, next_cursor

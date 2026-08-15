"""LinkedIn Ad Library API client (Layer 2 shared toolkit).

A thin, framework-agnostic wrapper over the single Ad Library search endpoint.
Every behaviour here is grounded in the fixture-backed audit under
``docs/api-knowledge-base/`` — read those before changing this file:

  - ``endpoints.md``   — accepted params, required headers, response envelope.
  - ``constraints.md`` — rejected params, rate limits (429, no ``Retry-After``),
                         token expiry (401), the ``count`` <= 25 cap.

This client deliberately fixes the two silent bugs in the legacy
``src/services/linkedin_client.py``: it NEVER sends ``countries`` or ``adType``
(both always 400 — see ``constraints.md`` §1/§2). It also never sends
``advertiserUrn``, ``advertiserPageUrl``, ``payer``, or any ``dateRange`` /
``searchStartDate`` / ``searchEndDate`` param. Country, ad-type, and date
filtering are all client-side concerns and out of scope for this layer.

Design notes:
  - I/O-light: the access token is read from the argument or, failing that,
    the ``ZENABM_TOKEN`` environment variable (preferred), then the legacy
    ``LINKEDIN_ACCESS_TOKEN`` (kept for backward compatibility). The optional
    base-url override is read from ``ZENABM_API_BASE_URL`` (preferred) or the
    legacy ``LINKEDIN_API_BASE_URL``. No ``load_dotenv``, no file reads — that
    stays in the Layer 3 sub-projects.
  - ``session`` and ``sleep_fn`` are injectable so the whole thing is testable
    with a fake transport and no real sleeping (see ``tests/test_core_client.py``).
"""
from __future__ import annotations

import os
import time
from typing import Any, Callable, Dict, Iterator, List, Optional

import requests

from core.schema import AdElement, AdLibraryResponse, ApiError


class LinkedInApiError(Exception):
    """Raised for a non-200, non-429 response from the Ad Library API.

    Attributes:
        status: The HTTP status code returned.
        error:  The parsed :class:`~core.schema.ApiError` when the response
                body matched LinkedIn's Rest.li error envelope, else ``None``.
        raw:    The raw decoded JSON body (or ``None`` if it did not decode).
    """

    def __init__(
        self,
        status: int,
        error: Optional[ApiError],
        raw: Optional[Any],
    ) -> None:
        self.status = status
        self.error = error
        self.raw = raw
        code = error.code if error is not None else None
        super().__init__(
            f"LinkedIn Ad Library API returned HTTP {status}"
            + (f" (code={code})" if code else "")
        )


class LinkedInAdLibraryClient:
    """Client for the LinkedIn Ad Library search endpoint.

    See the module docstring and ``docs/api-knowledge-base/`` for the full
    contract. In short: one endpoint, ``q=criteria`` always sent, ``advertiser``
    and/or ``keyword`` optional, ``count`` clamped to 25, 429 retried with a
    fixed wait, other errors surfaced as :class:`LinkedInApiError`.
    """

    #: Query params this client will never send — each returns 400 from the API.
    #: (constraints.md §1/§2/§3). Kept for documentation / defensive assertions.
    FORBIDDEN_PARAMS = frozenset(
        {
            "countries",
            "adType",
            "advertiserUrn",
            "advertiserPageUrl",
            "payer",
            "searchStartDate",
            "searchEndDate",
            "dateRange",
            "dateRange.start",
            "dateRange.start.day",
            "dateRange.start.month",
            "dateRange.start.year",
            "dateRange.end",
            "dateRange.end.day",
            "dateRange.end.month",
            "dateRange.end.year",
        }
    )

    #: Server-side hard cap on ``count`` (constraints.md §14).
    MAX_COUNT = 25

    #: The public LinkedIn Ad Library base URL — the effective default when no
    #: ``base_url`` arg and no base-url env override are supplied.
    DEFAULT_BASE_URL = "https://api.linkedin.com/rest/adLibrary"

    def __init__(
        self,
        access_token: Optional[str] = None,
        version: str = "202601",
        base_url: Optional[str] = None,
        session: Optional[requests.Session] = None,
        sleep_fn: Callable[[float], Any] = time.sleep,
        max_retries: int = 3,
        retry_wait_seconds: float = 35.0,
    ) -> None:
        # Env fallback only — no dotenv, no file reads (core stays I/O-light).
        # A missing token is not fatal at construction time; we raise only when
        # a request is actually made, so tests can build a client with no token.
        # Neutral ``ZENABM_TOKEN`` is preferred (hides the data source in the
        # environment); the legacy ``LINKEDIN_ACCESS_TOKEN`` is still accepted so
        # existing .env files keep working.
        self._access_token = (
            access_token
            or os.environ.get("ZENABM_TOKEN")
            or os.environ.get("LINKEDIN_ACCESS_TOKEN")
        )
        self.version = version
        # Base-url precedence: explicit arg > neutral ``ZENABM_API_BASE_URL`` >
        # legacy ``LINKEDIN_API_BASE_URL`` > the public default. The env override
        # lets a future ZenABM proxy be a one-line change.
        self.base_url = (
            base_url
            or os.environ.get("ZENABM_API_BASE_URL")
            or os.environ.get("LINKEDIN_API_BASE_URL")
            or self.DEFAULT_BASE_URL
        )
        self.session = session if session is not None else requests.Session()
        self.sleep_fn = sleep_fn
        self.max_retries = max_retries
        self.retry_wait_seconds = retry_wait_seconds

    # ── Headers ────────────────────────────────────────────────────────────

    def _headers(self) -> Dict[str, str]:
        if not self._access_token:
            raise ValueError(
                "No access token. Pass access_token=... or set the ZENABM_TOKEN "
                "environment variable (the legacy LINKEDIN_ACCESS_TOKEN is also "
                "accepted). Tokens expire (~26 days) and must be regenerated — "
                "see docs/api-knowledge-base/constraints.md §7."
            )
        return {
            "Authorization": f"Bearer {self._access_token}",
            "LinkedIn-Version": self.version,
            "X-Restli-Protocol-Version": "2.0.0",
        }

    # ── Low-level GET with 429 retry ───────────────────────────────────────

    def _get(self, params: Dict[str, Any]) -> Any:
        """Perform one logical GET, retrying on HTTP 429.

        Returns the decoded JSON body on 200. Raises :class:`LinkedInApiError`
        on any other non-200 status, and after exhausting retries on 429.
        """
        headers = self._headers()

        # Defense-in-depth: never let a forbidden param (each 400s — see
        # constraints.md §1/§2/§3) reach the wire. This should never trigger;
        # it guards against a future caller building params by hand.
        assert not (set(params) & self.FORBIDDEN_PARAMS), (
            "Refusing to send forbidden Ad Library params: "
            f"{sorted(set(params) & self.FORBIDDEN_PARAMS)}"
        )

        attempts = 0
        while True:
            response = self.session.get(self.base_url, headers=headers, params=params)
            status = response.status_code

            if status == 200:
                return response.json()

            if status == 429:
                # LinkedIn sends no Retry-After header (constraints.md §6).
                # Wait a fixed interval and retry up to max_retries times.
                if attempts >= self.max_retries:
                    raise LinkedInApiError(
                        status, self._parse_error(response), self._safe_json(response)
                    )
                attempts += 1
                self.sleep_fn(self.retry_wait_seconds)
                continue

            # Any other non-200: surface as a structured error immediately.
            raise LinkedInApiError(
                status, self._parse_error(response), self._safe_json(response)
            )

    @staticmethod
    def _safe_json(response: Any) -> Optional[Any]:
        try:
            return response.json()
        except Exception:
            return None

    @classmethod
    def _parse_error(cls, response: Any) -> Optional[ApiError]:
        body = cls._safe_json(response)
        if body is None:
            return None
        try:
            return ApiError.model_validate(body)
        except Exception:
            return None

    # ── Public API ─────────────────────────────────────────────────────────

    def search(
        self,
        advertiser: Optional[str] = None,
        keyword: Optional[str] = None,
        start: int = 0,
        count: int = 25,
    ) -> AdLibraryResponse:
        """Search the Ad Library for a single page of results.

        Args:
            advertiser: Fuzzy advertiser-name match (constraints.md §12 —
                results collide; filter by company id downstream).
            keyword: Full-text search of ad copy. May be combined with
                ``advertiser``.
            start: Pagination offset.
            count: Page size. Clamped to :attr:`MAX_COUNT` (25).

        Returns:
            A validated :class:`~core.schema.AdLibraryResponse`.

        Raises:
            ValueError: If no access token is available.
            LinkedInApiError: On any non-200 (after 429 retries are exhausted).
        """
        params: Dict[str, Any] = {
            "q": "criteria",
            "start": start,
            # Clamp on both ends: the API 400s on count<=0 and caps at MAX_COUNT.
            "count": max(1, min(count, self.MAX_COUNT)),
        }
        # Skip empty/whitespace-only optional filters — sending ``advertiser=""``
        # (or ``keyword=""``) 400s the API. Only send them when non-blank.
        if advertiser and advertiser.strip():
            params["advertiser"] = advertiser
        if keyword and keyword.strip():
            params["keyword"] = keyword

        body = self._get(params)
        return AdLibraryResponse.model_validate(body)

    def iter_ads(
        self,
        advertiser: Optional[str] = None,
        keyword: Optional[str] = None,
        max_ads: Optional[int] = None,
        page_size: int = 25,
        page_sleep: float = 4.0,
    ) -> Iterator[AdElement]:
        """Yield :class:`~core.schema.AdElement` across all pages of a search.

        Pagination follows ``paging.links`` where ``rel == "next"``. When no
        "next" link is present it falls back to incrementing ``start`` by
        ``page_size`` and stops once ``start >= paging.total`` or a page comes
        back empty. Between pages it sleeps ``page_sleep`` seconds via the
        injected ``sleep_fn`` to stay under the burst rate limit
        (constraints.md §6).

        Never implements "stop when we hit old ads" — ordering is deterministic
        but jittery (constraints.md §5); date filtering is a client-side concern.

        Args:
            advertiser: Fuzzy advertiser-name match.
            keyword: Full-text ad-copy search.
            max_ads: Stop after yielding this many ads. ``None`` means no cap
                (bounded only by the result set / your quota).
            page_size: Per-request page size (clamped to 25 by ``search``).
            page_sleep: Seconds to sleep between page requests.
        """
        yielded = 0
        start = 0
        first_page = True

        while True:
            if not first_page:
                self.sleep_fn(page_sleep)
            first_page = False

            page = self.search(
                advertiser=advertiser,
                keyword=keyword,
                start=start,
                count=page_size,
            )

            if not page.elements:
                return

            for ad in page.elements:
                yield ad
                yielded += 1
                if max_ads is not None and yielded >= max_ads:
                    return

            # Decide whether another page exists and where it starts.
            next_start = self._next_start(page, start, page_size)
            if next_start is None:
                return
            start = next_start

    @staticmethod
    def _next_start(
        page: AdLibraryResponse, current_start: int, page_size: int
    ) -> Optional[int]:
        """Return the ``start`` for the next page, or ``None`` if this is the last.

        Prefer the server-provided ``rel == "next"`` link (parsing its ``start``
        query param); fall back to incrementing ``current_start`` by ``page_size``
        while ``start < paging.total``.
        """
        links = page.paging.links or []
        for link in links:
            if link.rel == "next":
                parsed = _extract_start(link.href)
                # Only trust the server "next" link when it STRICTLY ADVANCES
                # past the current start. A self-referential / non-advancing
                # "next" (e.g. start=0 again) would loop forever, so we fall
                # through to the bounded increment path instead.
                if parsed is not None and parsed > current_start:
                    return parsed
                # "next" present but not advancing (or unparseable): fall through
                # to the bounded increment fallback.
                break

        candidate = current_start + page_size
        if candidate < page.paging.total:
            return candidate
        return None


def _extract_start(href: str) -> Optional[int]:
    """Pull the integer ``start`` value out of a paging link href, if present."""
    from urllib.parse import parse_qs, urlparse

    query = urlparse(href).query
    values = parse_qs(query).get("start")
    if not values:
        return None
    try:
        return int(values[0])
    except (TypeError, ValueError):
        return None

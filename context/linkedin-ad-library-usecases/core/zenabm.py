"""ZenABM interface (Layer 2 shared toolkit) — used by skills 1 & 2.

ZenABM is the user's own product; it holds the user's *own* LinkedIn ad
performance (impressions, spend, clicks — richer than the public Ad Library).
Skills compare Ad-Library competitor data (via ``core.client`` + ``core.signals``)
against the user's own numbers fetched from ZenABM.

Important architectural note
----------------------------
The real ZenABM data is served over an **MCP server**, and MCP tools are invoked
by the Claude Code agent/harness — *not* by arbitrary Python in this package.
So this module deliberately does NOT open network/MCP connections itself. Instead
it provides:

  * :class:`MyAdPerformance` — the typed data contract for the user's own
    per-keyword performance.
  * :class:`ZenABMClient` — a ``Protocol`` that skill code (``compare.py``)
    depends on, so it never hard-codes where the numbers come from.
  * :class:`StubZenABMClient` — an in-memory implementation for tests/demos.
  * :func:`MyAdPerformance.from_mcp_result` — builds the contract from whatever
    dict the ZenABM MCP tool returns, so a SKILL.md flow can do:
    "call the ZenABM MCP tool → pass its JSON here → feed the client to compare".

When the ZenABM MCP tool schema is finalized, wire it in via a thin adapter that
implements :class:`ZenABMClient` (see ``# TODO`` in :class:`MCPZenABMClient`).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Protocol, runtime_checkable


@dataclass
class MyAdPerformance:
    """The user's own LinkedIn ad performance for one keyword/theme, from ZenABM.

    All metric fields are optional because ZenABM plans/permissions may expose
    different subsets. ``keyword`` is the only required field. Unlike the public
    Ad Library, ZenABM (the user's own account) can expose real ``spend_usd``,
    ``clicks`` and ``ctr`` — that asymmetry is the whole point of the comparison.
    """

    keyword: str
    n_ads: Optional[int] = None
    impressions: Optional[int] = None
    spend_usd: Optional[float] = None
    clicks: Optional[int] = None
    ctr: Optional[float] = None
    #: Anything else ZenABM returned that we don't model explicitly.
    extra: Dict[str, object] = field(default_factory=dict)

    @classmethod
    def from_mcp_result(cls, keyword: str, result: Dict[str, object]) -> "MyAdPerformance":
        """Build from a raw ZenABM MCP tool result dict.

        Tolerant of key naming (``impressions``/``total_impressions``, etc.) and
        stashes unrecognized keys in ``extra``. Adjust the alias lists once the
        ZenABM MCP schema is fixed.
        """
        def pick(*names: str) -> Optional[object]:
            for n in names:
                if n in result and result[n] is not None:
                    return result[n]
            return None

        known = {
            "n_ads": pick("n_ads", "ad_count", "ads"),
            "impressions": pick("impressions", "total_impressions", "impression_count"),
            "spend_usd": pick("spend_usd", "spend", "total_spend"),
            "clicks": pick("clicks", "total_clicks"),
            "ctr": pick("ctr", "click_through_rate"),
        }
        consumed = {
            "n_ads", "ad_count", "ads",
            "impressions", "total_impressions", "impression_count",
            "spend_usd", "spend", "total_spend",
            "clicks", "total_clicks",
            "ctr", "click_through_rate",
        }
        extra = {k: v for k, v in result.items() if k not in consumed}
        return cls(
            keyword=keyword,
            n_ads=_as_int(known["n_ads"]),
            impressions=_as_int(known["impressions"]),
            spend_usd=_as_float(known["spend_usd"]),
            clicks=_as_int(known["clicks"]),
            ctr=_as_float(known["ctr"]),
            extra=extra,
        )


@runtime_checkable
class ZenABMClient(Protocol):
    """What skill code needs from ZenABM. Depend on this, not a concrete class."""

    def get_keyword_performance(self, keyword: str) -> Optional[MyAdPerformance]:
        """Return the user's own performance for ``keyword``, or None if untracked."""
        ...

    def list_tracked_keywords(self) -> List[str]:
        """Keywords/themes the user's ZenABM account is running ads on."""
        ...


class StubZenABMClient:
    """In-memory :class:`ZenABMClient` for tests and offline demos.

    Seed it with sample data::

        client = StubZenABMClient({
            "product analytics": MyAdPerformance("product analytics",
                                                 n_ads=4, impressions=52000, spend_usd=8000),
        })
    """

    def __init__(self, data: Optional[Dict[str, MyAdPerformance]] = None) -> None:
        # Normalize keys at construction so lookups are genuinely case- and
        # whitespace-insensitive (e.g. "Product Analytics" == " product analytics").
        self._data: Dict[str, MyAdPerformance] = {
            k.strip().casefold(): v for k, v in (data or {}).items()
        }

    def get_keyword_performance(self, keyword: str) -> Optional[MyAdPerformance]:
        return self._data.get(keyword.strip().casefold())

    def list_tracked_keywords(self) -> List[str]:
        return list(self._data.keys())


class MCPZenABMClient:
    """Placeholder adapter for the real ZenABM MCP server.

    Not implemented: MCP tools are invoked by the Claude Code agent, not by this
    library. The intended pattern is that a SKILL.md flow calls the ZenABM MCP
    tool, then constructs :meth:`MyAdPerformance.from_mcp_result` and feeds a
    :class:`StubZenABMClient` (or a real adapter) into ``compare``.
    """

    def __init__(self, *_: object, **__: object) -> None:  # pragma: no cover
        raise NotImplementedError(
            "ZenABM MCP is invoked by the agent, not this library. Fetch the data "
            "via the ZenABM MCP tool in the skill flow, then use "
            "MyAdPerformance.from_mcp_result(...) + StubZenABMClient. See "
            "docs/architecture.md (Layer 2 core.zenabm) and the skill's SKILL.md."
        )


def _as_int(v: object) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _as_float(v: object) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None

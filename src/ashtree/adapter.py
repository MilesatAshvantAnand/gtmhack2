"""Translate sanitized Ashtree fixture payloads into run-envelope records.

The adapter is intentionally fixture-only: it delegates consent, verification,
coverage, and action-cap policy to :mod:`src.ashtree.runner`, then maps that
policy result to the camelCase ``AshtreeRunEnvelope`` contract. It has no
provider, environment, credential, or send capability.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .runner import run_fixture as _run_policy


def run_fixture(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return a contract-shaped, draft-only envelope for one fixture payload."""

    policy = _run_policy(payload)
    trial = _mapping(payload, "trial")
    competitor = _mapping(payload, "competitor")
    opted_out = trial.get("consent") == "opted_out"
    coverage = _coverage(payload)
    trial_id = _required_text(trial.get("id"), "payload.trial.id")
    envelope: dict[str, Any] = {
        "runId": f"fixture-{trial_id}",
        "trigger": "trial_started",
        "trial": {
            "trialId": trial_id,
            "status": _trial_status(trial.get("status")),
            "accountCanonicalId": f"zenabm:{trial_id}",
            "accountVerification": "verified",
        },
        "suppression": _suppression(payload, opted_out),
        "coverage": coverage,
        "status": "blocked_insufficient_evidence",
        "recommendedActions": [],
        "outreachDrafts": [],
    }

    if opted_out:
        envelope["status"] = "blocked_opt_out"
        envelope["blockReasons"] = list(policy["policyNotes"])
        return envelope

    if policy["outcome"] == "rejected":
        envelope["blockReasons"] = list(policy["policyNotes"])
        return envelope

    actions = _recommendations(policy["recommendedActions"], competitor, coverage)
    if not actions:
        envelope["blockReasons"] = list(policy["policyNotes"])
        return envelope

    envelope["status"] = "drafts_ready_for_review"
    envelope["recommendedActions"] = actions
    envelope["outreachDrafts"] = [_draft(trial_id, actions[0]["sourceIds"])]
    return envelope


def _recommendations(
    actions: object, competitor: Mapping[str, Any], coverage: str
) -> list[dict[str, Any]]:
    if not _verified_competitor(competitor) or not isinstance(actions, list):
        return []

    recommendations: list[dict[str, Any]] = []
    for action in actions[:3]:
        if not isinstance(action, Mapping):
            continue
        source_ids = _source_ids(action.get("evidence"))
        if not source_ids:
            continue
        recommendation = _text(action.get("action"), "")
        if not recommendation:
            continue
        recommendations.append(
            {
                "actionId": _text(action.get("id"), f"action-{len(recommendations) + 1}"),
                "title": "ZenABM next step",
                "recommendation": recommendation,
                "entity": {
                    "name": _text(competitor.get("displayName"), "Verified competitor"),
                    "entityType": "competitor",
                    "canonicalId": competitor["canonicalLinkedinCompanyId"],
                    "verification": "verified",
                },
                "sourceIds": source_ids,
                "coverage": coverage,
                "confidence": _confidence(action.get("confidence")),
                "limitations": _limitations(coverage),
                "owner": {"role": _owner(action.get("owner"))},
                "successMetric": {
                    "name": _text(action.get("successMetric"), "reviewed_next_step"),
                    "measurementWindow": "first_week",
                },
                "humanReview": {"required": True, "status": "pending"},
            }
        )
    return recommendations


def _draft(trial_id: str, source_ids: list[str]) -> dict[str, Any]:
    return {
        "draftId": f"fixture-{trial_id}-draft-1",
        "trialId": trial_id,
        "channel": "email",
        "status": "draft",
        "body": "Review this evidence-linked ZenABM finding before using any outreach.",
        "humanReview": "required",
        "sourceIds": source_ids,
    }


def _suppression(payload: Mapping[str, Any], opted_out: bool) -> dict[str, Any]:
    contact = payload.get("contact")
    trial = payload.get("trial")
    consent = trial.get("consent") if isinstance(trial, Mapping) else None
    result: dict[str, Any] = {
        "checked": True,
        "optedOut": opted_out,
        "marketingStatus": _marketing_status(consent),
    }
    if isinstance(contact, Mapping) and isinstance(contact.get("id"), str) and contact["id"]:
        result["sourceId"] = contact["id"]
    return result


def _coverage(payload: Mapping[str, Any]) -> str:
    coverage = payload.get("coverage")
    if not isinstance(coverage, Mapping):
        return "unknown"
    visibility = coverage.get("publicAdVisibility")
    return visibility if visibility in {"complete", "partial", "unknown"} else "unknown"


def _trial_status(value: object) -> str:
    return value if value in {"active", "inactive", "unknown"} else "unknown"


def _marketing_status(value: object) -> str:
    statuses = {
        "eligible_for_draft": "allowed",
        "opted_out": "opted_out",
        "suppressed": "suppressed",
    }
    return statuses.get(value, "unknown")


def _limitations(coverage: str) -> list[str]:
    if coverage == "unknown":
        return ["Public-ad coverage is unknown; unavailable data is not treated as zero."]
    if coverage == "partial":
        return ["Public-ad visibility is partial; unsupported measurements remain unknown."]
    return []


def _confidence(value: object) -> str:
    if value == "directional":
        return "medium"
    return value if value in {"high", "medium", "low", "unknown"} else "unknown"


def _owner(value: object) -> str:
    return value if value in {"trial_user", "csm", "ae", "marketing_owner"} else "trial_user"


def _verified_competitor(competitor: Mapping[str, Any]) -> bool:
    return (
        competitor.get("verification") == "verified"
        and isinstance(competitor.get("canonicalLinkedinCompanyId"), str)
        and bool(competitor["canonicalLinkedinCompanyId"].strip())
    )


def _source_ids(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return list(dict.fromkeys(item for item in value if isinstance(item, str) and item))


def _mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"payload.{key} must be an object")
    return value


def _text(value: object, fallback: str) -> str:
    return value.strip() if isinstance(value, str) and value.strip() else fallback


def _required_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()

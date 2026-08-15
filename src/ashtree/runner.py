"""Fixture-only policy runner for the Ashtree trial-to-value workflow.

``run_fixture`` consumes the snake_case payloads in ``fixtures/ashtree`` and
returns their snake_case policy outcome. The repository's JSON schemas use a
camelCase run envelope at the boundary; an owning orchestration layer can map
this bounded, review-only result into that envelope without changing policy.

There are intentionally no provider clients, environment reads, or send calls
in this module.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any


CandidateScorer = Callable[[Mapping[str, Any], Mapping[str, Any]], float]


def run_fixture(
    payload: Mapping[str, Any], *, scorer: CandidateScorer | None = None
) -> dict[str, Any]:
    """Evaluate one sanitized trial payload and return a review-only outcome.

    Candidate actions are optional fixture extensions (``candidateActions`` or
    ``candidate_actions``). They are considered only after consent and
    canonical competitor verification pass, and the returned list is capped at
    three. ``scorer`` is injectable so product scoring can be integrated
    without coupling this fixture runner to a provider or model.
    """

    trial = _object(payload, "trial")
    consent = trial.get("consent")
    if consent == "opted_out":
        return _suppressed_outcome()

    if trial.get("status") != "active":
        return _blocked_outcome(
            "The selected trial is not active, so no draft or recommendation may be created."
        )

    competitor = _object(payload, "competitor")
    if not _is_verified(competitor):
        return {
            "outcome": "rejected",
            "competitorUse": "blocked",
            "recommendedActions": [],
            "outreach": {"mode": "no_draft", "sendAllowed": False},
            "policyNotes": [
                "Reject the fuzzy advertiser match until a canonical LinkedIn company ID is verified.",
                "Do not generate competitor findings or outreach from an unverified match.",
            ],
        }

    coverage = _optional_object(payload.get("coverage"), "coverage")
    visibility = coverage.get("publicAdVisibility") if coverage else None
    observations = _objects(payload.get("observations", []), "observations")
    actions = _actions(payload, observations, visibility, scorer)

    if visibility == "unknown":
        return {
            "outcome": "accepted_with_limitations",
            "competitorUse": "limited",
            "recommendedActions": actions,
            "outreach": {"mode": "draft_only", "sendAllowed": False},
            "policyNotes": [
                "No competitor activity, impression, spend, click, creative, or targeting claim may be generated.",
                "Unavailable public-ad coverage is unknown, not zero.",
            ],
        }

    return {
        "outcome": "accepted",
        "competitorUse": "allowed",
        "recommendedActions": actions,
        "outreach": {"mode": "draft_only", "sendAllowed": False},
        "policyNotes": _coverage_notes(visibility, coverage),
    }


def _actions(
    payload: Mapping[str, Any],
    observations: list[dict[str, Any]],
    visibility: Any,
    scorer: CandidateScorer | None,
) -> list[dict[str, Any]]:
    candidates = _objects(
        payload.get("candidateActions", payload.get("candidate_actions", [])),
        "candidate actions",
    )
    if candidates:
        ranked = sorted(
            enumerate(candidates),
            key=lambda item: (-_score(payload, item[1], scorer), item[0]),
        )
        return [_candidate_action(candidate) for _, candidate in ranked[:3]]

    if visibility == "unknown":
        return [
            {
                "id": "action_002",
                "action": "Confirm the trial account's campaign objective before proposing an experiment; public competitor-ad coverage is unavailable for the selected region.",
                "owner": "trial_user",
                "successMetric": "campaign_objective_confirmed",
                "confidence": "unknown",
                "evidence": ["coverage"],
            }
        ]

    evidence = [str(observation["id"]) for observation in observations if observation.get("id")]
    if not evidence:
        return []
    confidence = observations[0].get("confidence", "unknown")
    return [
        {
            "id": "action_001",
            "action": "Review the verified competitor's public ad observation alongside the trial account's current campaign objective and select one ZenABM experiment to test.",
            "owner": "trial_user",
            "successMetric": "experiment_created",
            "confidence": confidence,
            "evidence": evidence,
        }
    ]


def _candidate_action(candidate: Mapping[str, Any]) -> dict[str, Any]:
    """Return only fixture action fields; candidate input never enables send."""

    required = ("id", "action", "owner", "successMetric", "confidence", "evidence")
    missing = [field for field in required if field not in candidate]
    if missing:
        raise ValueError(f"candidate action is missing: {', '.join(missing)}")
    return {field: candidate[field] for field in required}


def _score(
    payload: Mapping[str, Any], candidate: Mapping[str, Any], scorer: CandidateScorer | None
) -> float:
    value = scorer(payload, candidate) if scorer else candidate.get("priority", 0)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("candidate action scores must be numeric")
    return float(value)


def _coverage_notes(visibility: Any, coverage: Mapping[str, Any] | None) -> list[str]:
    if visibility == "partial" and coverage and coverage.get("impressions") == "unknown":
        return [
            "The action does not assert spend, clicks, creative text, targeting, or causal impact.",
            "Public-ad visibility is partial and impressions remain unknown.",
        ]
    if visibility == "partial":
        return ["Public-ad visibility is partial; unsupported measurements remain unknown."]
    return ["Recommendations remain evidence-linked and require human review before any draft is used."]


def _suppressed_outcome() -> dict[str, Any]:
    return {
        "outcome": "suppressed",
        "competitorUse": "not_processed",
        "recommendedActions": [],
        "outreach": {"mode": "no_draft", "draftCreated": False, "sendAllowed": False},
        "policyNotes": [
            "Stop before analysis or draft creation because the trial contact opted out.",
            "A suppression check is required again before any future send attempt.",
        ],
    }


def _blocked_outcome(reason: str) -> dict[str, Any]:
    return {
        "outcome": "rejected",
        "competitorUse": "not_processed",
        "recommendedActions": [],
        "outreach": {"mode": "no_draft", "sendAllowed": False},
        "policyNotes": [reason],
    }


def _is_verified(competitor: Mapping[str, Any]) -> bool:
    return (
        competitor.get("verification") == "verified"
        and isinstance(competitor.get("canonicalLinkedinCompanyId"), str)
        and bool(competitor["canonicalLinkedinCompanyId"].strip())
    )


def _object(payload: Mapping[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"payload.{key} must be an object")
    return dict(value)


def _optional_object(value: Any, label: str) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError(f"payload.{label} must be an object")
    return dict(value)


def _objects(value: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"payload.{label} must be an array")
    if not all(isinstance(item, Mapping) for item in value):
        raise ValueError(f"payload.{label} items must be objects")
    return [dict(item) for item in value]

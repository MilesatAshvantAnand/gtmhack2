"""Fixture-only orchestration for an Ashtree trial-to-value run.

This module intentionally has no provider clients.  It accepts data that has
already been collected (usually sanitized fixtures), ranks candidate actions,
and returns a JSON-serializable envelope for a caller to render or review.
It never reads environment variables and never executes outreach.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


JsonValue = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
CandidateAction = Mapping[str, Any]
ActionScorer = Callable[[Mapping[str, Any], Mapping[str, Any]], float | Mapping[str, Any]]


def run_fixture(
    trial_profile: Mapping[str, Any],
    candidate_actions: Sequence[CandidateAction],
    *,
    scorer: ActionScorer | None = None,
    run_id: str | None = None,
    generated_at: datetime | None = None,
) -> dict[str, JsonValue]:
    """Build a serializable, review-only run envelope from fixture data.

    ``scorer`` receives ``(trial_profile, candidate_action)`` and may return a
    numeric score or a mapping with a numeric ``score`` plus optional metadata.
    No action is executed by this function; callers must keep any report or
    outreach generated from this envelope under human review.
    """

    normalized_profile = _json_object(trial_profile, label="trial_profile")
    ranked_actions = [
        _score_action(normalized_profile, action, scorer, position)
        for position, action in enumerate(candidate_actions)
    ]
    ranked_actions.sort(key=lambda action: (-action["score"], action["input_position"]))

    for rank, action in enumerate(ranked_actions, start=1):
        action["rank"] = rank
        action.pop("input_position")

    timestamp = generated_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    return {
        "run_id": run_id or f"ashtree-{uuid4().hex}",
        "run_type": "fixture_only",
        "generated_at": timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "trial_profile": normalized_profile,
        "candidate_actions": ranked_actions,
        "execution": {
            "network_calls": False,
            "outreach_sent": False,
            "review_required": True,
        },
    }


def _score_action(
    trial_profile: Mapping[str, JsonValue],
    candidate_action: CandidateAction,
    scorer: ActionScorer | None,
    position: int,
) -> dict[str, JsonValue]:
    action = _json_object(candidate_action, label="candidate_action")
    result: float | Mapping[str, Any] = scorer(trial_profile, action) if scorer else _default_score(action)

    if isinstance(result, Mapping):
        details = _json_object(result, label="scorer result")
        score = _numeric_score(details.pop("score", None))
        scoring: dict[str, JsonValue] = {"method": "injected", "details": details}
    else:
        score = _numeric_score(result)
        scoring = {"method": "injected" if scorer else "default"}

    return {
        "action": action,
        "score": score,
        "scoring": scoring,
        "input_position": position,
    }


def _default_score(action: Mapping[str, JsonValue]) -> float:
    """Use an explicit fixture priority when no product scorer is supplied."""

    return _numeric_score(action.get("priority", 0))


def _numeric_score(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("action scores must be numeric")
    return float(value)


def _json_object(value: Mapping[str, Any], *, label: str) -> dict[str, JsonValue]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{label} must be a mapping")
    normalized = _json_value(dict(value), label=label)
    assert isinstance(normalized, dict)
    return normalized


def _json_value(value: Any, *, label: str) -> JsonValue:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {
            str(key): _json_value(item, label=label)
            for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_value(item, label=label) for item in value]
    raise TypeError(f"{label} contains a non-JSON value: {type(value).__name__}")


def main(argv: Sequence[str] | None = None) -> int:
    """Run a fixture payload from disk and print its serializable envelope."""

    parser = argparse.ArgumentParser(description="Run Ashtree fixture-only orchestration.")
    parser.add_argument("payload", type=Path, help="JSON file with trial_profile and candidate_actions")
    arguments = parser.parse_args(argv)

    payload = json.loads(arguments.payload.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        parser.error("payload must be a JSON object")
    try:
        envelope = run_fixture(
            payload["trial_profile"],
            payload["candidate_actions"],
            run_id=payload.get("run_id"),
        )
    except (KeyError, TypeError, ValueError) as error:
        parser.error(str(error))

    print(json.dumps(envelope, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised by the CLI.
    raise SystemExit(main())

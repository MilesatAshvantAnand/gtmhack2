"""Portable checks for the fixture-first Ashtree workflow.

These tests use ``unittest`` so ``python -m unittest`` remains a supported
fallback when pytest is not installed.  Pytest discovers the same tests and
gets its root/fixture helpers from ``conftest.py``.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import unittest
from collections.abc import Mapping
from copy import deepcopy

from jsonschema import Draft202012Validator, ValidationError
from referencing import Registry, Resource

from conftest import FIXTURES_DIR, PROJECT_ROOT, fixture_files, load_fixture


ASHTREE_ADAPTER_MODULE = "src.ashtree.adapter"
ASHTREE_POLICY_MODULE = "src.ashtree.runner"
MANIFEST_PATH = "ashtree/manifest.json"
CONTRACTS_DIR = PROJECT_ROOT / "contracts"


def load_ashtree_adapter():
    """Import the integration adapter once it exists; don't hide its failures."""
    try:
        adapter_spec = importlib.util.find_spec(ASHTREE_ADAPTER_MODULE)
    except ModuleNotFoundError as error:
        if error.name in {"src", "src.ashtree"}:
            return None
        raise
    if adapter_spec is None:
        return None
    return importlib.import_module(ASHTREE_ADAPTER_MODULE)


def load_ashtree_policy():
    return importlib.import_module(ASHTREE_POLICY_MODULE)


def run_envelope_validator() -> Draft202012Validator:
    action_path = CONTRACTS_DIR / "recommended-action.schema.json"
    envelope_path = CONTRACTS_DIR / "ashtree-run-envelope.schema.json"
    with action_path.open(encoding="utf-8") as schema_file:
        action_schema = json.load(schema_file)
    with envelope_path.open(encoding="utf-8") as schema_file:
        envelope_schema = json.load(schema_file)
    registry = Registry().with_resource(
        action_schema["$id"], Resource.from_contents(action_schema)
    )
    return Draft202012Validator(envelope_schema, registry=registry)


class AshtreeHarnessTests(unittest.TestCase):
    def test_project_root_and_fixture_directory_are_discoverable(self) -> None:
        self.assertTrue((PROJECT_ROOT / "pyproject.toml").is_file())
        self.assertTrue(FIXTURES_DIR.is_dir())
        self.assertEqual(tuple(fixture_files()), tuple(sorted(fixture_files())))

    def test_fixture_loader_reads_sanitized_json_when_fixtures_arrive(self) -> None:
        fixtures = tuple(fixture_files())
        if not fixtures:
            self.assertEqual(fixtures, ())
            return

        relative_name = fixtures[0].relative_to(FIXTURES_DIR).as_posix()
        self.assertIsInstance(load_fixture(relative_name), (dict, list))

    def test_integrated_fixture_adapter_preserves_public_contract(self) -> None:
        adapter = load_ashtree_adapter()
        if adapter is None:
            self.skipTest("src.ashtree.adapter has not been added to this worktree yet")

        self.assertTrue(
            hasattr(adapter, "run_fixture"),
            "src.ashtree.adapter must expose run_fixture(payload)",
        )
        if not (CONTRACTS_DIR / "ashtree-run-envelope.schema.json").is_file():
            self.skipTest("Ashtree run-envelope contracts have not been added yet")
        manifest = load_fixture(MANIFEST_PATH)
        self.assertIsInstance(manifest, Mapping)
        self.assertIn("cases", manifest)
        policy = load_ashtree_policy()
        validator = run_envelope_validator()

        for case in manifest["cases"]:
            with self.subTest(case=case["id"]):
                payload = load_fixture(f"ashtree/{case['input']}")
                expected = load_fixture(f"ashtree/{case['expected']}")
                self.assertEqual(policy.run_fixture(payload), expected)
                result = adapter.run_fixture(payload)
                validator.validate(result)
                self._assert_run_envelope(result)
                self._assert_case_rules(case["id"], payload, result)

    def test_run_envelope_schema_rejects_send_state_and_raw_provider_data(self) -> None:
        schema_path = CONTRACTS_DIR / "ashtree-run-envelope.schema.json"
        if not schema_path.is_file():
            self.skipTest("Ashtree run-envelope contracts have not been added yet")
        validator = run_envelope_validator()
        valid_blocked = {
            "runId": "fixture-contract-check",
            "trigger": "manual_selected_trial",
            "trial": {
                "trialId": "trial-contract-check",
                "status": "active",
                "accountCanonicalId": "zenabm:trial-contract-check",
                "accountVerification": "verified",
            },
            "suppression": {
                "checked": True,
                "optedOut": False,
                "marketingStatus": "allowed",
            },
            "coverage": "unknown",
            "status": "blocked_insufficient_evidence",
            "recommendedActions": [],
            "outreachDrafts": [],
            "blockReasons": ["Contract validation fixture."],
        }
        validator.validate(valid_blocked)

        sent = deepcopy(valid_blocked)
        sent["status"] = "sent"
        with self.assertRaises(ValidationError):
            validator.validate(sent)

        raw_provider_data = deepcopy(valid_blocked)
        raw_provider_data["rawProviderData"] = {"contact": "forbidden"}
        with self.assertRaises(ValidationError):
            validator.validate(raw_provider_data)

    def _assert_run_envelope(self, result: object) -> None:
        self.assertIsInstance(result, Mapping)
        for key in (
            "runId",
            "trigger",
            "trial",
            "suppression",
            "coverage",
            "status",
            "recommendedActions",
            "outreachDrafts",
        ):
            self.assertIn(key, result)
        self.assertIn(result["coverage"], {"complete", "partial", "unknown"})
        self.assertTrue(result["suppression"].get("checked"))
        self.assertIsInstance(result["recommendedActions"], list)
        self.assertIsInstance(result["outreachDrafts"], list)

        for action in result["recommendedActions"]:
            self.assertTrue(action["sourceIds"], "actions require source evidence")
            self.assertIn(action["coverage"], {"complete", "partial", "unknown"})
            self.assertIn(action["confidence"], {"high", "medium", "low", "unknown"})
            self.assertEqual(action["entity"].get("verification"), "verified")
            self.assertTrue(action["humanReview"].get("required"))
            self.assertEqual(action["humanReview"].get("status"), "pending")

        for draft in result["outreachDrafts"]:
            self.assertEqual(draft.get("status"), "draft")
            self.assertEqual(draft.get("humanReview"), "required")
            self.assertTrue(draft.get("sourceIds"), "drafts require source evidence")

    def _assert_case_rules(
        self, case_id: str, payload: Mapping[str, object], result: Mapping[str, object]
    ) -> None:
        if case_id == "opted-out-draft-only":
            self.assertEqual(payload["trial"]["consent"], "opted_out")
            self.assertTrue(result["suppression"].get("optedOut"))
            self.assertEqual(result["status"], "blocked_opt_out")
            self.assertEqual(result["recommendedActions"], [])
            self.assertEqual(result["outreachDrafts"], [])
            return

        if case_id == "unverified-competitor-rejection":
            self.assertEqual(result["status"], "blocked_insufficient_evidence")
            self.assertEqual(result["recommendedActions"], [])
            self.assertEqual(result["outreachDrafts"], [])
            return

        coverage = payload.get("coverage", {})
        if coverage.get("publicAdVisibility") == "unknown":
            self.assertEqual(result["coverage"], "unknown")
            self.assertEqual(result["status"], "blocked_insufficient_evidence")
            self.assertEqual(result["recommendedActions"], [])
            self.assertEqual(result["outreachDrafts"], [])
        if case_id == "verified-competitor":
            self.assertEqual(result["coverage"], "partial")
            self.assertTrue(result["recommendedActions"])

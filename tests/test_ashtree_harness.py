"""Portable checks for the fixture-first Ashtree workflow.

These tests use ``unittest`` so ``python -m unittest`` remains a supported
fallback when pytest is not installed.  Pytest discovers the same tests and
gets its root/fixture helpers from ``conftest.py``.
"""

from __future__ import annotations

import importlib
import importlib.util
import unittest
from collections.abc import Mapping

from conftest import FIXTURES_DIR, PROJECT_ROOT, fixture_files, load_fixture


ASHTREE_ADAPTER_MODULE = "src.ashtree.adapter"
MANIFEST_PATH = "ashtree/manifest.json"


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
        manifest = load_fixture(MANIFEST_PATH)
        self.assertIsInstance(manifest, Mapping)
        self.assertIn("cases", manifest)

        for case in manifest["cases"]:
            with self.subTest(case=case["id"]):
                payload = load_fixture(f"ashtree/{case['input']}")
                result = adapter.run_fixture(payload)
                self._assert_run_envelope(result)
                self._assert_case_rules(case["id"], payload, result)

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

        coverage = payload.get("coverage", {})
        if coverage.get("publicAdVisibility") == "unknown":
            self.assertEqual(result["coverage"], "unknown")
        if case_id == "verified-competitor":
            self.assertEqual(result["coverage"], "partial")
            self.assertTrue(result["recommendedActions"])

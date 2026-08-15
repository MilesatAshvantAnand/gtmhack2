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


ASHTREE_MODULE = "src.ashtree"


def load_ashtree_module():
    """Import the implementation once it exists; don't hide import failures."""
    if importlib.util.find_spec(ASHTREE_MODULE) is None:
        return None
    return importlib.import_module(ASHTREE_MODULE)


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

    def test_ashtree_fixture_run_preserves_review_and_evidence_rules(self) -> None:
        module = load_ashtree_module()
        if module is None:
            self.skipTest("src.ashtree has not been added to this worktree yet")

        fixtures = tuple(fixture_files())
        self.assertTrue(fixtures, "src.ashtree requires a checked-in JSON fixture")
        self.assertTrue(
            hasattr(module, "run_fixture"),
            "src.ashtree must expose run_fixture(payload) for local-only runs",
        )

        payload = load_fixture(fixtures[0].relative_to(FIXTURES_DIR).as_posix())
        result = module.run_fixture(payload)
        self.assertIsInstance(result, Mapping)

        for key in ("evidence", "coverage", "outreach"):
            self.assertIn(key, result)
        self.assertIn(result["coverage"], {"complete", "partial", "unknown"})
        self.assertIsInstance(result["evidence"], list)
        self.assertTrue(result["evidence"], "recommendations need source evidence")
        self.assertEqual(result["outreach"].get("status"), "draft")
        self.assertNotIn("send", result["outreach"])


from __future__ import annotations

import unittest

from src.ashtree import run_fixture


def eligible_payload() -> dict[str, object]:
    return {
        "trial": {
            "id": "trial_fixture_001",
            "status": "active",
            "consent": "eligible_for_draft",
        },
        "competitor": {
            "displayName": "Orbit Metrics",
            "canonicalLinkedinCompanyId": "123456",
            "verification": "verified",
        },
        "coverage": {"publicAdVisibility": "partial"},
        "observations": [{"id": "obs_001", "confidence": "directional"}],
    }


class AshtreeRunnerTests(unittest.TestCase):
    def test_public_api_returns_run_envelope(self) -> None:
        result = run_fixture(eligible_payload())

        self.assertEqual(result["status"], "drafts_ready_for_review")
        self.assertEqual(result["trial"]["status"], "active")
        self.assertEqual(result["suppression"]["marketingStatus"], "allowed")
        self.assertIn("runId", result)
        self.assertNotIn("outcome", result)

    def test_missing_or_unknown_consent_fails_closed(self) -> None:
        for consent in (None, "unknown", "suppressed"):
            with self.subTest(consent=consent):
                payload = eligible_payload()
                trial = dict(payload["trial"])
                if consent is None:
                    trial.pop("consent")
                else:
                    trial["consent"] = consent
                payload["trial"] = trial

                result = run_fixture(payload)

                self.assertEqual(result["status"], "blocked_insufficient_evidence")
                self.assertEqual(result["recommendedActions"], [])
                self.assertEqual(result["outreachDrafts"], [])

    def test_missing_trial_identity_is_rejected(self) -> None:
        payload = eligible_payload()
        payload["trial"] = {"status": "active", "consent": "eligible_for_draft"}

        with self.assertRaisesRegex(ValueError, "payload.trial.id"):
            run_fixture(payload)


if __name__ == "__main__":
    unittest.main()

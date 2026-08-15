from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError
from referencing import Registry, Resource

from conftest import PROJECT_ROOT, load_fixture
from src.ashtree import run_fixture
from src.ashtree.runner import run_fixture as run_policy_fixture


CONTRACTS_DIR = PROJECT_ROOT / "contracts"


def load_schemas() -> dict[str, dict[str, object]]:
    schemas: dict[str, dict[str, object]] = {}
    for path in sorted(CONTRACTS_DIR.glob("*.schema.json")):
        with path.open(encoding="utf-8") as schema_file:
            schemas[path.name] = json.load(schema_file)
    return schemas


SCHEMAS = load_schemas()
REGISTRY = Registry().with_resources(
    (schema["$id"], Resource.from_contents(schema)) for schema in SCHEMAS.values()
)


def validator(schema_name: str) -> Draft202012Validator:
    return Draft202012Validator(SCHEMAS[schema_name], registry=REGISTRY)


class ArtifactContractTests(unittest.TestCase):
    def test_every_schema_is_valid_draft_2020_12(self) -> None:
        for name, schema in SCHEMAS.items():
            with self.subTest(schema=name):
                Draft202012Validator.check_schema(schema)

    def test_every_fixture_and_runner_output_validates(self) -> None:
        manifest = load_fixture("ashtree/manifest.json")
        input_validator = validator(manifest["contracts"]["input"])
        expected_validator = validator(manifest["contracts"]["expected"])
        envelope_validator = validator(manifest["contracts"]["runEnvelope"])

        for case in manifest["cases"]:
            with self.subTest(case=case["id"]):
                payload = load_fixture(f"ashtree/{case['input']}")
                expected = load_fixture(f"ashtree/{case['expected']}")
                input_validator.validate(payload)
                expected_validator.validate(expected)
                policy_result = run_policy_fixture(payload)
                self.assertEqual(policy_result, expected)
                expected_validator.validate(policy_result)
                envelope = run_fixture(payload)
                envelope_validator.validate(envelope)
                observation_ids = {
                    observation["id"] for observation in payload.get("observations", [])
                }
                for action in policy_result["recommendedActions"]:
                    self.assertLessEqual(set(action["evidence"]), observation_ids)
                for action in envelope["recommendedActions"]:
                    self.assertLessEqual(set(action["sourceIds"]), observation_ids)

    def test_artifact_flow_is_evidence_linked_and_draft_only(self) -> None:
        evidence = [
            {
                "evidenceId": "evidence-hubspot-status",
                "source": "hubspot_trial",
                "field": "trial.status",
                "value": "active",
                "coverage": "complete",
                "confidence": "high",
            },
            {
                "evidenceId": "evidence-linkedin-active-ads",
                "source": "linkedin_public_ads",
                "field": "activeAdCount",
                "value": 14,
                "coverage": "partial",
                "confidence": "medium",
                "note": "Public-ad coverage does not expose spend, clicks, or hidden targeting.",
            },
        ]
        trial_profile = {
            "trialId": "trial-fixture-contract",
            "company": "Northstar Analytics",
            "domain": "northstar.example",
            "accountCanonicalId": "zenabm:trial-fixture-contract",
            "accountVerification": "verified",
            "status": "active",
            "marketingStatus": "allowed",
            "zenabmConnection": "connected",
            "evidenceIds": ["evidence-hubspot-status"],
        }
        competitor_brief = {
            "briefId": "competitors-fixture-contract",
            "trialId": "trial-fixture-contract",
            "competitors": [
                {
                    "name": "Orbit Metrics",
                    "canonicalLinkedinCompanyId": "123456",
                    "verification": "verified",
                    "activeAdCount": 14,
                    "activityWindowDays": 30,
                    "coverage": "partial",
                    "sourceIds": ["evidence-linkedin-active-ads"],
                    "limitations": ["Public-ad spend and targeting are unavailable."],
                }
            ],
            "coverage": "partial",
            "limitations": ["Public-ad visibility can be incomplete outside the EU/EEA."],
        }
        audit_finding = {
            "findingId": "finding-fixture-contract",
            "trialId": "trial-fixture-contract",
            "category": "competitor_activity",
            "claim": "A verified competitor has 14 active public ads in the configured window.",
            "recommendation": "Review one ZenABM competitor experiment.",
            "coverage": "partial",
            "confidence": "medium",
            "sourceIds": ["evidence-linkedin-active-ads"],
            "limitations": ["The source does not expose spend, clicks, or hidden targeting."],
        }
        value_brief = {
            "briefId": "value-fixture-contract",
            "trialId": "trial-fixture-contract",
            "headline": "A verified competitor is actively advertising on LinkedIn.",
            "opportunities": [
                {
                    "findingId": "finding-fixture-contract",
                    "claim": audit_finding["claim"],
                    "recommendation": audit_finding["recommendation"],
                    "sourceIds": audit_finding["sourceIds"],
                    "coverage": audit_finding["coverage"],
                    "confidence": audit_finding["confidence"],
                    "limitations": audit_finding["limitations"],
                }
            ],
            "nextStep": "Review the evidence in ZenABM before choosing an experiment.",
            "coverage": "partial",
            "limitations": ["Directional public-ad evidence only."],
        }
        outreach_draft = {
            "draftId": "draft-fixture-contract",
            "trialId": "trial-fixture-contract",
            "channel": "email",
            "status": "draft",
            "subject": "A LinkedIn ad observation for Northstar",
            "body": "I prepared a source-linked observation for your review.",
            "sourceIds": ["evidence-linkedin-active-ads"],
            "humanReview": "required",
        }

        artifacts = {
            "evidence.schema.json": evidence,
            "trial-profile.schema.json": [trial_profile],
            "competitor-brief.schema.json": [competitor_brief],
            "audit-finding.schema.json": [audit_finding],
            "value-brief.schema.json": [value_brief],
            "outreach-draft.schema.json": [outreach_draft],
        }
        for schema_name, records in artifacts.items():
            for record in records:
                with self.subTest(schema=schema_name):
                    validator(schema_name).validate(record)

        evidence_ids = {record["evidenceId"] for record in evidence}
        referenced_ids = set(trial_profile["evidenceIds"])
        referenced_ids.update(competitor_brief["competitors"][0]["sourceIds"])
        referenced_ids.update(audit_finding["sourceIds"])
        referenced_ids.update(value_brief["opportunities"][0]["sourceIds"])
        referenced_ids.update(outreach_draft["sourceIds"])
        self.assertLessEqual(referenced_ids, evidence_ids)

    def test_unknown_finding_requires_unknown_confidence_and_limitations(self) -> None:
        finding = {
            "findingId": "finding-unknown",
            "trialId": "trial-unknown",
            "category": "qualification",
            "claim": "CRM technology could not be determined.",
            "recommendation": "Stop before enrichment or outreach.",
            "coverage": "unknown",
            "confidence": "medium",
            "sourceIds": ["evidence-crm-unknown"],
        }

        with self.assertRaises(ValidationError):
            validator("audit-finding.schema.json").validate(finding)

        finding["confidence"] = "unknown"
        finding["limitations"] = ["The website response did not expose a permitted marker."]
        validator("audit-finding.schema.json").validate(finding)

    def test_outreach_contract_rejects_send_fields(self) -> None:
        draft = {
            "draftId": "draft-no-send",
            "trialId": "trial-no-send",
            "channel": "email",
            "status": "draft",
            "body": "Review this source-linked draft.",
            "sourceIds": ["evidence-1"],
            "humanReview": "required",
        }
        validator("outreach-draft.schema.json").validate(draft)

        send_attempt = deepcopy(draft)
        send_attempt["send"] = True
        with self.assertRaises(ValidationError):
            validator("outreach-draft.schema.json").validate(send_attempt)

    def test_unknown_states_reject_zero_high_confidence_and_missing_limits(self) -> None:
        unknown_evidence = {
            "evidenceId": "evidence-unknown",
            "source": "website_technology",
            "field": "crmDetection",
            "value": 0,
            "coverage": "unknown",
            "confidence": "high",
            "note": "No permitted marker was available.",
        }
        with self.assertRaises(ValidationError):
            validator("evidence.schema.json").validate(unknown_evidence)

        unknown_evidence.pop("value")
        unknown_evidence["confidence"] = "unknown"
        validator("evidence.schema.json").validate(unknown_evidence)

        unknown_competitor = {
            "briefId": "competitors-unknown",
            "trialId": "trial-unknown",
            "competitors": [
                {
                    "name": "Orbit Metrics",
                    "canonicalLinkedinCompanyId": "123456",
                    "verification": "verified",
                    "activeAdCount": 0,
                    "activityWindowDays": 30,
                    "coverage": "unknown",
                    "sourceIds": ["evidence-unknown"],
                    "limitations": ["Public-ad coverage is unavailable."],
                }
            ],
            "coverage": "unknown",
        }
        with self.assertRaises(ValidationError):
            validator("competitor-brief.schema.json").validate(unknown_competitor)

        unknown_opportunity = {
            "briefId": "value-unknown",
            "trialId": "trial-unknown",
            "headline": "Qualification is unknown.",
            "opportunities": [
                {
                    "findingId": "finding-unknown",
                    "claim": "CRM technology could not be determined.",
                    "recommendation": "Stop before enrichment.",
                    "sourceIds": ["evidence-unknown"],
                    "coverage": "unknown",
                    "confidence": "high",
                }
            ],
            "nextStep": "Collect permitted evidence.",
            "coverage": "unknown",
        }
        with self.assertRaises(ValidationError):
            validator("value-brief.schema.json").validate(unknown_opportunity)

    def test_fixture_contract_and_runner_fail_closed_on_missing_evidence(self) -> None:
        payload = load_fixture("ashtree/verified-competitor.input.json")
        missing_coverage = deepcopy(payload)
        missing_coverage.pop("coverage")
        with self.assertRaises(ValidationError):
            validator("ashtree-fixture-input.schema.json").validate(missing_coverage)
        result = run_fixture(missing_coverage)
        self.assertEqual(result["status"], "blocked_insufficient_evidence")
        self.assertEqual(result["outreachDrafts"], [])

        source_less = deepcopy(payload)
        source_less["observations"][0].pop("source")
        source_less["observations"][0].pop("statement")
        with self.assertRaises(ValidationError):
            validator("ashtree-fixture-input.schema.json").validate(source_less)
        result = run_fixture(source_less)
        self.assertEqual(result["status"], "blocked_insufficient_evidence")
        self.assertEqual(result["outreachDrafts"], [])

        no_observations = deepcopy(payload)
        no_observations["observations"] = []
        validator("ashtree-fixture-input.schema.json").validate(no_observations)
        policy_result = run_policy_fixture(no_observations)
        validator("ashtree-policy-outcome.schema.json").validate(policy_result)
        envelope = run_fixture(no_observations)
        validator("ashtree-run-envelope.schema.json").validate(envelope)
        self.assertEqual(envelope["status"], "blocked_insufficient_evidence")

    def test_candidate_actions_require_resolvable_evidence(self) -> None:
        payload = load_fixture("ashtree/verified-competitor.input.json")
        payload["candidateActions"] = [
            {
                "id": "action-candidate",
                "action": "Review the verified public observation in ZenABM.",
                "owner": "trial_user",
                "successMetric": "observation_reviewed",
                "confidence": "directional",
                "evidence": ["obs_001"],
                "priority": 10,
            }
        ]
        validator("ashtree-fixture-input.schema.json").validate(payload)
        result = run_policy_fixture(payload)
        self.assertEqual(result["recommendedActions"][0]["id"], "action-candidate")

        payload["candidateActions"][0]["evidence"] = ["missing-observation"]
        with self.assertRaisesRegex(ValueError, "resolve to observation IDs"):
            run_policy_fixture(payload)

    def test_no_draft_policy_rejects_draft_created_true(self) -> None:
        outcome = load_fixture("ashtree/inactive-trial-rejection.expected.json")
        outcome["outreach"]["draftCreated"] = True

        with self.assertRaises(ValidationError):
            validator("ashtree-policy-outcome.schema.json").validate(outcome)

    def test_review_ready_contract_rejects_unknown_high_confidence_action(self) -> None:
        payload = load_fixture("ashtree/verified-competitor.input.json")
        envelope = run_fixture(payload)
        envelope["coverage"] = "unknown"
        action = envelope["recommendedActions"][0]
        action["coverage"] = "unknown"
        action["confidence"] = "high"
        action["limitations"] = []

        with self.assertRaises(ValidationError):
            validator("recommended-action.schema.json").validate(action)
        with self.assertRaises(ValidationError):
            validator("ashtree-run-envelope.schema.json").validate(envelope)


if __name__ == "__main__":
    unittest.main()

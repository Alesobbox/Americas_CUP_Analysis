"""Focused unit tests for race attempts, family reconciliation, and outcome evidence (T05)."""
import json
from pathlib import Path
import unittest

from pipeline.kinematic_ml.labels import (
    construct_family_and_attempt,
    reconcile_attempts_and_families,
    build_outcome_evidence_ledger,
    freeze_evaluation_families,
)

ROOT = Path(__file__).resolve().parents[2]


class TestAC75AttemptsAndOutcomes(unittest.TestCase):
    def test_stopped_and_resailed_race_family(self):
        """Verify stopped race and resail share family_id but only resail is scored."""
        rec_stopped = {
            "filename": "24 09 28 BCN LV Finals Match 3 GBRvITA (stopped).jsonl",
            "stage": "final",
            "domain": "competitive",
            "date": "2024-09-28",
            "sample_competitors": ["INEOS", "LUNA_ROSSA"],
        }
        rec_resail = {
            "filename": "24 09 29 BCN LV Finals Match 3 GBRvITA Re-Sail.jsonl",
            "stage": "final",
            "domain": "competitive",
            "date": "2024-09-29",
            "sample_competitors": ["INEOS", "LUNA_ROSSA"],
        }
        att_stopped = construct_family_and_attempt(rec_stopped)
        att_resail = construct_family_and_attempt(rec_resail)

        # Same family ID
        self.assertEqual(att_stopped.family_id, att_resail.family_id)
        # Distinct attempt IDs
        self.assertNotEqual(att_stopped.attempt_id, att_resail.attempt_id)
        # Only resail is scored
        self.assertFalse(att_stopped.scored_outcome_eligible)
        self.assertTrue(att_resail.scored_outcome_eligible)
        self.assertEqual(att_stopped.linked_resail_attempt_id, att_resail.attempt_id)

    def test_practice_session_domain_isolation(self):
        """Practice attempts provide physical motion rows but cannot enter scored outcomes."""
        rec_practice = {
            "filename": "24 08 02 BCN OP2 S1P1.jsonl",
            "stage": "official_practice",
            "domain": "practice",
            "date": "2024-08-02",
            "sample_competitors": ["ETNZ", "INEOS"],
        }
        att_practice = construct_family_and_attempt(rec_practice)
        self.assertEqual(att_practice.domain, "practice")
        self.assertFalse(att_practice.scored_outcome_eligible)
        self.assertEqual(att_practice.status, "practice_session")

    def test_reconcile_full_archive_attempts_and_families(self):
        """Reconciliation across all 115 AC75 files ensures no family has multiple scored attempts."""
        manifest_files = list((ROOT / ".forecast" / "ac75_learning" / "sources").glob("*/manifest.json"))
        manifest = json.loads(manifest_files[-1].read_text(encoding="utf-8"))

        reconciled = reconcile_attempts_and_families(manifest)
        self.assertEqual(reconciled["total_ac75_sources"], 115)
        self.assertGreater(reconciled["total_ac75_families"], 50)

    def test_field_level_outcome_evidence_provenance(self):
        """Verify outcome evidence ledger retains field-level provenance and identifies Match telemetry absence."""
        manifest_files = list((ROOT / ".forecast" / "ac75_learning" / "sources").glob("*/manifest.json"))
        manifest = json.loads(manifest_files[-1].read_text(encoding="utf-8"))

        ledger_data = build_outcome_evidence_ledger(manifest)
        self.assertEqual(ledger_data["total_races"], 82)
        # Without race-level anchors, unverified candidate results must NOT be marked verified
        self.assertEqual(ledger_data["total_anchor_verified_races"], 0)

        # Check a specific match outcome (e.g. ac37_match_r1)
        match_r1 = next(o for o in ledger_data["outcomes"] if o["family_id"] == "ac37_match_r1")
        self.assertEqual(match_r1["telemetry_status"], "missing_from_archive")
        self.assertFalse(match_r1["winner"]["verified"])
        self.assertEqual(match_r1["winner"]["provenance"], "candidate_results_json")

    def test_competitor_identities_and_100_percent_join(self):
        """Verify no stringified dicts in attempts and 100% of competitive attempts join to outcomes."""
        manifest_files = list((ROOT / ".forecast" / "ac75_learning" / "sources").glob("*/manifest.json"))
        manifest = json.loads(manifest_files[-1].read_text(encoding="utf-8"))

        reconciled = reconcile_attempts_and_families(manifest)
        outcomes_data = build_outcome_evidence_ledger(manifest)

        # 1. No stringified dicts
        for att in reconciled["attempts"]:
            self.assertFalse(att["team_a"].startswith("{"))
            self.assertFalse(att["team_b"].startswith("{"))

        # 2. 100% of competitive families join to outcomes
        outcome_fams = {o["family_id"] for o in outcomes_data["outcomes"]}
        competitive_attempt_fams = {
            f for f in reconciled["families"].keys()
            if not f.startswith("ac37_practice") and not f.startswith("ac40_")
        }
        joined = competitive_attempt_fams & outcome_fams
        self.assertEqual(len(joined), len(competitive_attempt_fams))

    def test_freeze_evaluation_families(self):
        """Verify final evaluation families are frozen based strictly on holdout dates and do not overwrite."""
        manifest_files = list((ROOT / ".forecast" / "ac75_learning" / "sources").glob("*/manifest.json"))
        manifest = json.loads(manifest_files[-1].read_text(encoding="utf-8"))

        frozen = freeze_evaluation_families(manifest)
        self.assertEqual(frozen["reserved_holdout_families_count"], 9)
        self.assertIn("2024-10-04", frozen["holdout_dates"])
        self.assertEqual(len(frozen["holdout_dates"]), 5)
        self.assertIn("content_sha256", frozen)

        # Re-running returns identical frozen assignment
        rerun_frozen = freeze_evaluation_families(manifest)
        self.assertEqual(frozen["content_sha256"], rerun_frozen["content_sha256"])


if __name__ == "__main__":
    unittest.main()

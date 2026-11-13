"""Focused unit tests for AC37 archive inventory and evidence registration (T02)."""
import json
from pathlib import Path
import unittest

from pipeline.kinematic_ml.inventory import (
    build_source_inventory,
    audit_outcome_evidence,
    reserve_chronological_evaluation_dates,
    parse_date_from_filename,
)

ROOT = Path(__file__).resolve().parents[2]


class TestAC75Inventory(unittest.TestCase):
    def test_filename_date_parsing(self):
        """Test extraction of dates from archive naming schemes."""
        self.assertEqual(parse_date_from_filename("24 08 22 FPR1 Match 1 SUIvFRA.jsonl"), "2024-08-22")
        self.assertEqual(parse_date_from_filename("24 09 14 BCN LVS Match 1 ITAvUSA.ac37"), "2024-09-14")
        self.assertEqual(parse_date_from_filename("24 10 04 BCN LV Finals Match 11 GBRvITA.jsonl"), "2024-10-04")
        self.assertEqual(parse_date_from_filename("2023-09-16 VNR 1.jsonl"), "2023-09-16")
        self.assertIsNone(parse_date_from_filename("random_file.json"))

    def test_archive_accounting_and_ac40_isolation(self):
        """Verify dynamic archive reconciliation and strict AC40 isolation."""
        manifest_files = list((ROOT / ".forecast" / "ac75_learning" / "sources").glob("*/manifest.json"))
        self.assertGreaterEqual(len(manifest_files), 1, "Expected at least one generated manifest.json")
        
        manifest = json.loads(manifest_files[-1].read_text(encoding="utf-8"))
        self.assertEqual(manifest["total_files"], 160)
        self.assertEqual(manifest["ac37_file_count"], 132)
        self.assertEqual(manifest["ac75_file_count"], 115)
        self.assertEqual(manifest["ac75_eligible_jsonl_count"], 100)
        self.assertEqual(manifest["ac75_unsupported_binary_count"], 15)

        sources = manifest["sources"]
        # Verify no AC40 is included
        for s in sources:
            if s["boat_class"] == "AC40":
                self.assertEqual(s["status"], "excluded")
                self.assertIn("boat_class_ac40", s["reason_codes"][0])

        # Verify 15 semifinal files are unsupported_wire_schema
        semi_sources = [s for s in sources if s["stage"] == "semifinal"]
        self.assertEqual(len(semi_sources), 15)
        for s in semi_sources:
            self.assertEqual(s["format"], "ac37")
            self.assertEqual(s["status"], "unsupported_wire_schema")
            self.assertIn("binary_protobuf_schema_pending_verification", s["reason_codes"])

    def test_outcome_evidence_and_match_telemetry_gap(self):
        """Verify outcome evidence audit and that America's Cup Match telemetry absence is recorded."""
        evidence = audit_outcome_evidence()
        # 82 total: 16 prelim + 31 round robin (including match 31 tie-breaker) + 15 semifinal + 11 final + 9 match
        self.assertEqual(evidence["total_outcome_races"], 82)
        self.assertEqual(evidence["stage_breakdown"]["preliminary_barcelona_ac75"], 16)
        self.assertEqual(evidence["stage_breakdown"]["round_robin"], 31)
        self.assertEqual(evidence["stage_breakdown"]["lvc_final"], 11)
        self.assertEqual(evidence["stage_breakdown"]["match"], 9)
        self.assertEqual(evidence["stage_breakdown"]["lvc_semifinal_1"] + evidence["stage_breakdown"]["lvc_semifinal_2"], 15)

        # Match physical telemetry gap confirmed
        self.assertEqual(evidence["telemetry_missing_count"], 9)
        self.assertIn("ac37_match_r1", evidence["telemetry_missing_ids"])
        self.assertIn("ac37_match_r9", evidence["telemetry_missing_ids"])

    def test_chronological_evaluation_reservation_metadata_only(self):
        """Verify reservation of latest 20% competitive dates prior to any model tuning."""
        manifest_files = list((ROOT / ".forecast" / "ac75_learning" / "sources").glob("*/manifest.json"))
        manifest = json.loads(manifest_files[-1].read_text(encoding="utf-8"))
        
        reservation = reserve_chronological_evaluation_dates(manifest)
        # All 24 competitive dates are included (including binary semifinals)
        self.assertEqual(reservation["total_competitive_dates"], 24)
        # Latest 20% of 24 dates with ceil = 5 dates
        self.assertEqual(reservation["reserved_holdout_dates_count"], 5)
        self.assertEqual(
            reservation["reserved_holdout_dates"],
            ["2024-09-29", "2024-09-30", "2024-10-01", "2024-10-02", "2024-10-04"]
        )
        self.assertEqual(reservation["development_dates_count"], 19)
        self.assertEqual(reservation["isolation_status"], "locked_prior_to_feature_or_label_tuning")

    def test_competitor_identities_are_clean_canonical_strings(self):
        """Verify that inspect_header_sample resolves canonical strings and never stringified dicts."""
        manifest_files = list((ROOT / ".forecast" / "ac75_learning" / "sources").glob("*/manifest.json"))
        manifest = json.loads(manifest_files[-1].read_text(encoding="utf-8"))
        for s in manifest["sources"]:
            comps = s.get("sample_competitors", [])
            for c in comps:
                self.assertIsInstance(c, str)
                self.assertFalse(c.startswith("{"), f"Stringified dict found in competitors: {c}")
                self.assertFalse(c.startswith("'"), f"Stringified dict found in competitors: {c}")
                if s["boat_class"] == "AC75" and s["format"] == "jsonl" and s["stage"] != "unknown":
                    self.assertTrue(c.startswith("ac37:"), f"Expected canonical ac37:* team, got {c}")


if __name__ == "__main__":
    unittest.main()

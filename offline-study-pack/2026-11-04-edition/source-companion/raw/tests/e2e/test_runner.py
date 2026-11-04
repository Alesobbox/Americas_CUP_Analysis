"""Unified CLI Test Runner for AC40 America's Cup 2D Regatta Replay E2E Test Suite.

Supports executing individual tiers (1-4) or the complete test suite with
structured visual reporting and summary metrics.

Usage:
    python tests/e2e/test_runner.py [--tier {1,2,3,4,all}] [--verbose]
"""

from __future__ import annotations
import sys
import os
import time
import argparse
import unittest
from io import StringIO
from typing import List, Dict, Any, Tuple

# Ensure workspace root is in python path
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)


TIER_MODULES = {
    1: "tests.e2e.tier1_features_test",
    2: "tests.e2e.tier2_boundaries_test",
    3: "tests.e2e.tier3_pairwise_test",
    4: "tests.e2e.tier4_workloads_test",
}

TIER_NAMES = {
    1: "Tier 1 — Feature Coverage (13 Core Features, >=5 tests each)",
    2: "Tier 2 — Boundary & Corner Cases (5 Domains, >=5 tests each)",
    3: "Tier 3 — Cross-Feature Combinations (Pairwise Interaction)",
    4: "Tier 4 — Real-World Application Workloads (Full Dataset Integrity)",
}


def run_tier(tier_num: int, verbosity: int = 2) -> Tuple[unittest.TestResult, float]:
    """Runs tests for a specific tier and returns result and duration."""
    module_name = TIER_MODULES[tier_num]
    loader = unittest.defaultTestLoader
    suite = loader.loadTestsFromName(module_name)

    start_time = time.time()
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    elapsed = time.time() - start_time

    return result, elapsed


def print_banner(text: str):
    print("=" * 80)
    print(f" {text}")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="AC40 Regatta Replay E2E Test Runner")
    parser.add_argument(
        "--tier",
        type=str,
        default="all",
        choices=["1", "2", "3", "4", "all"],
        help="Test tier to execute (1, 2, 3, 4, or all)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose test execution output",
    )
    args = parser.parse_args()

    verbosity = 2 if args.verbose else 1

    tiers_to_run = [1, 2, 3, 4] if args.tier == "all" else [int(args.tier)]

    print_banner("AC40 AMERICA'S CUP 2D REGATTA REPLAY — E2E TEST RUNNER")
    print(f"Workspace: {WORKSPACE_ROOT}")
    print(f"Executing Tiers: {tiers_to_run}\n")

    summary_rows = []
    total_tests = 0
    total_failures = 0
    total_errors = 0
    total_skipped = 0
    total_time = 0.0

    overall_success = True

    for t in tiers_to_run:
        print_banner(f"RUNNING {TIER_NAMES[t]}")
        res, elapsed = run_tier(t, verbosity=verbosity)

        tests_run = res.testsRun
        fails = len(res.failures)
        errs = len(res.errors)
        skips = len(res.skipped)
        passed = tests_run - fails - errs - skips

        total_tests += tests_run
        total_failures += fails
        total_errors += errs
        total_skipped += skips
        total_time += elapsed

        if fails > 0 or errs > 0:
            overall_success = False

        status = "PASS" if (fails == 0 and errs == 0) else "FAIL"
        summary_rows.append({
            "tier": f"Tier {t}",
            "name": TIER_NAMES[t].split("—")[1].strip() if "—" in TIER_NAMES[t] else TIER_NAMES[t],
            "total": tests_run,
            "passed": passed,
            "failed": fails,
            "errors": errs,
            "skipped": skips,
            "time_s": f"{elapsed:.2f}s",
            "status": status,
        })
        print()

    # Final summary table
    print_banner("E2E TEST SUITE EXECUTION SUMMARY")
    header = f"{'Tier':<8} | {'Description':<42} | {'Tests':<6} | {'Pass':<5} | {'Fail':<5} | {'Time':<8} | {'Status'}"
    print(header)
    print("-" * 88)
    for row in summary_rows:
        line = (
            f"{row['tier']:<8} | "
            f"{row['name'][:42]:<42} | "
            f"{row['total']:<6} | "
            f"{row['passed']:<5} | "
            f"{row['failed']:<5} | "
            f"{row['time_s']:<8} | "
            f"{row['status']}"
        )
        print(line)
    print("-" * 88)
    print(
        f"TOTAL: {total_tests} tests executed in {total_time:.2f}s. "
        f"Passed: {total_tests - total_failures - total_errors - total_skipped}, "
        f"Failed: {total_failures}, Errors: {total_errors}, Skipped: {total_skipped}."
    )
    print(f"OVERALL STATUS: {'[PASS] 100% SUCCESS' if overall_success else '[FAIL] TEST DEFECTS DETECTED'}")
    print("=" * 80)

    sys.exit(0 if overall_success else 1)


if __name__ == "__main__":
    main()

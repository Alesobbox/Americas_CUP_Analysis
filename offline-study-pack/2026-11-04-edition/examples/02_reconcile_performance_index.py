#!/usr/bin/env python3
"""
Executable Example 02 — Reconciling the 6-Axis Peer-Normalized Performance Radar
================================================================================
Data Provenance:
  - Uses ACTUAL REPOSITORY EVIDENCE from:
      1. `evidence/naples_pr1_performance.csv`
      2. `evidence/naples_mr_final_performance.csv`
  - Demonstrates:
      a) Self-excluding peer mean on each matched leg.
      b) Why the race dimension index (mean of per-leg ratios) differs from 100 * value / peer_mean
         (ratio of cross-leg means) using `ITA G` Downwind VMG in `naples_pr1` (`109.9671` vs `108.0853`).
      c) Why Leg 2 has `peer_count = 6` while Leg 4 has `peer_count = 4` (`NZL B` and `SUI` drop out
         of Leg 4 due to `< 95%` valid source coverage).
      d) Why `naples_mr_final` (`ITA B` vs `NZL B`) restricts scope to 4 of 6 legs (`matched_legs = [1,2,3,4]`).

Requires: Python 3.10+ standard library only.
"""

from __future__ import annotations

import csv
from pathlib import Path

EVIDENCE_DIR = Path(__file__).resolve().parent.parent / "evidence"


def load_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE_DIR / name).open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def main() -> None:
    print("=" * 78)
    print("EXECUTABLE EXAMPLE 02: SELF-EXCLUDING PEER RADAR & MATCHED-LEG SCOPE")
    print("=" * 78)

    pr1_rows = load_csv("naples_pr1_performance.csv")

    # 1. Extract ITA G downwind_vmg rows (all_comparable_legs, leg 2, leg 4)
    ita_all = next(
        r for r in pr1_rows
        if r["team_code"] == "ITA G" and r["scope"] == "all_comparable_legs" and r["metric"] == "downwind_vmg"
    )
    ita_l2 = next(
        r for r in pr1_rows
        if r["team_code"] == "ITA G" and r["scope"] == "leg" and r["leg"] == "2" and r["metric"] == "downwind_vmg"
    )
    ita_l4 = next(
        r for r in pr1_rows
        if r["team_code"] == "ITA G" and r["scope"] == "leg" and r["leg"] == "4" and r["metric"] == "downwind_vmg"
    )

    val_l2, peer_l2, idx_l2 = float(ita_l2["value"]), float(ita_l2["peer_mean"]), float(ita_l2["index"])
    val_l4, peer_l4, idx_l4 = float(ita_l4["value"]), float(ita_l4["peer_mean"]), float(ita_l4["index"])
    val_all, peer_all, idx_all = float(ita_all["value"]), float(ita_all["peer_mean"]), float(ita_all["index"])

    mean_of_ratios = (idx_l2 + idx_l4) / 2.0
    ratio_of_means = 100.0 * val_all / peer_all

    print("\n[1. ACTUAL REPOSITORY EVIDENCE: naples_pr1 — ITA G Downwind VMG]")
    print(f"  Leg 2 (peer_count={ita_l2['peer_count']}): ITA G = {val_l2:.4f} kt | Peer Mean = {peer_l2:.4f} kt | Leg 2 Index = {idx_l2:.4f}")
    print(f"  Leg 4 (peer_count={ita_l4['peer_count']}): ITA G = {val_l4:.4f} kt | Peer Mean = {peer_l4:.4f} kt | Leg 4 Index = {idx_l4:.4f}")
    print(f"  Exported Dimension Value (Mean of Legs 2 & 4)     : {val_all:.4f} kt")
    print(f"  Exported Dimension Peer Mean (Mean of Peer Means) : {peer_all:.4f} kt")
    print(f"  Exported Dimension Index (Mean of Leg Ratios)     : {idx_all:.4f} (computed: {mean_of_ratios:.4f})")
    print(f"  Naive 100 * value / peer_mean (Ratio of Means)    : {ratio_of_means:.4f}")
    print(f"  Discrepancy (Mean-of-Ratios minus Ratio-of-Means) : +{idx_all - ratio_of_means:.4f} index pts")

    assert abs(idx_all - 109.9671042123199) < 1e-9
    assert abs(ratio_of_means - 108.085343) < 1e-5

    # 2. Verify USA and GBR B exclusion reasons in naples_pr1
    usa_row = next(r for r in pr1_rows if r["team_code"] == "USA" and r["scope"] == "all_comparable_legs")
    gbr_b_row = next(r for r in pr1_rows if r["team_code"] == "GBR B" and r["scope"] == "all_comparable_legs")
    print(f"\n  Excluded boats in naples_pr1:")
    print(f"    USA   quality={usa_row['quality']} | reason='{usa_row['reason']}'")
    print(f"    GBR B quality={gbr_b_row['quality']} | reason='{gbr_b_row['reason']}'")

    # 3. Verify Match Race Final (naples_mr_final) matched-leg scope
    mr_rows = load_csv("naples_mr_final_performance.csv")
    print("\n[2. ACTUAL REPOSITORY EVIDENCE: naples_mr_final (ITA B vs NZL B)]")
    for r in mr_rows:
        if r["team_code"] == "NZL B" and r["scope"] == "all_comparable_legs":
            print(
                f"  NZL B | {r['metric']:16s} | index={float(r['index']):8.2f} | "
                f"val={float(r['value']):6.2f} {r['unit']:2s} | peer={float(r['peer_mean']):6.2f} | "
                f"legs_count={r['sample_count']} | coverage_s={float(r['coverage_s']):6.2f}s"
            )
    print("\nAll assertions passed successfully.")


if __name__ == "__main__":
    main()

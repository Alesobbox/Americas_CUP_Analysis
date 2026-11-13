# AC38 Official Results vs. On-Water Telemetry Reconstruction Comparison

**Audit Status:** Complete across 18 competitive AC38 preliminary regatta races.
- **Fully Verified Official Classifications:** 2 races (with external official `https://` source).
- **Partial Unverified Races:** 16 races (Cagliari fleet races where only podium/point totals were published).

## Key Discrepancies Detected and Reconciled

1. **Cagliari Race 1 (`26_05_22_cag_ipr_race_1`):**
   - **On-Water Gate Crossings:** `['ITA G', 'FRA', 'SUI', 'NZL B', 'NZL G', 'GBR G', 'ITA B']` (ITA B crossed 7th on water).
   - **Official Published Classification:** `['ITA G', 'FRA', 'SUI', 'NZL B', 'NZL G', 'GBR G']` with `ITA B` and `GBR B` classified as DNS/DSQ (0 points).
   - **Root Cause:** Telemetry contains `PENALTY_REASON_OCS` / `PENALTY_TYPE_DISQUALIFIED` for `ITA B`. The official classification penalized `ITA B` out of the finish order.

2. **Cagliari Race 7 (`26_05_24_cag_ipr_race_7`):**
   - Telemetry and official reports record `ITA G` OCS penalty (`ocs_or_dsq_entries: ['ITA G']`).

3. **Naples Race 2 (`26_09_25_nap_ipr_race_2`):**
   - `FRA` retired (`RET` / `dnf_entries: ['FRA']`, scoring 0 points), previously misclassified as `DNS`.

## Comprehensive Race Audit Table

| Race ID | Event | Status | Verified | On-Water Finisher Count | Official Classified Count | Discrepancies / Incidents |
| :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| `26_05_22_cag_ipr_race_1` | CAG_IPR | `final` | No | 7 | Partial (6) | DNS: ITA B, GBR B; OCS/DSQ: ITA B |
| `26_05_22_cag_ipr_race_2` | CAG_IPR | `partial_unverified` | No | 6 | Partial (3) | DNS: GBR B, GBR G |
| `26_05_22_cag_ipr_race_3` | CAG_IPR | `final` | No | 8 | Partial (8) | Clean finish |
| `26_05_23_cag_ipr_race_4` | CAG_IPR | `partial_unverified` | No | 7 | Partial (4) | DNS: GBR B |
| `26_05_23_cag_ipr_race_5` | CAG_IPR | `partial_unverified` | No | 6 | Partial (3) | DNS: GBR B |
| `26_05_23_cag_ipr_race_6` | CAG_IPR | `final` | No | 7 | Partial (7) | DNS: GBR B |
| `26_05_24_cag_ipr_mr_final` | CAG_IPR | `final` | Yes | 2 | 2 | Clean finish |
| `26_05_24_cag_ipr_race_7` | CAG_IPR | `partial_unverified` | No | 7 | Partial (3) | DNS: GBR B; OCS/DSQ: ITA G |
| `26_05_24_cag_ipr_race_8` | CAG_IPR | `partial_unverified` | No | 8 | Partial (3) | Clean finish |
| `26_09_25_nap_ipr_race_1-3` | NAP_IPR | `final` | No | 9 | Partial (9) | Clean finish |
| `26_09_25_nap_ipr_race_2` | NAP_IPR | `final` | No | 8 | Partial (8) | DNF: FRA |
| `26_09_25_nap_ipr_race_3` | NAP_IPR | `final` | No | 9 | Partial (9) | Clean finish |
| `26_09_26_nap_ipr_race_4` | NAP_IPR | `final` | No | 9 | Partial (9) | Clean finish |
| `26_09_26_nap_ipr_race_5` | NAP_IPR | `final` | No | 8 | Partial (8) | DNS: FRA |
| `26_09_26_nap_ipr_race_6` | NAP_IPR | `final` | No | 9 | Partial (9) | Clean finish |
| `26_09_27_nap_ipr_race_7` | NAP_IPR | `final` | No | 9 | Partial (9) | Clean finish |
| `26_09_27_nap_ipr_race_8` | NAP_IPR | `final` | No | 9 | Partial (9) | Clean finish |
| `naples_mr_final` | NAP_IPR | `final` | Yes | 2 | 2 | Clean finish |


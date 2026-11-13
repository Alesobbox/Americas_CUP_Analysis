# AC37 Archive Data Audit & Evidence Inventory

**Generated At:** 2026-11-13T13:16:14.256156+00:00  
**Inventory ID:** `ac37-inventory-1c41eee174812054`  
**Merkle Root:** `1c41eee174812054f357a25156d69a7b4114f8470584a70720111acf4a74202d`  
**Owning Code:** `pipeline/kinematic_ml/inventory.py`  

---

## 1. Executive Summary & Archive Accounting

Total archive surveyed: **160 files** (27.78 GB).

| Archive Section | Boat Class | Wire Format | Files | Total Bytes | Status & Scope |
|---|---|---|---:|---:|---|
| `Data/*.jsonl` | `AC40` | `JSONL` | 0 | 0 | Excluded (`boat_class_ac40_replay_archive`) |
| `Data/AC37/prelims_ac40_2023/` | `AC40` | `JSONL` | 17 | 5,279,305,697 | Excluded (`boat_class_ac40_preliminary`) |
| `Data/AC37/ac75_official_practice/` | `AC75` | `JSONL` | 41 | 4,331,373,198 | Included Practice (`domain: practice`) |
| `Data/AC37/ac75_prelim_barcelona/` | `AC75` | `JSONL` | 16 | 3,245,076,449 | Included Competitive (`domain: competitive`) |
| `Data/AC37/ac75_lvc_round_robins/` | `AC75` | `JSONL` | 31 | 6,253,888,357 | Included Competitive (`domain: competitive`) |
| `Data/AC37/ac75_lvc_semifinals_raw/` | `AC75` | `.ac37 Protobuf` | 15 | 1,202,281,899 | Unsupported Wire Schema (`pending .proto descriptor`) |
| `Data/AC37/ac75_lvc_finals/` | `AC75` | `JSONL` | 12 | 2,654,846,345 | Included Competitive (`domain: competitive`) |
| **Total AC37 Archive** | **Mixed** | **Mixed** | **132** | **22,966,771,945** | **100% Accounted For** |

---

## 2. Boat Class Isolation & Coverage Exclusions

1. **AC40 Isolation:** All 17 AC40 files (0 root replay files + 17 preliminary 2023 files) are strictly excluded from AC75 model training and normalization.
2. **Unsupported Binary Protobuf Schema:** The 15 semifinal `.ac37` files (1.12 GB) require a verified official Protocol Buffer schema. In accordance with the project contract, they are classified as `unsupported_wire_schema`. This coverage limitation is propagated downstream to T04/T05 without blocking JSONL normalization.
3. **Eligible AC75 JSONL Telemetry:** 100 files totaling 16,485,184,349 bytes (~15.35 GB) across Official Practice, Preliminary, Round Robins, and Finals are fully eligible for streaming normalization.

---

## 3. Candidate Outcome Evidence Audit (`docs/ac37_results.json`)

- Total records: **82 races**
  - Barcelona Preliminary: 0 races
  - LVC Round Robins: 31 races
  - LVC Semifinals: 15 races
  - LVC Finals: 11 races
  - America's Cup Match: 9 races
- **Critical Telemetry Finding:** Physical telemetry is **missing** for all 9 America's Cup Match races (`ac37_match_r1` through `ac37_match_r9`). The Match records represent official race results only, with no corresponding high-rate sensor streams in the archive.
- **Stopped / Resail Attempt Links:** `24 09 28 BCN LV Finals Match 3 GBRvITA (stopped).jsonl` is linked to `24 09 29 BCN LV Finals Match 3 GBRvITA Re-Sail.jsonl`.

---

## 4. Chronological Evaluation Holdout Reservation

To maintain strict chronological isolation before any feature or event detector tuning:
- Total eligible competitive AC75 dates: **24 dates** (from 2024-08-22 to 2024-10-04).
- **Development Dates (19):** 2024-08-22, 2024-08-23, 2024-08-24, 2024-08-25, 2024-08-29, 2024-08-30, 2024-08-31, 2024-09-01, 2024-09-03, 2024-09-05, 2024-09-07, 2024-09-09, 2024-09-14, 2024-09-15, 2024-09-16, 2024-09-18, 2024-09-19, 2024-09-26, 2024-09-28
- **Reserved Final Holdout Block (5 dates):**
  - Dates: `2024-09-29, 2024-09-30, 2024-10-01, 2024-10-02, 2024-10-04`
  - Files (9): `24 09 29 BCN LV Finals Match 3 GBRvITA Re-Sail.jsonl, 24 09 29 BCN LV Finals Match 4 ITAvGBR.jsonl, 24 09 30 BCN LV Finals Match 5 ITAvGBR.jsonl, 24 09 30 BCN LV Finals Match 6 GBRvITA.jsonl, 24 10 01 BCN LV Finals Match 7 GBRvITA.jsonl, 24 10 01 BCN LV Finals Match 8 ITAvGBR.jsonl, 24 10 02 BCN LV Finals Match 10 GBRvITA.jsonl, 24 10 02 BCN LV Finals Match 9 ITAvGBR.jsonl, 24 10 04 BCN LV Finals Match 11 GBRvITA.jsonl`
  - Status: **Locked prior to feature extraction or model tuning**.

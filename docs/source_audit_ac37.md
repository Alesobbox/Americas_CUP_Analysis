# AC37 Barcelona & Preliminary Regattas Source Audit

**Audit Date:** 2026-11-07 15:13:23 UTC
**Archive Path:** `Data/AC37/`
**Total Volume:** 132 raw files, 21.39 GB (22,966,771,945 bytes)

## 1. Executive Summary

The `Data/AC37/` archive contains telemetry datasets from the 37th America's Cup cycle across two distinct boat classes and multiple stages:
1. **AC40 Fleet & Match Racing (2023):** 17 JSONL files from Vilanova i la Geltrú and Jeddah.
2. **AC75 Match Racing (Barcelona 2024):** 115 files covering Official Practice, Preliminary Regatta, and the entire Louis Vuitton Challenger Selection Series (Round Robins, Semifinals, and Finals).

| Section | Event / Stage | Boat Class | Wire Format | Files | Size (MB) |
| :--- | :--- | :--- | :--- | ---: | ---: |
| `prelims_ac40_2023/` | 2023 Preliminary Regattas (Vilanova & Jeddah) | `AC40` | `JSONL` | 17 | 5,034.7 MB |
| `ac75_official_practice/` | Barcelona 2024 Official Practice (OP2, OP3, OP4, OP6, OP7) | `AC75` | `JSONL` | 41 | 4,130.7 MB |
| `ac75_prelim_barcelona/` | Barcelona 2024 Preliminary Regatta (FPR1) | `AC75` | `JSONL` | 16 | 3,094.7 MB |
| `ac75_lvc_round_robins/` | Barcelona 2024 Louis Vuitton Cup Round Robins (RR1 & RR2) | `AC75` | `JSONL` | 31 | 5,964.2 MB |
| `ac75_lvc_semifinals_raw/` | Barcelona 2024 Louis Vuitton Cup Semifinals | `AC75` | `.ac37 Protobuf` | 15 | 1,146.6 MB |
| `ac75_lvc_finals/` | Barcelona 2024 Louis Vuitton Cup Finals | `AC75` | `JSONL` | 12 | 2,531.9 MB |
| **Total** | **All AC37 Stages** | Mixed | Mixed | **132** | **21,902.8 MB** |

## 2. Telemetry Wire Formats

- **JSON Lines (`.jsonl`):** 117 files. Each line represents a single structured JSON packet with `correlation_id`, `sequence_id`, and payload (`session`, `telemetry`, `competitor`, or `target`). High-rate GNSS and heading are at 20 Hz, SOG/COG at ~4.37 Hz, and wind at 1 Hz.
- **Length-Prefixed Protobuf (`.ac37`):** 15 files in `ac75_lvc_semifinals_raw/`. Each frame begins with a 4-byte big-endian length prefix followed by a serialized Protocol Buffer packet matching the official America's Cup message schema (Tag 5 = Session, Tag 4 = Telemetry).

## 3. Inventory by Stage

### `prelims_ac40_2023/` — 2023 Preliminary Regattas (Vilanova & Jeddah)
- **Class:** `AC40` | **Format:** `JSONL` | **Count:** 17 files | **Size:** 4.92 GB

| File Name | Size (MB) | Format | Boat Class |
| :--- | ---: | :--- | :--- |
| `2023-09-16 VNR 1.jsonl` | 470.74 MB | `JSONL` | `AC40` |
| `2023-09-16 VNR 2.jsonl` | 605.56 MB | `JSONL` | `AC40` |
| `2023-09-17 VNR 3.jsonl` | 441.51 MB | `JSONL` | `AC40` |
| `2023-09-17 VNR 4.jsonl` | 415.92 MB | `JSONL` | `AC40` |
| `2023-09-17 VNR 5.jsonl` | 569.98 MB | `JSONL` | `AC40` |
| `2023-09-17 VNR 6 USA NZL.jsonl` | 224.60 MB | `JSONL` | `AC40` |
| `2023-11-27 P1.jsonl` | 443.67 MB | `JSONL` | `AC40` |
| `2023-11-27 P2.jsonl` | 322.79 MB | `JSONL` | `AC40` |
| `2023-11-27 P3.jsonl` | 326.21 MB | `JSONL` | `AC40` |
| `2023-11-27 P4.jsonl` | 215.53 MB | `JSONL` | `AC40` |
| `2023-11-28 P5.jsonl` | 162.32 MB | `JSONL` | `AC40` |
| `2023-11-29 P6.jsonl` | 222.58 MB | `JSONL` | `AC40` |
| `2023-11-29 P7.jsonl` | 228.90 MB | `JSONL` | `AC40` |
| `2023-11-29 P8.jsonl` | 237.17 MB | `JSONL` | `AC40` |
| `2023-11-29 PS1 ITA USA.jsonl` | 52.96 MB | `JSONL` | `AC40` |
| *... and 2 additional files* | | | |

### `ac75_official_practice/` — Barcelona 2024 Official Practice (OP2, OP3, OP4, OP6, OP7)
- **Class:** `AC75` | **Format:** `JSONL` | **Count:** 41 files | **Size:** 4.03 GB

| File Name | Size (MB) | Format | Boat Class |
| :--- | ---: | :--- | :--- |
| `24 08 02 BCN OP2 S1P1 2.jsonl` | 64.40 MB | `JSONL` | `AC75` |
| `24 08 02 BCN OP2 S1P1.jsonl` | 75.31 MB | `JSONL` | `AC75` |
| `24 08 02 BCN OP2 S1P2.jsonl` | 74.63 MB | `JSONL` | `AC75` |
| `24 08 02 BCN OP2 S2P1 2.jsonl` | 74.96 MB | `JSONL` | `AC75` |
| `24 08 02 BCN OP2 S2P1.jsonl` | 73.90 MB | `JSONL` | `AC75` |
| `24 08 02 BCN OP2 S2P2.jsonl` | 70.91 MB | `JSONL` | `AC75` |
| `24 08 02 BCN OP2 S3P1 2.jsonl` | 75.18 MB | `JSONL` | `AC75` |
| `24 08 02 BCN OP2 S3P1.jsonl` | 75.10 MB | `JSONL` | `AC75` |
| `24 08 02 BCN OP2 S3P2.jsonl` | 67.96 MB | `JSONL` | `AC75` |
| `24 08 02 BCN OP2 S4P1.jsonl` | 65.75 MB | `JSONL` | `AC75` |
| `24 08 02 BCN OP2 S4P2.jsonl` | 59.14 MB | `JSONL` | `AC75` |
| `24 08 02 BCN OP2 S5P1.jsonl` | 65.44 MB | `JSONL` | `AC75` |
| `24 08 02 BCN OP2 S5P2.jsonl` | 60.08 MB | `JSONL` | `AC75` |
| `24 08 02 BCN OP2 S6P1.jsonl` | 75.08 MB | `JSONL` | `AC75` |
| `24 08 02 BCN OP2 S6P2.jsonl` | 75.12 MB | `JSONL` | `AC75` |
| *... and 26 additional files* | | | |

### `ac75_prelim_barcelona/` — Barcelona 2024 Preliminary Regatta (FPR1)
- **Class:** `AC75` | **Format:** `JSONL` | **Count:** 16 files | **Size:** 3.02 GB

| File Name | Size (MB) | Format | Boat Class |
| :--- | ---: | :--- | :--- |
| `24 08 22 FPR1 Match 1 SUIvFRA.jsonl` | 214.59 MB | `JSONL` | `AC75` |
| `24 08 22 FPR1 Match 2 NZLvITA.jsonl` | 139.04 MB | `JSONL` | `AC75` |
| `24 08 22 FPR1 Match 3 USAvGBR.jsonl` | 216.50 MB | `JSONL` | `AC75` |
| `24 08 22 FPR1 Match 4 ITAvFRA.jsonl` | 226.25 MB | `JSONL` | `AC75` |
| `24 08 23 BCN FPR Match 5 SUIvUSA.jsonl` | 216.89 MB | `JSONL` | `AC75` |
| `24 08 23 BCN FPR Match 6 GBRvNZL.jsonl` | 222.15 MB | `JSONL` | `AC75` |
| `24 08 23 BCN FPR Match 7 USAvITA.jsonl` | 223.38 MB | `JSONL` | `AC75` |
| `24 08 23 BCN FPR Match 8 FRAvNZL.jsonl` | 38.69 MB | `JSONL` | `AC75` |
| `24 08 24 BCN FPR Match 10 USAvFRA.jsonl` | 34.57 MB | `JSONL` | `AC75` |
| `24 08 24 BCN FPR Match 11 ITAvGBR.jsonl` | 225.47 MB | `JSONL` | `AC75` |
| `24 08 24 BCN FPR Match 12 NZLvSUI.jsonl` | 217.41 MB | `JSONL` | `AC75` |
| `24 08 24 BCN FPR Match 9 GBRvSUI.jsonl` | 217.00 MB | `JSONL` | `AC75` |
| `24 08 25 BCN FPR Final NZLvITA.jsonl` | 221.54 MB | `JSONL` | `AC75` |
| `24 08 25 BCN FPR Match 13 NZLvUSA.jsonl` | 215.35 MB | `JSONL` | `AC75` |
| `24 08 25 BCN FPR Match 14 ITAvSUI.jsonl` | 246.64 MB | `JSONL` | `AC75` |
| *... and 1 additional files* | | | |

### `ac75_lvc_round_robins/` — Barcelona 2024 Louis Vuitton Cup Round Robins (RR1 & RR2)
- **Class:** `AC75` | **Format:** `JSONL` | **Count:** 31 files | **Size:** 5.82 GB

| File Name | Size (MB) | Format | Boat Class |
| :--- | ---: | :--- | :--- |
| `24 08 29 BCN LV RR1 Match 1 FRAvSUI.jsonl` | 236.40 MB | `JSONL` | `AC75` |
| `24 08 29 BCN LV RR1 Match 2 ITAvNZL.jsonl` | 204.18 MB | `JSONL` | `AC75` |
| `24 08 29 BCN LV RR1 Match 3 GBRvUSA.jsonl` | 227.28 MB | `JSONL` | `AC75` |
| `24 08 29 BCN LV RR1 Match 4 FRAvITA.jsonl` | 225.21 MB | `JSONL` | `AC75` |
| `24 08 30 BCN LV RR1 Match 5 USAvSUI.jsonl` | 314.40 MB | `JSONL` | `AC75` |
| `24 08 30 BCN LV RR1 Match 6 NZLvGBR.jsonl` | 32.05 MB | `JSONL` | `AC75` |
| `24 08 31 BCN LV RR1 Match 10 FRAvUSA.jsonl` | 259.24 MB | `JSONL` | `AC75` |
| `24 08 31 BCN LV RR1 Match 11 GBRvITA.jsonl` | 213.12 MB | `JSONL` | `AC75` |
| `24 08 31 BCN LV RR1 Match 7 ITAvUSA.jsonl` | 217.28 MB | `JSONL` | `AC75` |
| `24 08 31 BCN LV RR1 Match 8 NZLvFRA.jsonl` | 48.57 MB | `JSONL` | `AC75` |
| `24 08 31 BCN LV RR1 Match 9 SUIvGBR.jsonl` | 249.53 MB | `JSONL` | `AC75` |
| `24 09 01 BCN LV RR1 Match 12 SUIvNZL.jsonl` | 71.00 MB | `JSONL` | `AC75` |
| `24 09 01 BCN LV RR1 Match 13 GBRvFRA.jsonl` | 218.66 MB | `JSONL` | `AC75` |
| `24 09 01 BCN LV RR1 Match 14 SUIvITA.jsonl` | 209.50 MB | `JSONL` | `AC75` |
| `24 09 01 BCN LV RR1 Match 15 USAvNZL.jsonl` | 224.34 MB | `JSONL` | `AC75` |
| *... and 16 additional files* | | | |

### `ac75_lvc_semifinals_raw/` — Barcelona 2024 Louis Vuitton Cup Semifinals
- **Class:** `AC75` | **Format:** `.ac37 Protobuf` | **Count:** 15 files | **Size:** 1.12 GB

| File Name | Size (MB) | Format | Boat Class |
| :--- | ---: | :--- | :--- |
| `24 09 14 BCN LVS Match 1 ITAvUSA.ac37` | 68.54 MB | `.ac37 Protobuf` | `AC75` |
| `24 09 14 BCN LVS Match 1 SUIvGBR.ac37` | 75.67 MB | `.ac37 Protobuf` | `AC75` |
| `24 09 14 BCN LVS Match 2 GBRvSUI.ac37` | 67.74 MB | `.ac37 Protobuf` | `AC75` |
| `24 09 14 BCN LVS Match 2 USAvITA.ac37` | 73.88 MB | `.ac37 Protobuf` | `AC75` |
| `24 09 15 BCN LVS Match 3 GBRvSUI.ac37` | 74.84 MB | `.ac37 Protobuf` | `AC75` |
| `24 09 15 BCN LVS Match 3 USAvITA.ac37` | 70.10 MB | `.ac37 Protobuf` | `AC75` |
| `24 09 15 BCN LVS Match 4 ITAvUSA.ac37` | 70.10 MB | `.ac37 Protobuf` | `AC75` |
| `24 09 15 BCN LVS Match 4 SUIvGBR.ac37` | 69.08 MB | `.ac37 Protobuf` | `AC75` |
| `24 09 16 BCN LVS Match 5 SUIvGBR.ac37` | 126.67 MB | `.ac37 Protobuf` | `AC75` |
| `24 09 16 BCN LVS Match 5 USAvITA.ac37` | 83.54 MB | `.ac37 Protobuf` | `AC75` |
| `24 09 18 BCN LVS Match 6 GBRvSUI.ac37` | 72.35 MB | `.ac37 Protobuf` | `AC75` |
| `24 09 18 BCN LVS Match 6 ITAvUSA.ac37` | 80.26 MB | `.ac37 Protobuf` | `AC75` |
| `24 09 18 BCN LVS Match 7 GBRvSUI.ac37` | 74.49 MB | `.ac37 Protobuf` | `AC75` |
| `24 09 18 BCN LVS Match 7 ITAvUSA.ac37` | 67.19 MB | `.ac37 Protobuf` | `AC75` |
| `24 09 19 BCN LVS Match 8 USAvITA.ac37` | 72.16 MB | `.ac37 Protobuf` | `AC75` |

### `ac75_lvc_finals/` — Barcelona 2024 Louis Vuitton Cup Finals
- **Class:** `AC75` | **Format:** `JSONL` | **Count:** 12 files | **Size:** 2.47 GB

| File Name | Size (MB) | Format | Boat Class |
| :--- | ---: | :--- | :--- |
| `24 09 26 BCN LV Finals Match 1 ITAvGBR.jsonl` | 224.89 MB | `JSONL` | `AC75` |
| `24 09 26 BCN LV Finals Match 2 GBRvITA.jsonl` | 218.96 MB | `JSONL` | `AC75` |
| `24 09 28 BCN LV Finals Match 3 GBRvITA (stopped).jsonl` | 345.99 MB | `JSONL` | `AC75` |
| `24 09 29 BCN LV Finals Match 3 GBRvITA Re-Sail.jsonl` | 29.03 MB | `JSONL` | `AC75` |
| `24 09 29 BCN LV Finals Match 4 ITAvGBR.jsonl` | 224.16 MB | `JSONL` | `AC75` |
| `24 09 30 BCN LV Finals Match 5 ITAvGBR.jsonl` | 224.34 MB | `JSONL` | `AC75` |
| `24 09 30 BCN LV Finals Match 6 GBRvITA.jsonl` | 224.54 MB | `JSONL` | `AC75` |
| `24 10 01 BCN LV Finals Match 7 GBRvITA.jsonl` | 146.53 MB | `JSONL` | `AC75` |
| `24 10 01 BCN LV Finals Match 8 ITAvGBR.jsonl` | 223.55 MB | `JSONL` | `AC75` |
| `24 10 02 BCN LV Finals Match 10 GBRvITA.jsonl` | 222.71 MB | `JSONL` | `AC75` |
| `24 10 02 BCN LV Finals Match 9 ITAvGBR.jsonl` | 228.61 MB | `JSONL` | `AC75` |
| `24 10 04 BCN LV Finals Match 11 GBRvITA.jsonl` | 218.53 MB | `JSONL` | `AC75` |

## 4. Contract with Downstream Pipeline

1. **Boat Class Isolation:** AC75 telemetry sessions must be ingested with `boat_class: 'AC75'` under `group: 'barcelona_2024'`, ensuring zero mutation or cross-contamination of the 28 AC40 analysis artifacts (`public/data/analysis/*.json`).
2. **Physical Kinematics:** Unlike AC40 one-design fleet races, AC75 match racing features bespoke team hull/foil geometries, cyclic battery power systems, and distinct polar speed polars.
3. **Protobuf Conversion:** The 15 semifinal `.ac37` files will be decoded via length-prefixed Protobuf readers into matching standard `.jsonl` before ingest.

## 5. Curated AC37 Datasets & Within-Cycle Transfer Study

- **AC40 2023 Preliminary Regattas:** `docs/ac37_ac40_2023_results.json` contains 15 official races from Vilanova and Jeddah with all 6 teams (`ETNZ`, `INEOS`, `LUNA_ROSSA`, `AMERICAN_MAGIC`, `ALINGHI`, `ORIENT_EXPRESS`).
- **AC75 2024 Match Racing Dataset:** `docs/ac37_results.json` contains 81 match races across Barcelona Preliminary (16 matches), LVC Round Robins (30 matches), Semifinals (15 matches), Finals (11 matches), and Match (9 matches) across all 6 teams.
- **Calibrated Within-Cycle Transfer:** Evaluated via `pipeline.prediction.transfer.run_transfer_study(ac40_source='ac37_2023')` and stored in `.forecast/transfer/ac37_transfer.json`. Verified with `n_shared_teams = 6`, including `ORIENT_EXPRESS`.


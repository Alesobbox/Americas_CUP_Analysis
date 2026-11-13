# AC38 Forecast Report (Experimental · from AC40 Evidence)

- **Artifact SHA-256:** `b80bbe9c629ea50f9da793fe5ef85bd143dc89c6307adddc526613287abdb078`
- **Schema / Status:** `ac38-forecast-1` / `experimental_rule_bounds` (`experimental=True`)
- **Issuance Cutoff (UTC):** `2026-10-01T00:00:00Z`
- **Conditioning:** Conditional on completed races without reliability/timing stoppages; reliability stoppages appear in separate sensitivity.
- **Scale & Priors:** κ = 1.0, AC40 SD = 1.2 (sensitivity 0.8, 1.8), β ~ N(0, 1), τ ~ HalfNormal(1)
- **Selected Transfer Model:** `results_only` (telemetry retained: `False`)
- **Monte Carlo Budget:** 200,000 tournament trials (seed `2027`); worst-case 95% MC half-width ≤ ±0.22 pp

## 1. Data Coverage & Mapping Assumptions
- AC38 races included: 18 (anchored full results: 2, reconstructed fleet orders: 16, excluded observations: 10)
- Default mapping policy: `confirmed_crew_then_principal_ac40_else_prior`
- AC37 within-cycle AC40-to-AC75 transfer distribution is applied unchanged in the baseline forecast.
- Country codes do not imply continuity between historical AC37 and current AC38 teams.
- Team strengths map confirmed crews first, then documented principal AC40 entry, else a population prior (Australia).
- No race-count crew mixture is used in the default mapping; equal senior/youth-women weighting is a sensitivity only.
- Wind-response effects remain off in the default forecast.
- Only 2 of 18 AC38 preliminary races have full captured independent match results; 16 fleet races rely on telemetry reconstruction with partial anchors.

## 2. Forecast Outcomes (Single Unified Model)
| Team | Exp Fleet Pos | RR Top 3 | Semifinal | Challenger Win | Cup Bounds [Lower, Upper] | MC SE (L/U) |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| Emirates Team New Zealand (`ETNZ`) | 3.81 | 0.00% | 0.00% | 0.00% | [11.33%, 33.79%] | ±0.07 / ±0.11 pp |
| GB1 (`GB1`) | 4.35 | 44.03% | 65.18% | 8.82% | [5.26%, 27.71%] | ±0.05 / ±0.10 pp |
| Luna Rossa (`LUNA_ROSSA`) | 2.64 | 79.24% | 88.08% | 43.69% | [30.34%, 52.80%] | ±0.10 / ±0.11 pp |
| Tudor Team Alinghi (`ALINGHI`) | 4.91 | 30.06% | 48.23% | 6.43% | [3.84%, 26.30%] | ±0.04 / ±0.10 pp |
| La Roche-Posay Racing Team (`LA_ROCHE_POSAY`) | 3.58 | 62.67% | 79.36% | 15.52% | [9.78%, 32.24%] | ±0.07 / ±0.10 pp |
| ARC Team USA (`ARC_USA`) | 4.59 | 36.00% | 56.70% | 7.69% | [4.57%, 27.03%] | ±0.05 / ±0.10 pp |
| Team Australia (`AUSTRALIA`) | 4.11 | 48.00% | 62.46% | 17.86% | [12.43%, 34.89%] | ±0.07 / ±0.11 pp |

## 3. Posterior Transfer Uncertainty & Nested Intervals
- β quantiles (5th / 50th / 95th): `-0.250` / `0.779` / `1.748`
- τ quantiles (5th / 50th / 95th): `0.190` / `0.741` / `1.558`
- ρ implied correlation (5th / 50th / 95th): `-0.271` / `0.787` / `0.990`
- Nested outer-inner posterior interval stabilization: `Reached nested simulation computation cap (240000 trials); final endpoint shift was 8.07 pp (> 0.50 pp).`

## 4. Unresolved Governing Rules
- Resolved trials: 155,082 / 200,000; Unresolved trials: 44,918 (22.46%)
- Six-challenger qualification/seeding tie procedure requires authoritative clarification (RRSAC 102.1 only covers 3- and 4-Challenger ties).
- Timing-dependent shared/zero-score results require the applicable race state and instructions.
- Incomplete-series, withdrawal and continuation instructions must be pinned before publication.
- Protocol Amendment 08 notes Article 13.2 rule number reference remains under review.

## 5. Structural Sensitivities
| Scenario | Residual | Zero β | Failure q | ETNZ Bounds | LUNA_ROSSA Bounds |
| --- | ---: | --- | ---: | --- | --- |
| Residual scale 0.5x | 0.5x | False | 0.00% | [10.83%, 38.55%] | [33.86%, 61.58%] |
| Baseline transfer (residual scale 1.0x) | 1.0x | False | 0.00% | [11.25%, 34.04%] | [30.13%, 52.92%] |
| Residual scale 2.0x | 2.0x | False | 0.00% | [12.58%, 28.14%] | [25.57%, 41.13%] |
| Zero cross-class transfer (beta = 0) | 1.0x | True | 0.00% | [15.57%, 46.72%] | [8.99%, 40.13%] |
| Equal senior + youth/women crew weighting | 1.0x | False | 0.00% | [11.36%, 34.90%] | [20.91%, 44.45%] |
| Independently anchored AC38 outcomes only | 1.0x | False | 0.00% | [7.50%, 27.30%] | [17.32%, 37.12%] |
| Reliability stoppage sensitivity (q = 2% per boat-race) | 1.0x | False | 2.00% | [0.04%, 99.78%] | [0.07%, 99.81%] |

## 6. Historical Backtest Evaluation
- Selection rule: `1-SE grouped improvement on both AC40 chronological and AC75 LOTO log loss` -> selected `results_only` (telemetry retained: `False`)
- **Accuracy claim:** No overall AC75 accuracy improvement over carryover/no-transfer is claimed: transfer improved AC40 chronological log loss over uniform (1.590 vs 1.788) and outperformed AC75 no-transfer chronologically (0.653 vs 0.693), but did not beat AC75 carryover (0.653 vs 0.647) or improve AC37 LOTO log loss by >1 SE (0.662 ± 0.029 vs 0.667); telemetry was not retained under the 1-SE rule.

| Benchmark | Model | N (Groups) | Grouped Log Loss ± SE | Brier | Cal Slope / Int | 50% / 90% Cov |
| --- | --- | ---: | --- | ---: | --- | --- |
| AC40 chronological | `uniform` | 27 (9) | 1.788 ± 0.085 | 0.812 | 1.00 / 0.00 | 68.2% / 100.0% |
| AC40 chronological | `results_only` | 27 (9) | 1.590 ± 0.161 | 0.730 | 1.14 / 0.21 | 71.2% / 96.6% |
| AC40 chronological | `results_plus_telemetry` | 27 (9) | 1.639 ± 0.156 | 0.752 | 1.03 / 0.04 | 69.6% / 98.5% |
| AC75 chronological | `no_transfer` | 82 (29) | 0.693 ± 0.000 | 0.250 | 1.00 / 0.15 | — |
| AC75 chronological | `naive_ac40_strength` | 82 (29) | 0.685 ± 0.067 | 0.242 | 0.58 / 0.02 | — |
| AC75 chronological | `ac75_carryover` | 82 (29) | 0.647 ± 0.052 | 0.221 | 0.94 / 0.32 | — |
| AC75 chronological | `transfer_results_only` | 82 (29) | 0.653 ± 0.052 | 0.224 | 0.88 / 0.25 | 62.1% / 96.5% |
| AC75 LOTO (AC37) | `no_transfer` | 164 (6) | 0.667 ± 0.020 | 0.236 | 0.98 / 0.15 | — |
| AC75 LOTO (AC37) | `naive_ac40_strength` | 164 (6) | 0.649 ± 0.047 | 0.242 | 0.58 / -0.00 | — |
| AC75 LOTO (AC37) | `results_only_transfer` | 164 (6) | 0.662 ± 0.029 | 0.242 | 0.69 / 0.18 | 33.3% / 100.0% |
| AC75 LOTO (AC37) | `results_plus_telemetry_transfer` | 164 (6) | 0.662 ± 0.030 | 0.243 | 0.68 / 0.18 | 33.3% / 100.0% |

## 7. Source Inventory Summary
| Domain | Telemetry Windows | Completed Races | Stopped/Abandoned/Resails | Boat-Races | Racing Days |
| --- | ---: | ---: | --- | ---: | ---: |
| AC37 AC40 Prelims | 17 | 14 | abandoned=1 | 80 | 5 |
| AC37 AC75 LVC & Match | 130 | 82 | stopped=1, resails=1 | 164 | 29 |
| AC38 AC40 Prelims | 28 | 18 | practice_windows=10 | 125 | 6 |

## 8. Comparison vs Previous Cup Publication
- Previous publication: `cup/5cae98e1c3856cd6885831d0b876d6ae048d0d005d5fc373ab7d0651a8f9a6b5.json` (`cup-ac38-conditional-2`, model `dd9a31a7834ae1e9d8c0c082b437e0c6542302bed171b0d8e5e45f9c6b3940da`)
- Previous cup_path publication used an uncalibrated 9-scenario AC40-to-AC75 envelope on kappa=1.8; ac38-forecast-1 refits a joint kappa=1.0 AC37 PL/BT transfer posterior, maps AC38 AC40 entries as of issuance_cutoff_utc, and propagates full posterior + unresolved-rule uncertainty.

| Team | Previous Cup Bounds | AC38 Unified Bounds | Midpoint Delta |
| --- | --- | --- | ---: |
| Emirates Team New Zealand (`ETNZ`) | [16.86%, 51.32%] | [11.33%, 33.79%] | -11.53 pp |
| GB1 (`GB1`) | [3.34%, 37.80%] | [5.26%, 27.71%] | -4.08 pp |
| Luna Rossa (`LUNA_ROSSA`) | [16.60%, 51.06%] | [30.34%, 52.80%] | +7.74 pp |
| Tudor Team Alinghi (`ALINGHI`) | [1.34%, 35.80%] | [3.84%, 26.30%] | -3.50 pp |
| La Roche-Posay Racing Team (`LA_ROCHE_POSAY`) | [8.52%, 42.98%] | [9.78%, 32.24%] | -4.74 pp |
| ARC Team USA (`ARC_USA`) | [10.80%, 45.26%] | [4.57%, 27.03%] | -12.23 pp |
| Team Australia (`AUSTRALIA`) | [8.08%, 42.54%] | [12.43%, 34.89%] | -1.65 pp |

## 9. Verification & Completion Tracking
| Dimension | Status | Evidence / Rationale |
| --- | --- | --- |
| `implementation_complete` | `True` | Joint transfer fit, cutoff AC40 fit, unified simulation, contracts, and UI wired. |
| `engineering_verified` | `True` | Grid converged=`True`, refinement ok=`True`, nested <=0.5pp=`False`. |
| `evidence_sufficient` | `False` | Observed AC40 teams=`False`, reconstructed AC38 races=`16`, resolved rules=`False` (22.46% unresolved). |
| `accuracy_improvement_demonstrated` | `False` | Telemetry retained=`False`; No overall AC75 accuracy improvement over carryover/no-transfer is claimed: transfer improved AC40 chronological log loss over uniform (1.590 vs 1.788) and outperformed AC75 no-transfer chronologically (0.653 vs 0.693), but did not beat AC75 carryover (0.653 vs 0.647) or improve AC37 LOTO log loss by >1 SE (0.662 ± 0.029 vs 0.667); telemetry was not retained under the 1-SE rule. |

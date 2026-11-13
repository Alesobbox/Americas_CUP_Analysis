# Kinematic Simulator Out-of-Sample Evaluation Report

**Evaluation Date:** 2026-11-09T12:57:23.809970+00:00  
**Status Declared:** `EXPERIMENTAL`  
**Policy:** Status is strictly performance-gated by empirical out-of-sample metrics against pre-declared thresholds.

---

## 1. Evaluation Methodology

- **Outer Loop:** Day-ahead chronological out-of-sample evaluation across development days `2026-05-23, 2026-05-24, 2026-09-25`.
- **Target Ordering:** Canonical alphabetical ordering $\text{team\_a} = \min(u, v)$, $\text{team\_b} = \max(u, v)$ to strictly prevent winner-first hindsight bias.
- **Empirical Shrinkage:** Inner cross-validation selects $\tau_{\text{team}} \in [0.15, 0.30, 0.50, 0.80]$.
- **Baseline Comparison:** Day-ahead `StrengthModel` Bradley-Terry predictions fit strictly on prior race data.

---

## 2. Quantitative Results

| Metric | Kinematic ML | Baseline Model | Threshold | Pass Gate |
|---|---|---|---|---|
| **Pairwise Comparisons (N)** | 72 | 72 | — | Yes |
| **Positive Outcome Rate ($\bar{y}$)** | 0.3611 | — | $0.20 \le \bar{y} \le 0.80$ | Yes |
| **Brier Score** | **0.2497** | 0.2152 | $\le 0.18$ | No (Experimental) |
| **Log Loss** | **0.6926** | 0.6143 | $\le 0.55$ | No (Experimental) |
| **Calibration Slope** | **0.398** | — | $[0.85, 1.15]$ | No (Experimental) |

---

## 3. Match Race Holdout Results

Evaluated on true 2-boat match race finals:
- Total match races: 1
- Mean Brier score: 0.25

---

## 4. Status Determination

Current empirical performance does not satisfy all three strict gates.
The kinematic simulator is therefore designated as **`experimental`** in the candidate catalog and UI.

# AC40 Kinematic Feature & Manoeuvre Detection Audit

**Audit Status:** Complete across 60 stratified 60-second race-boat telemetry windows.

## 1. Multi-Stream Window Support & Dropouts
- **Windows Evaluated:** 60
- **Valid Windows:** 8 (13.3%)
- **Dropout Exceeded Count (>1200ms):** 0
- **Max Gap Median:** 250.0 ms
- **Max Gap 95th Percentile:** 250.0 ms

## 2. Empirical Manoeuvre Detection Accuracy
Evaluated via greedy bipartite matching (tolerance $\pm 4000$ ms) against the repository full-physics multi-gate reference detector `ManoeuvreDetector`:
- **Total Detected Maneuvers:** 57 (25 tacks, 23 gybes, 9 other rotations)
- **True Positives (TP):** 5
- **False Positives (FP):** 43
- **False Negatives (FN):** 13
- **Empirical Precision:** `0.1042`
- **Empirical Recall:** `0.2778`

## 3. Speed Breakdown Across AC40 Syndicates
- **Overall Mean SOG:** 27.34 kt
- **Overall SOG SD:** 4.87 kt
- **Between-Team SD:** 0.45 kt
- **Pooled Within-Team SD:** 4.87 kt

| Team | Samples | Mean SOG (kt) | SD (kt) |
| :--- | :---: | :---: | :---: |
| FRA | 53 | 27.34 | 4.87 |


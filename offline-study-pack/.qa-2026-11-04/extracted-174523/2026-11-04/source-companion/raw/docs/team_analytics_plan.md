# Team analytics improvement plan

Requested 1 November 2026. Preserve the dashboard design, replay compatibility, and existing uncommitted work.

## Evidence and contract

The source audit and compact archive snapshot establish 28 AC40 sessions and 224 replayed boat-races. Historical results are reconstructed; there are no independently verified official finishing orders or measured polar/target-TWA channels. Existing historical coverage, completed-leg status, and source conflicts determine eligibility. Python owns all metric formulas and availability; the browser only selects and displays exported observations.

## Work and acceptance

1. **Study source and contracts.** Review PROJECT, source audit, historical analysis, dashboard contract, and actual compact coverage. Define additive versioned analytics without altering historical schema 2.0 or replay arrays.
2. **Tactical insights.** Export past-only trailing official-wind observations, coverage, and conditional five-minute trend extrapolations when sufficiently supported by a stable recent window. Never describe extrapolation as a calibrated forecast or a certain arrival time. Missing, stale, sparse, or unstable inputs explain their unavailable state. Browser selection cannot pass the playhead and expires stale observations.
3. **Boat performance.** Export six dimensions: upwind/downwind leg-directed VMG, upwind/downwind speed, and detector-conditioned tack/gybe speed retention. Use matching completed legs and the equal-weight mean of eligible other boats. Index 100 represents peers; preserve absolute values, source, coverage, denominators, counts, and unavailable reasons. Draw a circular radar within the existing Analysis styling with an accessible evidence table.
4. **Team debrief.** Rank observed same-leg elapsed-time deficits and high-loss manoeuvres, retaining reconstructed/derived labels and replay timestamps. These are review priorities rather than causal loss attribution. Make all outputs visible in Analysis, Replay/Compare where causal, and existing downloadable analysis files.
5. **Artifacts and verification.** Refresh all 28 details, historical index and artifact byte inventory deterministically. Verify formulas, no future input use, circular angles, gaps, stale data, peer exclusion and matching legs. Run focused tests, run.ps1 verify, production browser checks across fleet/match and desktop/mobile, and artifact inventory/hash checks. Complete every stage before delivery.

Implementation evidence and final check results are recorded in docs/team_analytics.md. A prior dashboard verification document describes its original dated run and is not evidence for this change.

## Completion

All five stages completed on 1 November 2026. The final repository gate passed 776 deterministic tests, production build, and Forecast/environment/analytics checks. All 16 production-browser scenarios and the final feature visual checks passed. Source evidence, coverage counts, reproducibility and preserved-data hashes are recorded in [team_analytics.md](team_analytics.md). The archive supports observed wind diagnostics; no recorded window qualifies for the conditional five-minute projection.

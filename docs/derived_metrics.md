# Tactical metrics shown in the browser

The versioned post-race contract is in [historical_analysis.md](historical_analysis.md). This page describes legacy replay values; [source_audit.md](source_audit.md) covers their evidence limits.

## Fleet ranking and gaps

Boats without a start crossing are unranked. Active boats are ordered by cumulative monotonic `progress_m`. Finished boats are ordered by reconstructed finish time. OCS/RET stays outside the active ranks. DNF is reported at the replay end because no earlier DNF transition is represented in the compact export.

The metre gap is `leader progress − boat progress`, clamped at zero. While racing, the time gap is calculated as metre gap divided by the leader's current speed in metres per second. Zero leader speed yields an unavailable time gap. The UI displays this as an estimate. When both boats have finished, their time gap is the difference between reconstructed finish times and is prefixed with `+`.

## Vessel and pairwise panels

SOG is speed over ground. VMG, TWA, heading, COG, current leg, and cumulative progress come from the synchronized export.

In head-to-head view, physical separation is the Euclidean distance between boats. Longitudinal offset projects B−A onto A's current leg direction; lateral offset projects onto the perpendicular course axis. Race progress delta compares cumulative progress, so it need not equal physical separation. Closure uses the relative SOG/COG velocity projected onto the separation vector; a positive value means the boats are approaching.

## Start analysis

Start analysis displays projected bow distance and along-line position at the gun, measured SOG, signed closing speed, reconstructed crossing order, and source conflicts. Python owns these historical formulas and availability rules.

## Summary and source distinction

Final classification and elapsed time are reconstructed from source leg timing records and geometric fallbacks; the source does not independently verify most official results. Distance sailed sums projected GNSS point-to-point movement between each boat's start and finish, or the end of available telemetry for non-finishers. Average SOG and fixed-axis VMG use the same interval in the legacy replay. Full-race fixed-axis VMG is not a useful overall performance score. The new analysis uses leg-directed and wind-relative VMG and checks raw timestamp coverage. `provenance` in the replay JSON lists the measured input streams and derived output fields.

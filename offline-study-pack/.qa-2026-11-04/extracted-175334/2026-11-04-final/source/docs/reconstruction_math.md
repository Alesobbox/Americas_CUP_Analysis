# Reconstruction math

## Coordinates and synchronization

The local projection uses the course-centre WGS84 origin. With latitude and longitude in degrees:

```text
x = (longitude − longitude₀) · k_lon
y = (latitude  − latitude₀)  · k_lat
```

The coefficients use WGS84 local curvature at the origin. The pipeline checks projected distances between both gate-mark pairs against a geodesic Haversine reference before processing telemetry. Longitude and latitude are preserved only in the raw source; browser geometry is in metres.

Each measured stream is independently synchronized to a 100 ms grid. Scalar values and projected positions use linear interpolation. Compass angles use the shortest circular arc, avoiding a false rotation from 359° through 180° to 1°. Raw SOG and wind speed are multiplied by `3600 / 1852` to produce knots.

## Start and gates

The antenna is behind the AC40 bow. The reconstruction projects the bow 12.963 m along measured heading before segment intersection. Adjacent bow samples form the moving segment; gate marks form a line segment. A crossing is accepted only when the segments intersect in the required course direction. The intersection fraction interpolates the crossing timestamp within the 100 ms interval. The mark chosen is determined by the intersection fraction along the gate line.

The start delta is the reconstructed crossing time minus the gun timestamp. Official `start_state` and penalty events validate OCS. GBR B remains OCS/RET in the exported classification. Where official leg messages are missing for USA, the same geometric crossing logic reconstructs its legs.

## Manoeuvres and progress

Tacks and gybes require both a true-wind-angle sign transition and sufficient heading change, speed loss, and hysteresis; see `pipeline/manoeuvres.py` for exact thresholds. Manoeuvre metrics record entry speed, minimum speed, loss, and recovery time.

Progress projects the bow onto the current leg direction and adds completed leg lengths. A running maximum prevents progress from decreasing during a tack or course excursion. Official finish timing determines final classification. The browser interpolates this already reconstructed progress and does not recompute gate events.

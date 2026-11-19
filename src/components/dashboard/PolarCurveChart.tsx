import type { BoatPolarObservedBin, PolarBracketCurve } from '../../types/analysis'

export function PolarCurveChart({
  bracket,
  mode,
  observedBins = [],
  boatLabel,
}: {
  bracket: PolarBracketCurve | undefined
  mode: 'upwind' | 'downwind'
  observedBins?: BoatPolarObservedBin[]
  boatLabel?: string
}) {
  if (!bracket || bracket.points.length === 0) {
    return (
      <p className="analysis-empty">
        Insufficient steady-state support in this wind bracket to render the conditional polar
        curve.
      </p>
    )
  }

  const pts = bracket.points
  const filteredBins = observedBins.filter(
    (entry) =>
      entry.tws_bin_kt >= bracket.tws_min_kt - 1.0 && entry.tws_bin_kt <= bracket.tws_max_kt + 1.0
  )

  const minTwa = Math.min(...pts.map((p) => p.twa_deg), ...filteredBins.map((b) => b.twa_bin_deg))
  const maxTwa = Math.max(...pts.map((p) => p.twa_deg), ...filteredBins.map((b) => b.twa_bin_deg))
  const allSpeeds = [
    ...pts.flatMap((p) => [p.mean_sog_kt, p.p50_sog_kt, p.p90_sog_kt]),
    ...filteredBins.map((b) => b.sog_mean_kt),
  ]
  const rawMinSpd = Math.min(...allSpeeds)
  const rawMaxSpd = Math.max(...allSpeeds)
  const minSpd = Math.max(0, Math.floor((rawMinSpd - 2) / 5) * 5)
  const maxSpd = Math.ceil((rawMaxSpd + 2) / 5) * 5
  const twaSpan = Math.max(10, maxTwa - minTwa)
  const spdSpan = Math.max(5, maxSpd - minSpd)

  const W = 640
  const H = 260
  const padL = 52
  const padR = 20
  const padT = 18
  const padB = 38
  const plotW = W - padL - padR
  const plotH = H - padT - padB

  const sx = (twa: number) => padL + ((twa - minTwa) / twaSpan) * plotW
  const sy = (sog: number) => padT + (1 - (sog - minSpd) / spdSpan) * plotH

  const pathFor = (accessor: (p: (typeof pts)[number]) => number) =>
    pts
      .map(
        (p, idx) =>
          `${idx === 0 ? 'M' : 'L'} ${sx(p.twa_deg).toFixed(1)} ${sy(accessor(p)).toFixed(1)}`
      )
      .join(' ')

  const yTicks = Array.from({ length: 5 }, (_, i) => minSpd + (spdSpan * i) / 4)
  const xStep = mode === 'upwind' ? 10 : 15
  const xStart = Math.ceil(minTwa / xStep) * xStep
  const xTicks: number[] = []
  for (let v = xStart; v <= maxTwa + 0.1; v += xStep) xTicks.push(v)

  return (
    <div className="polar-chart-card">
      <div className="polar-legend" aria-label="Polar curve legend">
        <span>
          <i className="polar-swatch p90" />
          Observed p90 (upper conditional percentile)
        </span>
        <span>
          <i className="polar-swatch p50" />
          Conditional median (p50)
        </span>
        <span>
          <i className="polar-swatch mean" />
          Conditional mean SOG
        </span>
        {filteredBins.length > 0 && (
          <>
            <span>
              <i className="polar-swatch port" />
              {boatLabel ?? 'Boat'} Port bins
            </span>
            <span>
              <i className="polar-swatch stbd" />
              {boatLabel ?? 'Boat'} Stbd bins
            </span>
          </>
        )}
      </div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="polar-svg-chart"
        role="img"
        aria-label={`Observed ground-speed polar for ${mode} sailing in ${bracket.label}`}
      >
        {yTicks.map((tick) => (
          <g key={`y-${tick}`}>
            <line
              x1={padL}
              y1={sy(tick)}
              x2={W - padR}
              y2={sy(tick)}
              stroke="#e2e8f0"
              strokeWidth="1"
            />
            <text x={padL - 8} y={sy(tick) + 4} textAnchor="end" fill="#475569" fontSize="11">
              {tick.toFixed(0)} kt
            </text>
          </g>
        ))}
        {xTicks.map((tick) => (
          <g key={`x-${tick}`}>
            <line
              x1={sx(tick)}
              y1={padT}
              x2={sx(tick)}
              y2={H - padB}
              stroke="#f1f5f9"
              strokeWidth="1"
            />
            <text x={sx(tick)} y={H - padB + 16} textAnchor="middle" fill="#475569" fontSize="11">
              {tick.toFixed(0)}°
            </text>
          </g>
        ))}
        <line
          x1={padL}
          y1={H - padB}
          x2={W - padR}
          y2={H - padB}
          stroke="#94a3b8"
          strokeWidth="1"
        />
        <line x1={padL} y1={padT} x2={padL} y2={H - padB} stroke="#94a3b8" strokeWidth="1" />
        <text x={W / 2} y={H - 4} textAnchor="middle" fill="#475569" fontSize="11">
          |TRUE WIND ANGLE| (DEGREES) · REF TWS {bracket.tws_ref_kt.toFixed(1)} KT
        </text>
        <path
          d={pathFor((p) => p.p90_sog_kt)}
          fill="none"
          stroke="#0f766e"
          strokeWidth="2"
          strokeDasharray="6 4"
        />
        <path
          d={pathFor((p) => p.mean_sog_kt)}
          fill="none"
          stroke="#334155"
          strokeWidth="1.75"
          strokeDasharray="2 3"
        />
        <path d={pathFor((p) => p.p50_sog_kt)} fill="none" stroke="#1a73e8" strokeWidth="2.75" />
        {filteredBins.map((bin, idx) =>
          bin.tack === 'PORT' ? (
            <circle
              key={`bin-${idx}`}
              cx={sx(bin.twa_bin_deg)}
              cy={sy(bin.sog_mean_kt)}
              r={Math.min(7, 3 + Math.sqrt(bin.sample_count) * 0.4)}
              fill="#c2410c"
              fillOpacity="0.82"
              stroke="#ffffff"
              strokeWidth="1"
            >
              <title>
                {`PORT |TWA| ${bin.twa_bin_deg}° · TWS ${bin.tws_bin_kt} kt: ${bin.sog_mean_kt} kt (pred ${bin.predicted_sog_kt} kt, n=${bin.sample_count}s)`}
              </title>
            </circle>
          ) : (
            <rect
              key={`bin-${idx}`}
              x={sx(bin.twa_bin_deg) - 3.5}
              y={sy(bin.sog_mean_kt) - 3.5}
              width="7"
              height="7"
              rx="1.5"
              fill="#0369a1"
              fillOpacity="0.82"
              stroke="#ffffff"
              strokeWidth="1"
            >
              <title>
                {`STARBOARD |TWA| ${bin.twa_bin_deg}° · TWS ${bin.tws_bin_kt} kt: ${bin.sog_mean_kt} kt (pred ${bin.predicted_sog_kt} kt, n=${bin.sample_count}s)`}
              </title>
            </rect>
          )
        )}
      </svg>
    </div>
  )
}

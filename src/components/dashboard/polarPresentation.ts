import type { PolarBootstrapInterval, PolarTackContrast } from '../../types/analysis'

export function formatSigned(value: number | null | undefined, digits = 2, unit = ' kt') {
  if (value === null || value === undefined || !Number.isFinite(value)) return 'Unavailable'
  const sign = value > 0 ? '+' : value < 0 ? '−' : ''
  return `${sign}${Math.abs(value).toFixed(digits)}${unit}`
}

export function formatBootstrapCi(interval: PolarBootstrapInterval | null | undefined) {
  if (!interval) return 'Unavailable'
  return `${formatSigned(interval.value, 2, ' kt')} [${formatSigned(interval.ci_low_kt, 2, '')}, ${formatSigned(interval.ci_high_kt, 2, '')}]`
}

export function formatTackContrast(contrast: PolarTackContrast | null | undefined) {
  if (!contrast) return 'Unavailable'
  return `${formatSigned(contrast.contrast_kt, 3, ' kt')} [${formatSigned(contrast.ci_low_kt, 3, '')}, ${formatSigned(contrast.ci_high_kt, 3, '')}]`
}

export function formatMetric(value: number | null | undefined, digits = 3, unit = '') {
  return value === null || value === undefined || !Number.isFinite(value)
    ? 'Unavailable'
    : `${value.toFixed(digits)}${unit}`
}

export function formatPercent(value: number | null | undefined) {
  return value === null || value === undefined ? 'Unavailable' : formatMetric(value * 100, 1, '%')
}

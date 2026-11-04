import { describe, expect, it } from 'vitest'
import { evidenceText } from './evidenceText'

describe('plain-language evidence labels', () => {
  it('keeps calculated timing distinct from official results', () => {
    expect(evidenceText('Reconstructed from source timing; not independently verified official results.')).toBe('Calculated from source timing; not independently verified official results.')
    expect(evidenceText('reconstructed · missing crossing')).toBe('calculated · missing crossing')
    expect(evidenceText('RECONSTRUCTED RESULT')).toBe('CALCULATED RESULT')
  })
  it('preserves unavailable reasons and accepts empty optional text', () => {
    expect(evidenceText('Unavailable: no valid racing window')).toBe('Unavailable: no valid racing window')
    expect(evidenceText(undefined)).toBe('')
  })
})

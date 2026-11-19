import { describe, expect, it } from 'vitest'
import { angleLerp, lerp } from './interpolate'

describe('interpolation', () => {
  it('takes the short path through north for wrapped headings', () =>
    expect(angleLerp(359, 1, 0.5)).toBe(0))
  it('keeps returned angles inside [0, 360)', () => expect(angleLerp(1, 359, 0.5)).toBe(0))
  it('interpolates positions linearly', () => expect(lerp(10, 30, 0.25)).toBe(15))
})

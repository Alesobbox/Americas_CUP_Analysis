/** Plain-language display copy; exported evidence codes and values stay intact. */
export function evidenceText(value: string | null | undefined): string {
  return (value ?? '')
    .replace(/\breconstructed\b/gi, (word) =>
      word === word.toUpperCase() ? 'CALCULATED' : word[0] === 'R' ? 'Calculated' : 'calculated'
    )
    .replace(/\breconstruction\b/gi, (word) =>
      word[0] === 'R' ? 'Telemetry calculation' : 'telemetry calculation'
    )
}

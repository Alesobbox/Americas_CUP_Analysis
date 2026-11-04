import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { forecastArtifactsPlugin } from './scripts/forecastArtifacts.ts'

export default defineConfig({
  plugins: [forecastArtifactsPlugin(), react()],
  server: {
    // Forecast objects are immutable and selected through index.json. Watching
    // them holds Windows file handles that can prevent atomic index replacement.
    // The forecast middleware reads new objects without that watch inventory.
    watch: { ignored: ['**/public/data/predictions', '**/public/data/predictions/**', '**/public/data/environment', '**/public/data/environment/**'] },
  },
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
    testTimeout: 60000,
  },
})

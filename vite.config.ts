import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    // Forecast objects are immutable and selected through index.json. Watching
    // them holds Windows file handles that can prevent atomic index replacement.
    watch: { ignored: ['**/public/data/predictions', '**/public/data/predictions/**'] },
  },
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
    testTimeout: 60000,
  },
})

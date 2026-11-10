import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'node',
    globals: true,
    setupFiles: ['./tests/vitestCompatibility.mjs', './tests/setup.js'],
    include: ['tests/**/*.test.js'],
    fileParallelism: false,
    restoreMocks: false,
  },
});


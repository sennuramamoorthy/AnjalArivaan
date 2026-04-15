import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    include: [
      'src/**/*.{test,spec}.ts',
      '../../../tests/unit/packages/logger/**/*.{test,spec}.ts',
    ],
  },
});

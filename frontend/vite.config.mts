/// <reference types="vitest" />
import angular from '@analogjs/vite-plugin-angular';
import { defineConfig } from 'vite';

// Angular 19 has no first-party Vitest builder (that arrives in 20+), so the supported
// route is AnalogJS's plugin. Bonus: jsdom means tests need no Chrome, locally or in CI.
export default defineConfig(({ mode }) => ({
  plugins: [angular()],
  // Without this, Vite mis-resolves Angular's fesm2022 testing bundle
  // ("Failed to resolve import @angular/core/fesm2022/null").
  resolve: { mainFields: ['module'] },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['src/test-setup.ts'],
    include: ['src/**/*.spec.ts'],
    reporters: ['default'],
  },
  define: { 'import.meta.vitest': mode !== 'production' },
}));

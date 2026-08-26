import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    exclude: ["node_modules", "dist", "scripts/verify-*.mjs", "tests/e2e/**"],
    coverage: {
      provider: "v8",
      reporter: ["text", "html", "lcov"],
      include: ["src/lib/**/*.ts", "src/pages/builder/**/*.ts"],
      exclude: ["src/**/*.test.{ts,tsx}", "src/**/*.d.ts"],
    },
  },
});

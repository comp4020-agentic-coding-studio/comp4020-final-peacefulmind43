import { defineConfig } from "vitest/config";

// Every test in spec/ runs against the running app, which spec/global-setup.ts
// finds. Only spec/ runs: a test anywhere else needs adding to `include`.
export default defineConfig({
  test: {
    include: ["spec/**/*.test.ts"],
    globalSetup: ["./spec/global-setup.ts"],
    // The files share one running app and its round, and several count trials
    // or listen for live events, so they run one at a time.
    fileParallelism: false,
  },
});

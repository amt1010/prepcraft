import "dotenv/config";
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup/dbCleanup.ts", "./tests/setup/jestDom.ts"],
    passWithNoTests: true,
    clearMocks: true,
    // Integration test files share one real Postgres database and each
    // does global deleteMany() cleanup in beforeEach — running files in
    // parallel lets one file's cleanup stomp on another's fixtures mid-test.
    fileParallelism: false,
  },
});

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Reads VITE_* variables from the repository root .env (shared with backend/compose).
export default defineConfig({
  plugins: [react()],
  envDir: "..",
  server: { port: 5173 },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    // Tests must never depend on a developer's .env: the API base URL is the code default.
    env: { VITE_API_BASE_URL: "http://localhost:8000" },
  },
});

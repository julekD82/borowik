/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import preact from "@preact/preset-vite";
import { dataFilesPlugin } from "./scripts/data-files-plugin.mjs";

export default defineConfig({
  plugins: [preact(), dataFilesPlugin()],
  test: {
    environment: "node",
    setupFiles: ["./src/test-setup.ts"],
  },
});

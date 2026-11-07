import { defineConfig } from "tsup";

// Bundle the API (and @rtt/shared, which ships as TS source) into one ESM file
// for the Cloud Run container. Real npm deps stay external and are installed.
export default defineConfig({
  entry: ["src/index.ts"],
  format: ["esm"],
  platform: "node",
  target: "node22",
  outDir: "dist",
  clean: true,
  sourcemap: true,
  noExternal: ["@rtt/shared"],
});

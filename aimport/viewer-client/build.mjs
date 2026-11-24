// Builds the standalone Neuroglancer viewer (index.html, bundles, chunk and async-computation workers)
// into the folder given as the only argument: node build.mjs <out-dir>
// Then copies uPlot's prebuilt browser files (the ephys trace viewer, /viewer/assets/uplot/) to <out-dir>/vendor/uplot/.
// Follows neuroglancer's examples/vite (esbuild alone cannot bundle its `new URL(..., import.meta.url)` workers).
import { copyFileSync, mkdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { build } from "vite";

const outDir = process.argv[2];
if (!outDir) {
  console.error("usage: node build.mjs <out-dir>");
  process.exit(2);
}
const root = path.dirname(fileURLToPath(import.meta.url));

await build({
  root,
  configFile: false,
  base: "", // relative URLs: the engine serves the client under /viewer/ng/
  logLevel: "warn",
  resolve: {
    // only what the QA viewer uses: image layers from NIfTI files and OME-Zarr groups (microscopy, Zarr v2
    // and v3 with sharding) over http on the engine's own origin
    conditions: [
      "neuroglancer/datasource:none_by_default",
      "neuroglancer/datasource/nifti:enabled",
      "neuroglancer/datasource/zarr:enabled",
      "neuroglancer/kvstore:none_by_default",
      "neuroglancer/kvstore/http:enabled",
      "neuroglancer/kvstore/byte_range:enabled",
      "neuroglancer/kvstore/gzip:enabled",
      "neuroglancer/layer:none_by_default",
      "neuroglancer/layer/image:enabled",
    ],
  },
  worker: { format: "es" }, // required by neuroglancer's dynamic imports
  build: {
    outDir: path.resolve(outDir),
    emptyOutDir: true,
    chunkSizeWarningLimit: 4 * 1024 * 1024,
    sourcemap: false,
  },
});

// uPlot for the trace viewer: its own prebuilt IIFE and stylesheet, as published (no bundling)
const uplot = path.resolve(outDir, "vendor", "uplot");
mkdirSync(uplot, { recursive: true });
for (const name of ["uPlot.iife.min.js", "uPlot.min.css"]) {
  copyFileSync(path.join(root, "node_modules", "uplot", "dist", name), path.join(uplot, name));
}

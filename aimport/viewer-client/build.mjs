// Builds the standalone Neuroglancer viewer (index.html, bundles, chunk and async-computation workers)
// into the folder given as the only argument: node build.mjs <out-dir>
// Follows neuroglancer's examples/vite (esbuild alone cannot bundle its `new URL(..., import.meta.url)` workers).
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
    // only what the QA viewer uses: image layers from NIfTI files over http on the engine's own origin
    conditions: [
      "neuroglancer/datasource:none_by_default",
      "neuroglancer/datasource/nifti:enabled",
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

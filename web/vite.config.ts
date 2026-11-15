import path from "node:path";
import { fileURLToPath } from "node:url";
import type { Plugin } from "vite";
import { defineConfig } from "vitest/config";
import { dataSeparation } from "./plugins/data-separation.ts";

const webRoot = path.dirname(fileURLToPath(import.meta.url));

// In production builds, forbid every non-local request at the browser level.
const csp: Plugin = {
  name: "inject-csp",
  apply: "build",
  transformIndexHtml(html) {
    const policy =
      "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; " +
      "base-uri 'none'; form-action 'none'";
    return html.replace("<head>", `<head>\n    <meta http-equiv="Content-Security-Policy" content="${policy}" />`);
  },
};

export default defineConfig({
  base: "./",
  publicDir: false, // nothing is copied into a bundle implicitly; data goes through dataSeparation only
  plugins: [
    csp,
    dataSeparation({
      demoDir: path.join(webRoot, "demo-data"),
      fixturePath: path.join(webRoot, "..", "fixtures", "synthetic_usgs.geojson"),
      localDir: path.join(webRoot, "..", "data", "derived"),
    }),
  ],
  build: { target: "es2022", sourcemap: false },
  test: { environment: "node", include: ["tests/**/*.test.ts"] },
});

import type { NextConfig } from "next";

/**
 * Static export. The site has no backend: it reads JSON produced by the
 * Python pipeline and verifies everything it shows against Solana in the
 * browser. A static build means an assessor can serve the whole thing
 * from a folder and reach the same result as the hosted copy.
 */
const nextConfig: NextConfig = {
  output: "export",
  images: { unoptimized: true },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;

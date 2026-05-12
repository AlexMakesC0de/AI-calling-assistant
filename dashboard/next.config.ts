import type { NextConfig } from "next";

const config: NextConfig = {
  // Emit a minimal self-contained server bundle under .next/standalone.
  // Shrinks the runtime image and removes the need to ship node_modules.
  output: "standalone",
  // Keep Prisma out of the webpack bundle — it loads its engine from
  // node_modules/.prisma/client at runtime, which requires the package
  // to stay as real files rather than be inlined.
  serverExternalPackages: ["@prisma/client", "prisma"],
  experimental: {
    serverActions: { bodySizeLimit: "25mb" },
  },
};

export default config;

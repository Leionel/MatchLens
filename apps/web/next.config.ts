import type { NextConfig } from "next";

const config: NextConfig = {
  output: "export",
  images: { unoptimized: true },
  ...(process.env.NODE_ENV === "development"
    ? {
        async rewrites() {
          return [
            {
              source: "/api/:path*",
              destination: `${process.env.MATCHLENS_API_ORIGIN || "http://127.0.0.1:8000"}/api/:path*`,
            },
          ];
        },
      }
    : {}),
};
export default config;

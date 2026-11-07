import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // @rtt/shared ships as TypeScript source
  transpilePackages: ["@rtt/shared"],
  poweredByHeader: false,
  images: {
    remotePatterns: [{ protocol: "https", hostname: "places.googleapis.com" }],
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
        ],
      },
    ];
  },
};

export default nextConfig;

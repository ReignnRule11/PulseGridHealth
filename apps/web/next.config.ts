import path from "node:path";
import type { NextConfig } from "next";

const backendOrigin = process.env.API_BACKEND_ORIGIN;

if (process.env.VERCEL === "1" && !backendOrigin) {
  throw new Error("API_BACKEND_ORIGIN must be configured in Vercel for the same-origin API proxy.");
}

if (backendOrigin) {
  const parsed = new URL(backendOrigin);
  if (!["http:", "https:"].includes(parsed.protocol) || parsed.pathname !== "/" || parsed.search || parsed.hash || parsed.username || parsed.password || (process.env.VERCEL === "1" && parsed.protocol !== "https:")) {
    throw new Error("API_BACKEND_ORIGIN must be an HTTPS origin on Vercel (no path, query, or credentials).");
  }
}

const nextConfig: NextConfig = {
  outputFileTracingRoot: path.resolve(process.cwd(), "../.."),
  async rewrites() {
    if (!backendOrigin) return [];
    return [{ source: "/api/:path*", destination: `${backendOrigin}/api/:path*` }];
  },
};

export default nextConfig;

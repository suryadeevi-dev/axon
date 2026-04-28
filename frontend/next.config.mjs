

const isProd = process.env.NODE_ENV === "production";
const isGhPages = process.env.DEPLOY_TARGET === "gh-pages";

const nextConfig = {
  output: isGhPages ? "export" : "standalone",
  // GitHub Pages deploys to /axon/ subdirectory
  basePath: isGhPages ? "/axon" : "",
  assetPrefix: isGhPages ? "/axon/" : "",
  trailingSlash: true,
  images: {
    unoptimized: true,
  },
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
    NEXT_PUBLIC_WS_URL: process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000",
  },
};

export default nextConfig;

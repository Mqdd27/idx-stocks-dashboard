/** @type {import('next').NextConfig} */
const nextConfig = {
  output: process.env.NEXT_OUTPUT === "export" ? "export" : "standalone",
  images: { unoptimized: true },
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://127.0.0.1:8200/api/:path*",
      },
      {
        source: "/health",
        destination: "http://127.0.0.1:8200/health",
      },
    ];
  },
};

export default nextConfig;
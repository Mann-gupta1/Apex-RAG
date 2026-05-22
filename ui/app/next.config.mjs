/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  reactStrictMode: true,
  experimental: {},
  async rewrites() {
    const api = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
    return [
      { source: "/proxy/api/:path*", destination: `${api}/api/:path*` },
      { source: "/proxy/graphql", destination: `${api}/graphql` },
    ];
  },
};

export default nextConfig;

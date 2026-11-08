/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
};

// Portable Windows build only. `npm run dev` does not set this.
if (process.env.WEBDELTA_STATIC_EXPORT === "1") {
  nextConfig.output = "export";
}

export default nextConfig;


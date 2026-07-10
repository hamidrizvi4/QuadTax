import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Hide the dev-mode route indicator — it overlaps the wizard's fixed
  // bottom CTA bar on mobile viewports (and shouldn't appear in demos).
  // Build/runtime errors still surface normally.
  devIndicators: false,
};

export default nextConfig;

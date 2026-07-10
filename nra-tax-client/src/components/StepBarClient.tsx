'use client';

import dynamic from 'next/dynamic';

// StepBar uses usePathname(), which touches the browser `location` global.
// During static prerender (next build) that global is undefined, throwing
// "location is not defined". Loading it client-only via ssr:false avoids the
// server-side render entirely. ssr:false must live in a Client Component
// (Next.js 16 disallows it inside Server Components like layout.tsx).
const StepBar = dynamic(
  () => import('@/components/StepBar').then((mod) => ({ default: mod.StepBar })),
  { ssr: false },
);

export function StepBarClient() {
  return <StepBar />;
}

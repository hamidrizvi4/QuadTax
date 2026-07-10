import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { StepBarClient } from "@/components/StepBarClient";

// This is a user-specific tax app (no SEO benefit from static HTML). Forcing
// dynamic rendering also sidesteps a Next.js 16 framework bug where the router
// infrastructure touches the browser `location` global during static
// prerender, logging a non-fatal "location is not defined" ReferenceError.
export const dynamic = "force-dynamic";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: {
    default: "QuadTax — US tax filing for international students",
    template: "%s | QuadTax",
  },
  description:
    "Photograph your W-2 and we handle the rest. Document-first 1040-NR filing for F-1 and J-1 students — 66 verified tax treaties, FICA refund detection, and deterministic, CPA-auditable math.",
  keywords: [
    "1040-NR",
    "nonresident tax",
    "F-1 taxes",
    "J-1 taxes",
    "international student taxes",
    "tax treaty",
    "FICA refund",
  ],
  openGraph: {
    title: "QuadTax — US tax filing for international students",
    description:
      "Document-first 1040-NR filing: AI reads your paperwork, deterministic math computes your return.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
          <StepBarClient />
          {children}
        </body>
    </html>
  );
}

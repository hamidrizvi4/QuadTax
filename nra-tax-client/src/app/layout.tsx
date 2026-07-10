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
  title: "QuadTax — NRA Tax Filing",
  description: "AI-powered US tax filing for international students on F-1 and J-1 visas.",
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

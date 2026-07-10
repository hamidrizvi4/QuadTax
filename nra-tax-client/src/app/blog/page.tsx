import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft, ArrowRight, BookOpen, ShieldCheck } from "lucide-react";

import { BLOG_POSTS } from "@/lib/blog-posts";

export const metadata: Metadata = {
  title: "Insights — QuadTax",
  description:
    "How QuadTax computes nonresident tax returns: deterministic math, treaty law, and the refunds most international students never claim.",
};

export default function BlogIndexPage() {
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex h-16 max-w-4xl items-center justify-between px-4 sm:px-6">
          <Link href="/" className="flex items-center gap-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600">
              <ShieldCheck className="h-4.5 w-4.5 text-white" />
            </span>
            <span className="font-extrabold tracking-tight">
              Quad<span className="text-blue-600">Tax</span>
            </span>
          </Link>
          <Link
            href="/"
            className="flex items-center gap-1.5 text-sm font-semibold text-slate-500 transition-colors hover:text-slate-900"
          >
            <ArrowLeft className="h-4 w-4" /> Back to home
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-4xl px-4 py-14 sm:px-6">
        <p className="text-sm font-bold uppercase tracking-widest text-blue-600">
          From the engine room
        </p>
        <h1 className="mt-3 text-4xl font-extrabold tracking-tight text-slate-900">
          Insights
        </h1>
        <p className="mt-4 max-w-2xl text-lg text-slate-600">
          How the engine works, why nonresident returns are different, and the
          refunds generic software leaves on the table.
        </p>

        <div className="mt-12 space-y-6">
          {BLOG_POSTS.map((post) => (
            <Link
              key={post.slug}
              href={`/blog/${post.slug}`}
              className="group block rounded-3xl border border-slate-200 bg-white p-8 shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-md"
            >
              <div className="flex flex-wrap items-center gap-2 text-xs font-semibold">
                <span className="rounded-full bg-blue-50 px-2.5 py-1 text-blue-700">
                  {post.category}
                </span>
                <span className="text-slate-400">{post.readMinutes} min read</span>
                <span className="text-slate-300">·</span>
                <time dateTime={post.date} className="text-slate-400">
                  {new Date(post.date + "T00:00:00").toLocaleDateString("en-US", {
                    month: "long",
                    day: "numeric",
                    year: "numeric",
                  })}
                </time>
              </div>
              <h2 className="mt-4 text-2xl font-bold leading-snug text-slate-900 transition-colors group-hover:text-blue-700">
                {post.title}
              </h2>
              <p className="mt-3 max-w-2xl leading-relaxed text-slate-500">{post.excerpt}</p>
              <span className="mt-5 inline-flex items-center gap-1.5 text-sm font-semibold text-blue-600">
                <BookOpen className="h-4 w-4" /> Read article{" "}
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
              </span>
            </Link>
          ))}
        </div>
      </main>
    </div>
  );
}

import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, ArrowRight, ShieldCheck } from "lucide-react";

import { BLOG_POSTS, getPost } from "@/lib/blog-posts";

export function generateStaticParams() {
  return BLOG_POSTS.map((post) => ({ slug: post.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const post = getPost(slug);
  if (!post) return { title: "Article not found — QuadTax" };
  return {
    title: `${post.title} — QuadTax`,
    description: post.excerpt,
  };
}

export default async function BlogPostPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const post = getPost(slug);
  if (!post) notFound();

  const others = BLOG_POSTS.filter((p) => p.slug !== post.slug);

  return (
    <div className="min-h-screen bg-white">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex h-16 max-w-3xl items-center justify-between px-4 sm:px-6">
          <Link href="/" className="flex items-center gap-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600">
              <ShieldCheck className="h-4.5 w-4.5 text-white" />
            </span>
            <span className="font-extrabold tracking-tight">
              Quad<span className="text-blue-600">Tax</span>
            </span>
          </Link>
          <Link
            href="/blog"
            className="flex items-center gap-1.5 text-sm font-semibold text-slate-500 transition-colors hover:text-slate-900"
          >
            <ArrowLeft className="h-4 w-4" /> All articles
          </Link>
        </div>
      </header>

      <article className="mx-auto max-w-3xl px-4 py-14 sm:px-6">
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

        <h1 className="mt-5 text-3xl font-extrabold leading-tight tracking-tight text-slate-900 sm:text-4xl">
          {post.title}
        </h1>

        <div className="mt-10 space-y-10">
          {post.sections.map((section, i) => (
            <section key={i}>
              {section.heading && (
                <h2 className="mb-4 text-2xl font-bold tracking-tight text-slate-900">
                  {section.heading}
                </h2>
              )}
              <div className="space-y-5">
                {section.paragraphs.map((p, j) => (
                  <p key={j} className="text-[17px] leading-relaxed text-slate-600">
                    {p}
                  </p>
                ))}
              </div>
            </section>
          ))}
        </div>

        <div className="mt-14 rounded-3xl bg-slate-900 p-8 text-center">
          <h2 className="text-xl font-bold text-white">
            Ready to see it work on your documents?
          </h2>
          <Link
            href="/intake/eligibility"
            className="group mt-5 inline-flex items-center gap-2 rounded-full bg-white px-6 py-3 text-sm font-bold text-slate-900 transition-all hover:bg-blue-50 active:scale-95"
          >
            Start my tax return
            <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
          </Link>
        </div>

        {others.length > 0 && (
          <aside className="mt-14 border-t border-slate-200 pt-10">
            <p className="text-sm font-bold uppercase tracking-widest text-slate-400">
              Keep reading
            </p>
            <div className="mt-5 grid gap-4 sm:grid-cols-2">
              {others.map((p) => (
                <Link
                  key={p.slug}
                  href={`/blog/${p.slug}`}
                  className="group rounded-2xl border border-slate-200 p-5 transition-all hover:border-blue-200 hover:bg-blue-50/40"
                >
                  <p className="text-xs font-semibold text-blue-600">{p.category}</p>
                  <p className="mt-2 font-bold leading-snug text-slate-900 group-hover:text-blue-700">
                    {p.title}
                  </p>
                </Link>
              ))}
            </div>
          </aside>
        )}
      </article>
    </div>
  );
}

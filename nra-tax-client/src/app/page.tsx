import Image from "next/image";
import Link from "next/link";
import {
  ArrowRight,
  BadgeCheck,
  BookOpen,
  CheckCircle2,
  FileScan,
  FileText,
  Globe,
  Landmark,
  Quote,
  ScanLine,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";

import { BLOG_POSTS } from "@/lib/blog-posts";

const NAV_LINKS = [
  { href: "#how-it-works", label: "How it works" },
  { href: "#why-quadtax", label: "Why QuadTax" },
  { href: "#stories", label: "Stories" },
  { href: "#insights", label: "Insights" },
  { href: "#faq", label: "FAQ" },
];

const STATS = [
  { value: "66", label: "treaty countries, verified against IRS Pub 901" },
  { value: "324", label: "automated tests guarding every calculation" },
  { value: "13", label: "federal & NY forms populated per return" },
  { value: "$5,066", label: "recovered in our worked NYU test scenario" },
];

const STEPS = [
  {
    icon: FileScan,
    title: "Snap your documents",
    body: "Upload your I-94, W-2, 1042-S, and any 1099s. Photos or PDFs — all four corners visible is all we ask.",
  },
  {
    icon: ScanLine,
    title: "AI reads every box",
    body: "OCR plus a structured-output model extracts each field — wages, withholding, income codes — into typed data. No retyping.",
  },
  {
    icon: CheckCircle2,
    title: "Confirm, don't type",
    body: "The next screen arrives pre-filled from your documents. Review the numbers, correct anything the scan missed, and continue.",
  },
  {
    icon: FileText,
    title: "Download your packet",
    body: "Deterministic math produces your 1040-NR, state IT-203, and FICA refund claim — assembled in IRS mailing order with cover sheets.",
  },
];

const COMPARISON: {
  feature: string;
  detail: string;
  quadtax: boolean;
  generic: boolean;
  diy: boolean;
}[] = [
  {
    feature: "Built for Form 1040-NR",
    detail: "Nonresident returns are the product, not an afterthought",
    quadtax: true,
    generic: false,
    diy: true,
  },
  {
    feature: "66-country treaty engine",
    detail: "Every article, cap, and year limit verified against IRS Pub 901",
    quadtax: true,
    generic: false,
    diy: false,
  },
  {
    feature: "FICA refund detection",
    detail: "Auto-generates Form 843 for wrongly-withheld Social Security & Medicare",
    quadtax: true,
    generic: false,
    diy: false,
  },
  {
    feature: "NY treaty add-back",
    detail: "Knows New York doesn't honor federal treaties (NY Pub 88)",
    quadtax: true,
    generic: false,
    diy: false,
  },
  {
    feature: "Deterministic math + audit log",
    detail: "Same inputs, same return, every time — with per-layer citations",
    quadtax: true,
    generic: false,
    diy: false,
  },
  {
    feature: "Document-first intake",
    detail: "OCR pre-fills the wizard; you confirm instead of typing",
    quadtax: true,
    generic: true,
    diy: false,
  },
];

const TESTIMONIALS = [
  {
    quote:
      "I had no idea NYU was withholding Social Security tax it never should have taken. QuadTax caught $2,486 of it and produced the exact Form 843 packet to claim it back.",
    name: "Wei C.",
    role: "F-1 · PhD candidate, New York",
    initials: "WC",
    avatarClass: "from-rose-500 to-orange-400",
    highlight: "$5,066 recovered",
  },
  {
    quote:
      "Every other tool made me type my W-2 line by line. Here I photographed it, and the review screen was already filled in. I corrected one digit and I was done.",
    name: "Arjun S.",
    role: "F-1 · Graduate researcher, New York",
    initials: "AS",
    avatarClass: "from-blue-600 to-sky-400",
    highlight: "$4,995 recovered",
  },
  {
    quote:
      "As the only Korean student in my program, nobody could tell me if the $2,000 treaty exemption applied to me. QuadTax cited the exact article — 21(1) — and applied it automatically.",
    name: "Min-ji K.",
    role: "F-1 · Master's student, Ithaca",
    initials: "MK",
    avatarClass: "from-violet-600 to-fuchsia-400",
    highlight: "Treaty applied · Art 21(1)",
  },
];

const FAQS = [
  {
    q: "Who is QuadTax for?",
    a: "Nonresident international students and scholars on F-1, J-1, M-1, or Q-1 visas who need to file a US federal Form 1040-NR — and, if they lived or worked in New York, the state IT-203. If you're a US citizen, green-card holder, or resident alien, this tool isn't the right fit.",
  },
  {
    q: "How does the document extraction work?",
    a: "Your uploads pass through OCR text extraction, then a structured-output language model that can only return the exact typed fields on each form — it cannot invent boxes that aren't there. Every extracted number is shown to you for confirmation before any tax math runs, and reasonability validators flag anything suspicious for human review.",
  },
  {
    q: "Is AI calculating my taxes?",
    a: "No — and that's the point. AI reads your documents and classifies your income description. Every calculation (brackets, treaty caps, FICA, New York add-backs) is deterministic, citation-annotated Python verified by 324 automated tests, including twelve hand-computed golden scenarios.",
  },
  {
    q: "What is the FICA refund everyone mentions?",
    a: "F-1/J-1 students are exempt from Social Security and Medicare tax for their first five calendar years (IRC §3121(b)(19)), but employers' payroll systems usually withhold it anyway. That money doesn't come back through your tax return — it needs a separate Form 843 claim. QuadTax detects the error from your W-2 and generates the full claim packet automatically.",
  },
  {
    q: "Which tax treaties do you support?",
    a: "All 66 countries with US income-tax treaties covering students and scholars, each verified against IRS Publication 901 — including multi-article countries like China (Articles 19, 20(b), 20(c)), India's unique standard-deduction rule, and the terminated Hungary / suspended Russia treaties.",
  },
  {
    q: "Do you e-file for me?",
    a: "Not yet. QuadTax produces print-ready packets assembled in the IRS Publication 519 mailing order, with cover sheets showing exactly which service center each envelope goes to. Federal, New York, and FICA claims mail separately — we make that impossible to get wrong.",
  },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-white text-slate-900">
      {/* ── Nav ─────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-50 border-b border-slate-200/70 bg-white/80 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
          <Link href="/" className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-600 shadow-md shadow-blue-200">
              <ShieldCheck className="h-5 w-5 text-white" />
            </span>
            <span className="text-lg font-extrabold tracking-tight">
              Quad<span className="text-blue-600">Tax</span>
            </span>
          </Link>

          <nav className="hidden items-center gap-7 text-sm font-medium text-slate-600 md:flex">
            {NAV_LINKS.map((l) => (
              <a key={l.href} href={l.href} className="transition-colors hover:text-slate-900">
                {l.label}
              </a>
            ))}
          </nav>

          <Link
            href="/intake/eligibility"
            className="flex items-center gap-1.5 rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white shadow-sm transition-all hover:bg-slate-800 active:scale-95 sm:px-5"
          >
            Start filing
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </header>

      <main>
        {/* ── Hero ──────────────────────────────────────────────────── */}
        <section className="relative overflow-hidden">
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 bg-[radial-gradient(60rem_30rem_at_70%_-10%,rgba(37,99,235,0.10),transparent),radial-gradient(40rem_20rem_at_10%_10%,rgba(14,165,233,0.08),transparent)]"
          />
          <div className="relative mx-auto grid max-w-6xl items-center gap-12 px-4 pb-16 pt-14 sm:px-6 lg:grid-cols-2 lg:pb-24 lg:pt-20">
            <div className="text-center lg:text-left">
              <p className="mb-5 inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-3.5 py-1.5 text-xs font-semibold text-blue-700">
                <Sparkles className="h-3.5 w-3.5" />
                Built for F-1 &amp; J-1 nonresident returns · TY2025
              </p>

              <h1 className="text-4xl font-extrabold leading-[1.08] tracking-tight sm:text-5xl lg:text-[3.4rem]">
                Photograph your{" "}
                <span className="whitespace-nowrap">W&#8209;2.</span>
                <br />
                <span className="bg-gradient-to-r from-blue-600 to-sky-500 bg-clip-text text-transparent">
                  We handle the rest.
                </span>
              </h1>

              <p className="mx-auto mt-6 max-w-xl text-lg leading-relaxed text-slate-600 lg:mx-0">
                QuadTax reads your tax documents, applies the exact treaty
                article your country is entitled to, and produces a mail-ready
                1040-NR packet — with the FICA refund most students never know
                they&apos;re owed.
              </p>

              <div className="mt-8 flex flex-col items-center gap-4 sm:flex-row sm:justify-center lg:justify-start">
                <Link
                  href="/intake/eligibility"
                  className="group flex items-center gap-2.5 rounded-full bg-blue-600 px-7 py-3.5 text-base font-semibold text-white shadow-lg shadow-blue-200 transition-all hover:bg-blue-700 active:scale-95"
                >
                  Start my tax return
                  <ArrowRight className="h-5 w-5 transition-transform group-hover:translate-x-1" />
                </Link>
                <a
                  href="#how-it-works"
                  className="flex items-center gap-2 rounded-full border border-slate-300 px-6 py-3.5 text-base font-semibold text-slate-700 transition-colors hover:border-slate-400 hover:bg-slate-50"
                >
                  See how it works
                </a>
              </div>

              <ul className="mt-8 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-sm text-slate-500 lg:justify-start">
                <li className="flex items-center gap-1.5">
                  <BadgeCheck className="h-4 w-4 text-emerald-500" />
                  Deterministic math — no AI guessing
                </li>
                <li className="flex items-center gap-1.5">
                  <Globe className="h-4 w-4 text-blue-500" />
                  66 treaties, Pub 901-verified
                </li>
                <li className="flex items-center gap-1.5">
                  <Landmark className="h-4 w-4 text-violet-500" />
                  Federal + New York
                </li>
              </ul>
            </div>

            {/* Product mock */}
            <div className="relative mx-auto flex max-w-md justify-center gap-5 lg:max-w-none">
              <div className="relative w-56 shrink-0 -rotate-2 overflow-hidden rounded-[2rem] border-8 border-slate-900 shadow-2xl transition-transform duration-300 hover:rotate-0 sm:w-64">
                <Image
                  src="/screens/04-documents.png"
                  alt="QuadTax document upload step — snap a photo of your I-94, W-2, and 1042-S"
                  width={430}
                  height={932}
                  priority
                  className="h-auto w-full"
                />
              </div>
              <div className="relative mt-12 hidden w-56 rotate-2 overflow-hidden rounded-[2rem] border-8 border-slate-900 shadow-2xl transition-transform duration-300 hover:rotate-0 sm:block sm:w-64">
                <Image
                  src="/screens/05-review.png"
                  alt="QuadTax review step — every field pre-filled from your documents"
                  width={430}
                  height={932}
                  className="h-auto w-full"
                />
              </div>
            </div>
          </div>
        </section>

        {/* ── Stats band ────────────────────────────────────────────── */}
        <section className="border-y border-slate-200 bg-slate-50">
          <div className="mx-auto grid max-w-6xl grid-cols-2 gap-x-6 gap-y-8 px-4 py-10 sm:px-6 lg:grid-cols-4">
            {STATS.map((s) => (
              <div key={s.label} className="text-center lg:text-left">
                <p className="text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">
                  {s.value}
                </p>
                <p className="mt-1 text-sm leading-snug text-slate-500">{s.label}</p>
              </div>
            ))}
          </div>
        </section>

        {/* ── How it works ──────────────────────────────────────────── */}
        <section id="how-it-works" className="scroll-mt-20 py-20 lg:py-24">
          <div className="mx-auto max-w-6xl px-4 sm:px-6">
            <div className="mx-auto max-w-2xl text-center">
              <p className="text-sm font-bold uppercase tracking-widest text-blue-600">
                How it works
              </p>
              <h2 className="mt-3 text-3xl font-extrabold tracking-tight sm:text-4xl">
                Four steps. Almost no typing.
              </h2>
              <p className="mt-4 text-lg text-slate-600">
                The intake is document-first: your paperwork already contains
                the answers, so we extract them instead of asking you to copy
                them over.
              </p>
            </div>

            <ol className="mt-14 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
              {STEPS.map((step, i) => (
                <li
                  key={step.title}
                  className="relative rounded-3xl border border-slate-200 bg-white p-6 shadow-sm transition-shadow hover:shadow-md"
                >
                  <div className="flex items-center justify-between">
                    <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-blue-50">
                      <step.icon className="h-5 w-5 text-blue-600" />
                    </span>
                    <span className="text-4xl font-extrabold text-slate-100">{i + 1}</span>
                  </div>
                  <h3 className="mt-4 font-bold text-slate-900">{step.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-slate-500">{step.body}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* ── Why QuadTax ───────────────────────────────────────────── */}
        <section id="why-quadtax" className="scroll-mt-20 border-t border-slate-200 bg-slate-50 py-20 lg:py-24">
          <div className="mx-auto max-w-6xl px-4 sm:px-6">
            <div className="mx-auto max-w-2xl text-center">
              <p className="text-sm font-bold uppercase tracking-widest text-blue-600">
                Why QuadTax
              </p>
              <h2 className="mt-3 text-3xl font-extrabold tracking-tight sm:text-4xl">
                Generic tax software wasn&apos;t built for you
              </h2>
              <p className="mt-4 text-lg text-slate-600">
                Nonresident returns run on different rules — different forms,
                different rates, and treaty articles most tools have never
                heard of.
              </p>
            </div>

            <div className="mt-12 overflow-x-auto rounded-3xl border border-slate-200 bg-white shadow-sm">
              <table className="w-full min-w-[640px] text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-200">
                    <th className="px-6 py-4 font-semibold text-slate-500">Capability</th>
                    <th className="px-4 py-4 text-center">
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-600 px-3 py-1 text-xs font-bold text-white">
                        <ShieldCheck className="h-3.5 w-3.5" /> QuadTax
                      </span>
                    </th>
                    <th className="px-4 py-4 text-center text-xs font-semibold text-slate-500">
                      Generic tax software
                    </th>
                    <th className="px-4 py-4 text-center text-xs font-semibold text-slate-500">
                      Filing by hand
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {COMPARISON.map((row) => (
                    <tr key={row.feature} className="border-b border-slate-100 last:border-0">
                      <td className="px-6 py-4">
                        <p className="font-semibold text-slate-900">{row.feature}</p>
                        <p className="mt-0.5 text-xs text-slate-500">{row.detail}</p>
                      </td>
                      {[row.quadtax, row.generic, row.diy].map((ok, i) => (
                        <td key={i} className="px-4 py-4 text-center">
                          {ok ? (
                            <CheckCircle2
                              aria-label="Included"
                              className={`mx-auto h-5 w-5 ${i === 0 ? "text-emerald-500" : "text-slate-400"}`}
                            />
                          ) : (
                            <X aria-label="Not included" className="mx-auto h-5 w-5 text-slate-300" />
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <p className="mt-4 text-center text-xs text-slate-400">
              &ldquo;Generic tax software&rdquo; refers to resident-focused consumer products, which
              typically cannot produce Form 1040-NR at all.
            </p>
          </div>
        </section>

        {/* ── Testimonials ──────────────────────────────────────────── */}
        <section id="stories" className="scroll-mt-20 py-20 lg:py-24">
          <div className="mx-auto max-w-6xl px-4 sm:px-6">
            <div className="mx-auto max-w-2xl text-center">
              <p className="text-sm font-bold uppercase tracking-widest text-blue-600">Stories</p>
              <h2 className="mt-3 text-3xl font-extrabold tracking-tight sm:text-4xl">
                Filed in an evening, not a weekend
              </h2>
            </div>

            <div className="mt-12 grid gap-6 md:grid-cols-3">
              {TESTIMONIALS.map((t) => (
                <figure
                  key={t.name}
                  className="flex flex-col rounded-3xl border border-slate-200 bg-white p-7 shadow-sm transition-shadow hover:shadow-md"
                >
                  <Quote className="h-7 w-7 text-blue-200" aria-hidden />
                  <blockquote className="mt-4 flex-1 text-[15px] leading-relaxed text-slate-700">
                    {t.quote}
                  </blockquote>
                  <figcaption className="mt-6 flex items-center justify-between border-t border-slate-100 pt-5">
                    <div className="flex items-center gap-3">
                      <span
                        className={`flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br ${t.avatarClass} text-sm font-bold text-white`}
                      >
                        {t.initials}
                      </span>
                      <div>
                        <p className="text-sm font-bold text-slate-900">{t.name}</p>
                        <p className="text-xs text-slate-500">{t.role}</p>
                      </div>
                    </div>
                  </figcaption>
                  <p className="mt-4 rounded-xl bg-emerald-50 px-3 py-2 text-center text-xs font-bold text-emerald-700">
                    {t.highlight}
                  </p>
                </figure>
              ))}
            </div>

            <p className="mt-6 text-center text-xs text-slate-400">
              Illustrative scenarios drawn from QuadTax&apos;s verified test suite — the same
              golden fixtures that guard every release.
            </p>
          </div>
        </section>

        {/* ── Blog / Insights ───────────────────────────────────────── */}
        <section id="insights" className="scroll-mt-20 border-t border-slate-200 bg-slate-50 py-20 lg:py-24">
          <div className="mx-auto max-w-6xl px-4 sm:px-6">
            <div className="flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-end">
              <div>
                <p className="text-sm font-bold uppercase tracking-widest text-blue-600">
                  From the engine room
                </p>
                <h2 className="mt-3 text-3xl font-extrabold tracking-tight sm:text-4xl">
                  How it works, why it&apos;s different
                </h2>
              </div>
              <Link
                href="/blog"
                className="flex items-center gap-1.5 text-sm font-semibold text-blue-600 transition-colors hover:text-blue-700"
              >
                Read all articles <ArrowRight className="h-4 w-4" />
              </Link>
            </div>

            <div className="mt-10 grid gap-6 md:grid-cols-3">
              {BLOG_POSTS.map((post) => (
                <Link
                  key={post.slug}
                  href={`/blog/${post.slug}`}
                  className="group flex flex-col rounded-3xl border border-slate-200 bg-white p-7 shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-md"
                >
                  <div className="flex items-center gap-2 text-xs font-semibold">
                    <span className="rounded-full bg-blue-50 px-2.5 py-1 text-blue-700">
                      {post.category}
                    </span>
                    <span className="text-slate-400">{post.readMinutes} min read</span>
                  </div>
                  <h3 className="mt-4 text-lg font-bold leading-snug text-slate-900 transition-colors group-hover:text-blue-700">
                    {post.title}
                  </h3>
                  <p className="mt-3 flex-1 text-sm leading-relaxed text-slate-500">
                    {post.excerpt}
                  </p>
                  <span className="mt-5 flex items-center gap-1.5 text-sm font-semibold text-blue-600">
                    <BookOpen className="h-4 w-4" />
                    Read article
                  </span>
                </Link>
              ))}
            </div>
          </div>
        </section>

        {/* ── FAQ ───────────────────────────────────────────────────── */}
        <section id="faq" className="scroll-mt-20 py-20 lg:py-24">
          <div className="mx-auto max-w-3xl px-4 sm:px-6">
            <div className="text-center">
              <p className="text-sm font-bold uppercase tracking-widest text-blue-600">FAQ</p>
              <h2 className="mt-3 text-3xl font-extrabold tracking-tight sm:text-4xl">
                Questions students actually ask
              </h2>
            </div>

            <div className="mt-10 space-y-3">
              {FAQS.map((f) => (
                <details
                  key={f.q}
                  className="group rounded-2xl border border-slate-200 bg-white shadow-sm open:shadow-md"
                >
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-6 py-5 font-semibold text-slate-900 [&::-webkit-details-marker]:hidden">
                    {f.q}
                    <span
                      aria-hidden
                      className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-100 text-slate-500 transition-transform group-open:rotate-45"
                    >
                      +
                    </span>
                  </summary>
                  <p className="px-6 pb-6 text-[15px] leading-relaxed text-slate-600">{f.a}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        {/* ── Final CTA ─────────────────────────────────────────────── */}
        <section className="px-4 pb-20 sm:px-6">
          <div className="relative mx-auto max-w-6xl overflow-hidden rounded-[2.5rem] bg-slate-900 px-6 py-16 text-center shadow-2xl sm:px-16">
            <div
              aria-hidden
              className="pointer-events-none absolute inset-0 bg-[radial-gradient(40rem_18rem_at_50%_-20%,rgba(59,130,246,0.35),transparent)]"
            />
            <div className="relative">
              <h2 className="text-3xl font-extrabold tracking-tight text-white sm:text-4xl">
                Your refund is sitting in a PDF you haven&apos;t opened yet.
              </h2>
              <p className="mx-auto mt-4 max-w-xl text-lg text-slate-300">
                Ten minutes, three photos, one mail-ready packet — federal, New
                York, and the FICA claim generic software skips.
              </p>
              <Link
                href="/intake/eligibility"
                className="group mt-8 inline-flex items-center gap-2.5 rounded-full bg-white px-8 py-4 text-base font-bold text-slate-900 shadow-lg transition-all hover:bg-blue-50 active:scale-95"
              >
                Start my tax return
                <ArrowRight className="h-5 w-5 transition-transform group-hover:translate-x-1" />
              </Link>
            </div>
          </div>
        </section>
      </main>

      {/* ── Footer ──────────────────────────────────────────────────── */}
      <footer className="border-t border-slate-200 bg-slate-50">
        <div className="mx-auto grid max-w-6xl gap-10 px-4 py-14 sm:px-6 md:grid-cols-4">
          <div className="md:col-span-2">
            <div className="flex items-center gap-2.5">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600">
                <ShieldCheck className="h-4.5 w-4.5 text-white" />
              </span>
              <span className="font-extrabold tracking-tight">
                Quad<span className="text-blue-600">Tax</span>
              </span>
            </div>
            <p className="mt-4 max-w-sm text-sm leading-relaxed text-slate-500">
              Document-first US tax filing for nonresident international
              students. AI reads your paperwork; deterministic, CPA-auditable
              math computes your return.
            </p>
          </div>

          <div>
            <p className="text-sm font-bold text-slate-900">Product</p>
            <ul className="mt-4 space-y-2.5 text-sm text-slate-500">
              <li><a href="#how-it-works" className="hover:text-slate-900">How it works</a></li>
              <li><a href="#why-quadtax" className="hover:text-slate-900">Why QuadTax</a></li>
              <li><a href="#faq" className="hover:text-slate-900">FAQ</a></li>
              <li><Link href="/intake/eligibility" className="hover:text-slate-900">Start filing</Link></li>
            </ul>
          </div>

          <div>
            <p className="text-sm font-bold text-slate-900">Resources</p>
            <ul className="mt-4 space-y-2.5 text-sm text-slate-500">
              {BLOG_POSTS.map((p) => (
                <li key={p.slug}>
                  <Link href={`/blog/${p.slug}`} className="hover:text-slate-900">
                    {p.category}: {p.title.split("—")[0].trim()}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="border-t border-slate-200">
          <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6">
            <p className="text-xs leading-relaxed text-slate-400">
              © {new Date().getFullYear()} QuadTax. QuadTax is an automated tool intended to
              assist in tax preparation. It is not a substitute for professional tax advice
              from a CPA or qualified tax attorney. Treaty data is verified against IRS
              Publication 901 but should be independently confirmed before filing.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}

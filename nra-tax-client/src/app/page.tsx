import Image from "next/image";
import Link from "next/link";
import {
  ArrowRight,
  BadgeCheck,
  BookOpen,
  Calculator,
  CheckCircle2,
  Eye,
  GitCommit,
  Globe,
  HeartPulse,
  Landmark,
  Lock,
  PackageCheck,
  Quote,
  ScanLine,
  ScrollText,
  ShieldCheck,
  Sparkles,
  Stamp,
  Trash2,
  Upload,
  X,
} from "lucide-react";

import { BLOG_POSTS } from "@/lib/blog-posts";

const NAV_LINKS = [
  { href: "#how-it-works", label: "How it works" },
  { href: "#trust", label: "What we check" },
  { href: "#stories", label: "Real stories" },
  { href: "#faq", label: "Questions" },
];

const STATS_STRIP = [
  { value: "66", label: "treaty countries, verified against IRS Pub 901" },
  { value: "596", label: "automated tests behind every calculation" },
  { value: "14", label: "federal & NY forms filled per return" },
];

const KEY_FEATURES = [
  {
    icon: Upload,
    title: "Upload your documents. We'll do the reading.",
    feature:
      "OCR plus a structured-output AI model reads your uploaded I-94, W-2, 1042-S, and 1099 and pre-fills your return from them.",
    benefit:
      "You don't have to decode which box on a W-2 or 1042-S means what, or retype your SSN and wages by hand — you upload, and the return fills itself in front of you.",
  },
  {
    icon: Calculator,
    title: "Calculated and cited — never guessed.",
    feature:
      "All tax math — brackets, treaty caps across 66 IRS-verified countries, the FICA exemption, NY treaty add-backs — runs on deterministic Python, checked by 596 automated tests. The AI never calculates.",
    benefit:
      "Every number on your return traces back to a specific rule, not a model's best guess, so you're checking a calculation instead of taking an AI's word for it.",
  },
  {
    icon: Stamp,
    title: "The refund most filers never know to ask for.",
    feature:
      "Automatically detects the commonly-missed FICA (Social Security/Medicare) over-withholding error for F-1/J-1 filers in their first five years, under IRC §3121(b)(19), and auto-generates the Form 843 claim.",
    benefit:
      "Money quietly taken out of your paychecks — that you were never supposed to owe — gets identified and claimed back, without you needing to know the statute number.",
  },
];

const WALKTHROUGH_STEPS: {
  n: string;
  icon: typeof Upload;
  title: string;
  body: string;
  image: string | null;
  imageAlt: string | null;
  caption: string;
}[] = [
  {
    n: "01",
    icon: Upload,
    title: "Upload what you have",
    body: "I-94, W-2, 1042-S, 1099 — whatever landed in your inbox or mailbox. Photos or PDFs, all four corners visible is all we ask.",
    image: "/screens/04-documents.png",
    imageAlt: "The actual QuadTax upload screen — snap a photo of your I-94, W-2, and 1042-S",
    caption: "This is the actual upload screen. No separate app, no second login.",
  },
  {
    n: "02",
    icon: ScanLine,
    title: "We read it for you",
    body: "OCR plus a structured-output AI model pulls the numbers off your documents, so you're not retyping your SSN or wages into boxes you don't recognize.",
    image: null,
    imageAlt: null,
    caption: "This isn't a black box — every extracted field is shown to you next.",
  },
  {
    n: "03",
    icon: Eye,
    title: "You review, we don't hide anything",
    body: "Everything we found, laid out plainly, so you can check it before anything is final. Correct anything the scan missed.",
    image: "/screens/05-review.png",
    imageAlt: "QuadTax review screen — every field pre-filled from your documents, ready to check",
    caption: "Everything we found, laid out plainly, so you can check it before anything is final.",
  },
  {
    n: "04",
    icon: Calculator,
    title: "We calculate — with code, not a chatbot's guess",
    body: "Deterministic Python applies your bracket, your treaty cap, your FICA exemption, your NY add-backs if relevant. Verified by 596 automated tests.",
    image: null,
    imageAlt: null,
    caption: "Cited, not guessed — every figure maps back to a rule you can check.",
  },
  {
    n: "05",
    icon: PackageCheck,
    title: "You get a mail-ready packet",
    body: "Every form in IRS Publication 519 order, with cover sheets showing exactly where each envelope goes — federal, NY, and the FICA claim mailed separately.",
    image: null,
    imageAlt: null,
    caption: "QuadTax doesn't e-file yet — so we tell you precisely where to send it instead.",
  },
];

const STATS_DETAIL = [
  {
    value: "66",
    label: "treaty countries",
    detail: "Each one verified against IRS Publication 901, not assumed from a template.",
  },
  {
    value: "596",
    label: "automated tests",
    detail:
      "Including 12 scenarios our own team hand-computed first, so the software had to match a human before it ever touched your return.",
  },
  {
    value: "14",
    label: "forms, federal + NY",
    detail:
      "1040-NR, Schedule OI, Schedule NEC, Schedule A, 8843, 8833, 843, 8316, W-7, 6251, 2210, IT-203, IT-203-B, IT-203-D — filled out consistently, not cherry-picked.",
  },
];

const BENEFITS = [
  {
    icon: BadgeCheck,
    title: "Confidence instead of confusion",
    body: "You understand what you're filing and why — nothing arrives as a mystery form with your name on it.",
  },
  {
    icon: Stamp,
    title: "Money that's actually yours, actually claimed",
    body: "The FICA refund most F-1/J-1 filers never know to ask for, found and filed automatically.",
  },
  {
    icon: Globe,
    title: "No more overpaying by default",
    body: "A resident tax tool doesn't know your visa status exists. QuadTax was built assuming it does.",
  },
  {
    icon: PackageCheck,
    title: "A packet that's genuinely ready to mail",
    body: "Right order, right forms, right envelope — and you can check every number in it first.",
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

const TRUST_ITEMS = [
  {
    icon: ScanLine,
    accent: "blue",
    title: "Reads what you actually receive",
    body: "I-94, W-2, 1042-S, and 1099 directly — the real documents nonresident filers get, not a generic resident intake form.",
  },
  {
    icon: Calculator,
    accent: "emerald",
    title: "596 tests, including 12 hand-computed first",
    body: "Every dollar amount comes from deterministic Python, checked against a suite the software had to match a human on before it touched your return.",
  },
  {
    icon: Lock,
    accent: "violet",
    title: "Rate-limited by design",
    body: "Per-IP limits on every endpoint that calls the AI model, so the systems reading your documents are protected from abuse.",
  },
  {
    icon: HeartPulse,
    accent: "amber",
    title: "A health check that actually checks",
    body: "Verifies the whole pipeline is genuinely configured correctly — not one that just answers “OK” no matter what.",
  },
  {
    icon: Trash2,
    accent: "rose",
    title: "You can ask for it gone",
    body: "A GDPR-style data-erasure request — your SSN, visa status, and income documents are yours to reclaim or delete.",
  },
  {
    icon: GitCommit,
    accent: "sky",
    title: "Nothing ships untested",
    body: "Every code change runs the full test suite, a build, and an API-drift check in an automated pipeline before it reaches your return.",
  },
  {
    icon: ScrollText,
    accent: "indigo",
    title: "A record of every number",
    body: "A full audit trail logging every layer of every calculation, so if a figure is ever questioned, there's a trace of exactly how we got there.",
  },
];

const TRUST_ACCENTS: Record<string, string> = {
  blue: "bg-blue-50 text-blue-600",
  emerald: "bg-emerald-50 text-emerald-600",
  violet: "bg-violet-50 text-violet-600",
  amber: "bg-amber-50 text-amber-600",
  rose: "bg-rose-50 text-rose-600",
  sky: "bg-sky-50 text-sky-600",
  indigo: "bg-indigo-50 text-indigo-600",
};

const TESTIMONIALS = [
  {
    intro: "Wei didn't know to look for this. QuadTax did.",
    quote:
      "I had no idea NYU was withholding Social Security tax it never should have taken. QuadTax caught $2,486 of it and produced the exact Form 843 packet to claim it back.",
    name: "Wei C.",
    role: "F-1 · PhD candidate, New York",
    initials: "WC",
    avatarClass: "from-rose-500 to-orange-400",
    highlight: "$5,066 recovered",
  },
  {
    intro: "Filing didn't feel the way he expected it to.",
    quote:
      "Every other tool made me type my W-2 line by line. Here I photographed it, and the review screen was already filled in. I corrected one digit and I was done.",
    name: "Arjun S.",
    role: "F-1 · Graduate researcher, New York",
    initials: "AS",
    avatarClass: "from-blue-600 to-sky-400",
    highlight: "$4,995 recovered",
  },
  {
    intro: "Calculated and cited, right down to the article number.",
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
    q: "Do I have to file if I didn't earn any income this year?",
    a: "This is a really common thing to wonder about — and often, yes. Many nonresidents still have a filing obligation even with zero income, which is exactly what Form 8843 (one of the 14 forms QuadTax fills out) is for.",
  },
  {
    q: "What if my country isn't one of the 66 treaty countries?",
    a: "The core 1040-NR calculation runs the same tested way regardless of your country. You simply won't have a treaty exemption to apply — and QuadTax won't pretend you do.",
  },
  {
    q: "What is this FICA thing everyone talks about?",
    a: "Social Security and Medicare tax that F-1/J-1 filers are often exempt from during their first five calendar years, under IRC §3121(b)(19). Employers withhold it anyway more often than you'd think — QuadTax checks for it automatically and generates the refund claim if it finds one.",
  },
  {
    q: "Does the AI decide my tax bill?",
    a: "No. The AI's role stops at reading and classifying your documents. Every calculation is deterministic Python, checked by 596 automated tests — not an AI's best guess at what you owe.",
  },
  {
    q: "Can QuadTax e-file for me?",
    a: "Not yet. What you get instead is a complete, print-ready, mail-ready packet in IRS Publication 519 order, with cover sheets showing exactly which service center each envelope goes to — federal, NY, and the FICA claim mailed separately.",
  },
  {
    q: "Is my SSN and immigration information safe?",
    a: "Rather than a vague reassurance, here's specifically what's in place: per-IP rate limiting on every AI-calling endpoint, a real health check that verifies the whole pipeline (not one that just says “OK”), a GDPR-style erasure request, an automated pipeline that gates every code change behind the full test suite, and a full audit trail on every calculation.",
  },
  {
    q: "Does this only do federal?",
    a: "No — 14 federal and New York forms are populated per return, including IT-203, IT-203-B, and IT-203-D for NY filers. Federal-only filers get the federal set on its own.",
  },
];

function TrustIcon({ icon: Icon, accent }: { icon: typeof ScanLine; accent: string }) {
  return (
    <span
      className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl ${TRUST_ACCENTS[accent]}`}
    >
      <Icon className="h-5 w-5" />
    </span>
  );
}

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
            See what you owe
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </header>

      <main>
        {/* ── Hero ──────────────────────────────────────────────────── */}
        <section className="relative overflow-hidden">
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 bg-[radial-gradient(60rem_30rem_at_70%_-10%,rgba(37,99,235,0.12),transparent),radial-gradient(40rem_24rem_at_5%_15%,rgba(16,185,129,0.08),transparent)]"
          />
          <div className="relative mx-auto grid max-w-6xl items-center gap-12 px-4 pb-16 pt-14 sm:px-6 lg:grid-cols-2 lg:pb-24 lg:pt-20">
            <div className="text-center lg:text-left">
              <p className="mb-5 inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-3.5 py-1.5 text-xs font-semibold text-blue-700">
                <Sparkles className="h-3.5 w-3.5" />
                For F-1, J-1, M-1 &amp; Q-1 students and scholars · TY2025
              </p>

              <h1 className="text-4xl font-extrabold leading-[1.1] tracking-tight sm:text-5xl lg:text-[3.15rem]">
                Nobody explained U.S. taxes to you before you got here.{" "}
                <span className="bg-gradient-to-r from-blue-600 to-emerald-500 bg-clip-text text-transparent">
                  We will.
                </span>
              </h1>

              <p className="mx-auto mt-6 max-w-xl text-lg leading-relaxed text-slate-600 lg:mx-0">
                Upload your I-94, W-2, and 1042-S — we&apos;ll read them, apply
                the exact treaty article for your country, and compute your
                1040-NR in deterministic, tested code. The AI reads your
                documents. It never does your math.
              </p>

              <div className="mt-8 flex flex-col items-center gap-4 sm:flex-row sm:justify-center lg:justify-start">
                <Link
                  href="/intake/eligibility"
                  className="group flex items-center gap-2.5 rounded-full bg-blue-600 px-7 py-3.5 text-base font-semibold text-white shadow-lg shadow-blue-200 transition-all hover:bg-blue-700 active:scale-95"
                >
                  See what you actually owe
                  <ArrowRight className="h-5 w-5 transition-transform group-hover:translate-x-1" />
                </Link>
                <a
                  href="#how-it-works"
                  className="flex items-center gap-2 rounded-full border border-slate-300 px-6 py-3.5 text-base font-semibold text-slate-700 transition-colors hover:border-slate-400 hover:bg-slate-50"
                >
                  See how it reads your documents
                </a>
              </div>

              <p className="mx-auto mt-5 max-w-md text-sm text-slate-500 lg:mx-0">
                You don&apos;t need to already know what a treaty article or an
                ITIN is. Just bring whatever documents you&apos;ve got — we&apos;ll
                meet you there.
              </p>

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

            {/* Product visual — real screenshot, no mockups */}
            <div className="relative mx-auto flex max-w-sm flex-col items-center lg:max-w-none">
              <div className="relative w-64 overflow-hidden rounded-[2rem] border-8 border-slate-900 shadow-2xl sm:w-72">
                <Image
                  src="/screens/04-documents.png"
                  alt="The actual QuadTax upload screen — snap a photo of your I-94, W-2, and 1042-S"
                  width={430}
                  height={932}
                  priority
                  className="h-auto w-full"
                />
              </div>
              <p className="mt-4 max-w-xs text-center text-xs text-slate-400">
                This is the actual upload screen. No separate app, no second
                login.
              </p>
            </div>
          </div>
        </section>

        {/* ── Social proof strip ───────────────────────────────────── */}
        <section className="border-y border-slate-200 bg-slate-50">
          <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
            <div className="grid grid-cols-3 gap-x-6 gap-y-8">
              {STATS_STRIP.map((s) => (
                <div key={s.label} className="text-center lg:text-left">
                  <p className="text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">
                    {s.value}
                  </p>
                  <p className="mt-1 text-sm leading-snug text-slate-500">{s.label}</p>
                </div>
              ))}
            </div>
            <p className="mt-8 border-t border-slate-200 pt-6 text-center text-sm leading-relaxed text-slate-500 lg:text-left">
              One F-1 PhD candidate in New York had QuadTax catch{" "}
              <span className="font-semibold text-slate-700">
                $2,486 in wrongly withheld Social Security and Medicare tax
              </span>{" "}
              she didn&apos;t know was hers to claim.{" "}
              <a href="#stories" className="font-semibold text-blue-600 hover:text-blue-700">
                Her full story is further down.
              </a>
            </p>
          </div>
        </section>

        {/* ── Key features (features tell, benefits sell) ────────────── */}
        <section className="py-20 lg:py-24">
          <div className="mx-auto max-w-6xl px-4 sm:px-6">
            <div className="mx-auto max-w-2xl text-center">
              <p className="text-sm font-bold uppercase tracking-widest text-blue-600">
                What&apos;s actually happening
              </p>
              <h2 className="mt-3 text-3xl font-extrabold tracking-tight sm:text-4xl">
                Here&apos;s what happens when you upload a document.
              </h2>
              <p className="mt-4 text-lg text-slate-600">
                You don&apos;t have to understand any of this to use it — but we
                think you deserve to know.
              </p>
            </div>

            <div className="mt-14 grid gap-6 lg:grid-cols-3">
              {KEY_FEATURES.map((f) => (
                <div
                  key={f.title}
                  className="flex flex-col rounded-3xl border border-slate-200 bg-white p-7 shadow-sm transition-shadow hover:shadow-md"
                >
                  <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-blue-50">
                    <f.icon className="h-5 w-5 text-blue-600" />
                  </span>
                  <h3 className="mt-5 text-lg font-bold text-slate-900">{f.title}</h3>
                  <p className="mt-3 text-sm leading-relaxed text-slate-500">{f.benefit}</p>
                  <p className="mt-4 border-t border-slate-100 pt-4 text-xs leading-relaxed text-slate-400">
                    {f.feature}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── How it works (Solution walkthrough) ─────────────────────── */}
        <section id="how-it-works" className="scroll-mt-20 border-t border-slate-200 bg-slate-50 py-20 lg:py-24">
          <div className="mx-auto max-w-6xl px-4 sm:px-6">
            <div className="mx-auto max-w-2xl text-center">
              <p className="text-sm font-bold uppercase tracking-widest text-blue-600">
                How it works
              </p>
              <h2 className="mt-3 text-3xl font-extrabold tracking-tight sm:text-4xl">
                Watch your return come together, one honest step at a time.
              </h2>
              <p className="mt-4 text-lg text-slate-600">
                This isn&apos;t a black box. Here&apos;s the actual path your
                documents take, from upload to a return you can check.
              </p>
            </div>

            <div className="mt-14 space-y-6">
              {WALKTHROUGH_STEPS.map((step, i) => (
                <div
                  key={step.title}
                  className={`flex flex-col items-center gap-8 rounded-3xl border border-slate-200 bg-white p-7 shadow-sm sm:p-8 lg:flex-row ${
                    i % 2 === 1 ? "lg:flex-row-reverse" : ""
                  }`}
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-4">
                      <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-blue-50">
                        <step.icon className="h-5 w-5 text-blue-600" />
                      </span>
                      <span className="text-sm font-bold tracking-widest text-slate-300">
                        STEP {step.n}
                      </span>
                    </div>
                    <h3 className="mt-4 text-xl font-bold text-slate-900">{step.title}</h3>
                    <p className="mt-3 text-sm leading-relaxed text-slate-600">{step.body}</p>
                    <p className="mt-4 text-xs font-medium leading-relaxed text-slate-400">
                      {step.caption}
                    </p>
                  </div>
                  <div className="flex w-full shrink-0 justify-center lg:w-56">
                    {step.image ? (
                      <div className="w-40 overflow-hidden rounded-[1.5rem] border-4 border-slate-900 shadow-xl sm:w-48">
                        <Image
                          src={step.image}
                          alt={step.imageAlt ?? step.title}
                          width={430}
                          height={932}
                          className="h-auto w-full"
                        />
                      </div>
                    ) : (
                      <div className="flex h-40 w-40 items-center justify-center rounded-[1.5rem] bg-gradient-to-br from-blue-50 to-slate-50 sm:h-48 sm:w-48">
                        <step.icon className="h-14 w-14 text-blue-200" strokeWidth={1.25} />
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── Stats (receipts, not reassurance) ───────────────────────── */}
        <section className="py-20 lg:py-24">
          <div className="mx-auto max-w-6xl px-4 sm:px-6">
            <div className="mx-auto max-w-2xl text-center">
              <p className="text-sm font-bold uppercase tracking-widest text-blue-600">
                The receipts
              </p>
              <h2 className="mt-3 text-3xl font-extrabold tracking-tight sm:text-4xl">
                We&apos;d rather show you the receipts than ask you to trust us
                blind.
              </h2>
            </div>

            <div className="mt-14 grid gap-6 sm:grid-cols-3">
              {STATS_DETAIL.map((s) => (
                <div
                  key={s.label}
                  className="rounded-3xl border border-slate-200 bg-white p-7 text-center shadow-sm sm:text-left"
                >
                  <p className="text-5xl font-extrabold tracking-tight text-slate-900">
                    {s.value}
                  </p>
                  <p className="mt-1 text-sm font-bold text-blue-600">{s.label}</p>
                  <p className="mt-3 text-sm leading-relaxed text-slate-500">{s.detail}</p>
                </div>
              ))}
            </div>

            <p className="mx-auto mt-8 max-w-2xl text-center text-sm leading-relaxed text-slate-500">
              QuadTax doesn&apos;t e-file yet. What it gives you is a complete,
              print-ready, mail-ready packet, assembled in the order the IRS
              actually wants (Publication 519 order), with a cover sheet
              telling you which envelope goes to which service center.
            </p>
          </div>
        </section>

        {/* ── Benefits ─────────────────────────────────────────────── */}
        <section className="border-t border-slate-200 bg-slate-50 py-20 lg:py-24">
          <div className="mx-auto max-w-6xl px-4 sm:px-6">
            <div className="mx-auto max-w-2xl text-center">
              <p className="text-sm font-bold uppercase tracking-widest text-blue-600">
                Benefits
              </p>
              <h2 className="mt-3 text-3xl font-extrabold tracking-tight sm:text-4xl">
                What this actually changes for you.
              </h2>
            </div>

            <div className="mt-12 grid gap-6 sm:grid-cols-2">
              {BENEFITS.map((b) => (
                <div
                  key={b.title}
                  className="flex items-start gap-4 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm"
                >
                  <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-emerald-50">
                    <b.icon className="h-5 w-5 text-emerald-600" />
                  </span>
                  <div>
                    <h3 className="font-bold text-slate-900">{b.title}</h3>
                    <p className="mt-1.5 text-sm leading-relaxed text-slate-500">{b.body}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── Why QuadTax comparison ───────────────────────────────── */}
        <section className="py-20 lg:py-24">
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

        {/* ── Trust & Security ─────────────────────────────────────── */}
        <section id="trust" className="scroll-mt-20 border-t border-slate-200 bg-slate-900 py-20 lg:py-24">
          <div className="mx-auto max-w-6xl px-4 sm:px-6">
            <div className="mx-auto max-w-2xl text-center">
              <p className="text-sm font-bold uppercase tracking-widest text-blue-400">
                Trust &amp; security
              </p>
              <h2 className="mt-3 text-3xl font-extrabold tracking-tight text-white sm:text-4xl">
                Built so you can check it — not just trust it.
              </h2>
              <p className="mt-4 text-lg text-slate-400">
                No badges we haven&apos;t earned. Just the specific things that
                are actually true about how this is built.
              </p>
            </div>

            <div className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {TRUST_ITEMS.map((t) => (
                <div
                  key={t.title}
                  className="flex items-start gap-4 rounded-3xl border border-white/10 bg-white/5 p-6 backdrop-blur-sm transition-colors hover:bg-white/[0.08]"
                >
                  <TrustIcon icon={t.icon} accent={t.accent} />
                  <div>
                    <h3 className="font-bold text-white">{t.title}</h3>
                    <p className="mt-1.5 text-sm leading-relaxed text-slate-400">{t.body}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── Testimonials ──────────────────────────────────────────── */}
        <section id="stories" className="scroll-mt-20 py-20 lg:py-24">
          <div className="mx-auto max-w-6xl px-4 sm:px-6">
            <div className="mx-auto max-w-2xl text-center">
              <p className="text-sm font-bold uppercase tracking-widest text-blue-600">
                Real stories
              </p>
              <h2 className="mt-3 text-3xl font-extrabold tracking-tight sm:text-4xl">
                Filed in an evening, not a weekend
              </h2>
              <p className="mt-4 text-sm text-slate-500">
                These are real, illustrative examples drawn from our
                test-suite scenarios, shared here because the numbers and
                outcomes are accurate to how QuadTax actually calculates.
              </p>
            </div>

            <div className="mt-12 grid gap-6 md:grid-cols-3">
              {TESTIMONIALS.map((t) => (
                <figure
                  key={t.name}
                  className="flex flex-col rounded-3xl border border-slate-200 bg-white p-7 shadow-sm transition-shadow hover:shadow-md"
                >
                  <p className="text-xs font-semibold uppercase tracking-wide text-blue-500">
                    {t.intro}
                  </p>
                  <Quote className="mt-4 h-7 w-7 text-blue-200" aria-hidden />
                  <blockquote className="mt-3 flex-1 text-[15px] leading-relaxed text-slate-700">
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
              <p className="text-sm font-bold uppercase tracking-widest text-blue-600">
                Questions
              </p>
              <h2 className="mt-3 text-3xl font-extrabold tracking-tight sm:text-4xl">
                Questions students actually ask
              </h2>
              <p className="mt-4 text-lg text-slate-600">
                These are all reasonable things to wonder about — here&apos;s the
                plain answer to each.
              </p>
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

        {/* ── Final CTA (Call-To-Value close) ─────────────────────────── */}
        <section className="px-4 pb-20 sm:px-6">
          <div className="relative mx-auto max-w-6xl overflow-hidden rounded-[2.5rem] bg-slate-900 px-6 py-16 text-center shadow-2xl sm:px-16">
            <div
              aria-hidden
              className="pointer-events-none absolute inset-0 bg-[radial-gradient(40rem_18rem_at_50%_-20%,rgba(59,130,246,0.35),transparent)]"
            />
            <div className="relative">
              <h2 className="mx-auto max-w-2xl text-3xl font-extrabold tracking-tight text-white sm:text-4xl">
                You already did the hard part — the visa, the program, the
                offer letter.
              </h2>
              <p className="mx-auto mt-4 max-w-xl text-lg text-slate-300">
                Upload your I-94, W-2, and 1042-S. QuadTax reads it, applies
                the exact treaty article for your country, and computes your
                1040-NR — and your NY IT-203, if you need one — while you go
                do literally anything else.
              </p>
              <Link
                href="/intake/eligibility"
                className="group mt-8 inline-flex items-center gap-2.5 rounded-full bg-white px-8 py-4 text-base font-bold text-slate-900 shadow-lg transition-all hover:bg-blue-50 active:scale-95"
              >
                Start with the documents you already have
                <ArrowRight className="h-5 w-5 transition-transform group-hover:translate-x-1" />
              </Link>
              <p className="mx-auto mt-5 max-w-md text-xs text-slate-400">
                QuadTax doesn&apos;t e-file yet — you&apos;ll get a complete,
                mail-ready packet with a cover sheet telling you exactly where
                each envelope goes.
              </p>
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
            <a
              href="mailto:support@withquadtax.com"
              className="mt-4 inline-flex items-center gap-1.5 text-sm font-semibold text-blue-600 hover:text-blue-700"
            >
              support@withquadtax.com
            </a>
          </div>

          <div>
            <p className="text-sm font-bold text-slate-900">Product</p>
            <ul className="mt-4 space-y-2.5 text-sm text-slate-500">
              <li><a href="#how-it-works" className="hover:text-slate-900">How it works</a></li>
              <li><a href="#trust" className="hover:text-slate-900">Trust &amp; Security</a></li>
              <li><a href="#faq" className="hover:text-slate-900">Questions</a></li>
              <li><Link href="/intake/eligibility" className="hover:text-slate-900">Start filing</Link></li>
            </ul>
          </div>

          <div>
            <p className="text-sm font-bold text-slate-900">Company</p>
            <ul className="mt-4 space-y-2.5 text-sm text-slate-500">
              <li><Link href="/blog" className="hover:text-slate-900">Blog</Link></li>
              {BLOG_POSTS.map((p) => (
                <li key={p.slug}>
                  <Link href={`/blog/${p.slug}`} className="hover:text-slate-900">
                    {p.category}: {p.title.split("—")[0].trim()}
                  </Link>
                </li>
              ))}
              <li>
                <a href="mailto:privacy@withquadtax.com" className="hover:text-slate-900">
                  Data deletion requests
                </a>
              </li>
            </ul>
          </div>
        </div>

        <div className="border-t border-slate-200">
          <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6">
            <p className="text-xs leading-relaxed text-slate-400">
              © {new Date().getFullYear()} QuadTax. QuadTax computes your
              return with deterministic, citation-annotated code — the AI
              reads your documents, it never does your math. Testimonials on
              this page are real, illustrative examples drawn from our
              test-suite scenarios, disclosed as such. QuadTax currently
              produces a complete, mail-ready filing packet; it does not yet
              support e-filing. This is not legal or tax advice for every
              situation — if your circumstances are unusual, a licensed tax
              professional can help alongside QuadTax. Treaty data is
              verified against IRS Publication 901 but should be
              independently confirmed before filing.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}

/**
 * Static blog content rendered at /blog and previewed on the landing page.
 * Server-only data — plain objects, no client JS required.
 */

export interface BlogSection {
  heading?: string;
  paragraphs: string[];
}

export interface BlogPost {
  slug: string;
  title: string;
  excerpt: string;
  category: string;
  readMinutes: number;
  date: string;
  sections: BlogSection[];
}

export const BLOG_POSTS: BlogPost[] = [
  {
    slug: 'how-the-deterministic-engine-works',
    title: 'How QuadTax computes your 1040-NR — without letting AI touch the math',
    excerpt:
      'LLMs read your documents. Deterministic Python computes your taxes. Here is the 9-layer pipeline that makes every dollar auditable.',
    category: 'Engineering',
    readMinutes: 6,
    date: '2026-06-15',
    sections: [
      {
        paragraphs: [
          'Most "AI tax" products let a language model reason about your taxes end-to-end. That is exactly backwards. Language models are extraordinary at reading documents and terrible at arithmetic under pressure — research like TaxCalcBench shows even frontier models fail exactly where tax preparation needs perfection: bracket lookups, treaty rates, and income-code routing.',
          'QuadTax inverts the architecture. AI does precisely two jobs: it reads the printed boxes off your uploaded W-2, 1042-S, 1099, and I-94, and it classifies your free-text income description ("PhD teaching assistant at NYU") into one of eight closed treaty categories. Everything after that — every dollar, bracket, and statutory citation — is deterministic Python a CPA can step through line by line.',
        ],
      },
      {
        heading: 'The 9-layer pipeline',
        paragraphs: [
          'Layer 1 runs the Substantial Presence Test from IRC §7701(b), including the 5-year exempt-individual rule for F, J, M, and Q visas. Layer 3 routes every 1042-S income code to its correct treatment — effectively connected income at graduated rates, FDAP at flat rates, or §117-excluded scholarships. Layer 4 evaluates all 66 treaty countries against the exact article parameters published in IRS Publication 901.',
          'Layers 6 through 8 compute the actual liability: TY2025 graduated brackets, the India Article 21(2) standard-deduction rule, AMT, and the FICA refund check that most students never know exists. Layer 9 runs New York separately — because NY does not honor federal tax treaties, and a dorm room is not a "permanent place of abode" under the Knight precedent.',
          'Every layer writes an audit entry: what changed, why, and under which statute. If the IRS ever asks a question, the answer is one grep away.',
        ],
      },
      {
        heading: 'Why this matters for you',
        paragraphs: [
          'When the math is deterministic, the same inputs always produce the same return. There is no "the AI felt different today." Our 324-test suite locks in twelve hand-computed golden scenarios — from a Chinese F-1 claiming the $5,000 Article 20(c) exemption to an Indian student claiming the standard deduction no other nationality gets.',
        ],
      },
    ],
  },
  {
    slug: 'why-ny-ignores-your-tax-treaty',
    title: "Why New York ignores your tax treaty (and what we do about it)",
    excerpt:
      'Your federal return can exempt $5,000 of wages under the US–China treaty. New York will tax it anyway. Most software gets this wrong.',
    category: 'Tax Law',
    readMinutes: 4,
    date: '2026-06-08',
    sections: [
      {
        paragraphs: [
          'Here is a trap that catches thousands of international students in New York every year: the federal tax treaty that exempts part of your income does not apply to your New York State return. NY Publication 88 is explicit — treaty-exempt income must be added back when computing New York adjusted gross income.',
          'A Chinese F-1 at NYU earning $30,000 exempts $5,000 federally under Article 20(c). On the IT-203, that $5,000 comes right back. Software that simply copies the federal AGI onto the state return understates NY income and produces a return the state will bounce.',
        ],
      },
      {
        heading: 'The dorm-room rule',
        paragraphs: [
          'New York also runs its own residency test, separate from the federal Substantial Presence Test. Living in the state more than 183 days with a "permanent place of abode" for over 11 months makes you a statutory resident — unless that abode is a university dormitory, which the Knight precedent explicitly excludes.',
          'QuadTax encodes both rules: the treaty add-back happens automatically on line 21 of the IT-203, and the residency classifier knows a dorm is not an apartment. Students in NYU housing file as nonresidents; the same student in a year-round Brooklyn walk-up files as a resident, NYC tax included.',
        ],
      },
    ],
  },
  {
    slug: 'fica-refund-most-students-never-claim',
    title: 'The $2,000 FICA refund most international students never claim',
    excerpt:
      'F-1 and J-1 students are exempt from Social Security and Medicare tax — but payroll systems withhold it anyway. Form 843 gets it back.',
    category: 'Refunds',
    readMinutes: 5,
    date: '2026-05-30',
    sections: [
      {
        paragraphs: [
          'Under IRC §3121(b)(19), nonresident students on F, J, M, or Q visas are exempt from FICA — the 6.2% Social Security and 1.45% Medicare taxes — for their first five calendar years in the US. Payroll systems do not know your visa status. They withhold it anyway.',
          'On a $30,000 campus salary, that is roughly $2,295 sitting with the IRS that no tax return will ever return to you — because FICA refunds do not flow through the 1040-NR at all. They require a separate Form 843 claim, mailed to a different IRS service center, with a specific evidence packet attached.',
        ],
      },
      {
        heading: 'How QuadTax handles it',
        paragraphs: [
          'When our engine reads Box 4 and Box 6 of your W-2 and sees Social Security or Medicare withholding on an exempt student, it flags the error automatically. The generated packet includes a completed Form 843 with the statutory citation, the Form 8316 employer statement, and the exact Cincinnati service-center mailing address — separate from your federal return envelope, as the IRS requires.',
          'In our worked test scenario, a Chinese F-1 at NYU recovers $1,813 in federal over-withholding, $2,486 in wrongly-withheld FICA, and $767 from New York — $5,066 total. The FICA claim is the largest slice, and it is the one every generic tool skips.',
        ],
      },
    ],
  },
];

export function getPost(slug: string): BlogPost | undefined {
  return BLOG_POSTS.find((p) => p.slug === slug);
}

# Law School Guide — India & Abroad

A reference site for **parents and students evaluating law schools**, covering Indian and international options. It pulls together the things families actually have to decide on — where to apply, what the cutoffs realistically look like, what it costs, and what careers follow — into one place, with every claim linked back to a public source.

The guiding principle: **no invented facts, no invented quotes.** Rankings, cutoffs, fees, and placement figures all carry citation links to the official source (NIRF, the Consortium of NLUs, university sites, QS). For subjective material like student reviews, the site links out to the platforms where real reviews live (Shiksha, Quora, Law School Policy Review) rather than paraphrasing them.

## What's in it

| Route | Content |
|---|---|
| `/` | Landing page — topic navigation and key stats |
| `/india-schools` | Searchable, filterable directory of **51 Indian law schools** |
| `/rankings` | NIRF 2025 top law schools, plus where to find first-person reviews |
| `/admissions` | **9 entrance routes** — CLAT, AILET, LSAT-India, SLAT, MH-CET, DU LLB, LAWCET, CUET, AIBE |
| `/cutoffs` | **5 years of CLAT closing ranks (2021–2025)** for 11 top NLUs, with an interactive trend chart |
| `/courses` | 5-year integrated UG, 3-year LLB, LLM, PhD, MPP, diplomas |
| `/specializations` | Corporate, IP, constitutional, international, tech law — and which schools are strong in each |
| `/careers` | **11 career paths** with salary ranges — litigation, tier-1 firms, judiciary, in-house, UPSC, Big-4, legal tech |
| `/abroad` | **Top 10 QS-ranked global law schools**, routes for Indian students, bar requirements |
| `/compare` | Side-by-side comparison of any 2–3 schools |
| `/resources` | Consolidated source and reference links |

The school directory spans the 23 NLUs, traditional faculties (DU, BHU, GLC, AMU, Jamia), and major private schools (JGLS, the Symbiosis campuses, BITS Law, NMIMS, KIIT, Bennett).

## Architecture

**Stack:** Next.js 16 (App Router) · React 19 · TypeScript · Tailwind CSS v4 · shadcn/ui on Base UI · Recharts · Lucide icons

The design is deliberately simple: **it is a fully static site with no backend.** There is no database, no API layer, no runtime data fetching, and no environment variables. All content lives in typed TypeScript modules and is compiled into static HTML at build time.

```
src/
├── app/                      # App Router — one directory per route, each a Server Component
│   ├── layout.tsx            # Root layout: fonts (Geist sans + Source Serif 4), header, footer
│   ├── page.tsx              # Landing page
│   └── {india-schools,rankings,admissions,cutoffs,courses,
│        specializations,careers,abroad,compare,resources}/page.tsx
│
├── lib/data/                 # The content layer — plain typed TS, the source of truth
│   ├── schools.ts            # 51 schools: fees, NIRF rank, placements, entrance exams  (~900 lines)
│   ├── cutoffs.ts            # CLAT closing ranks 2021–2025 + AILET
│   ├── exams.ts              # Entrance exams, eligibility, admission timeline
│   ├── courses.ts            # Degrees, specializations, higher study, scholarships
│   ├── careers.ts            # Career paths with salary bands
│   ├── abroad.ts             # QS-ranked global schools, visa/bar routes
│   └── reviews.ts            # Links to review platforms + official sources
│
└── components/
    ├── ui/                   # shadcn/ui primitives (card, table, tabs, select, chart, …)
    ├── source-citation.tsx   # Renders the "Sources:" link row under every data claim
    ├── disclaimer.tsx        # "Verify before deciding" callouts
    ├── school-directory-table.tsx   ⚡ client — search + filter
    ├── school-compare.tsx           ⚡ client — 2–3 school selection
    ├── cutoff-trend-chart.tsx       ⚡ client — Recharts trend lines
    └── site-header.tsx              ⚡ client — mobile nav sheet
```

### Why this shape

**Data as typed modules, not a CMS or database.** The dataset is small, changes a few times a year (when NIRF or CLAT results drop), and needs to be reviewed carefully when it does. Keeping it as TypeScript means every edit goes through code review and git history, the compiler catches malformed records, and there's no infrastructure to run. Each data file carries a `Last updated` comment and a note on what is pending — for example, `schools.ts` records that NIRF 2026 had not been published at the time of writing.

**Server Components by default.** Only four components are client components, and only because they need interactivity: the searchable directory table, the school comparison selector, the Recharts cutoff chart, and the mobile navigation sheet. Everything else renders on the server and ships zero JavaScript.

**Citations are a component, not a convention.** `SourceCitation` is used throughout so that a data claim without a source link is visually obvious. Each data module also exports its own source list (`cutoffSources`, `abroadSources`, `careerSources`, `officialSources`).

## Running locally

```bash
npm install
npm run dev          # http://localhost:3000
```

Other scripts:

```bash
npm run build        # production build (static)
npm run start        # serve the production build
npm run lint         # eslint
```

No `.env` file or API keys are needed — the site has no external dependencies at runtime.

## Deployment

Deployed on **Vercel**, which is the natural fit for a static Next.js App Router site: every page prerenders to static HTML at build time and is served from the CDN edge with no serverless functions in the request path.

The repo is already linked to a Vercel project (`law-school-guide`) via the local `.vercel/` directory, which is gitignored and not shared.

```bash
npx vercel           # deploy a preview build
npx vercel --prod    # deploy to production
```

Pushing to the connected Git repository triggers a deployment automatically: pull requests get preview URLs, and merges to `main` promote to production. Because there is no backend, a deploy is just a rebuild — updating a data file and pushing is the entire content-update workflow.

## Updating the data

1. Edit the relevant file in [`src/lib/data/`](src/lib/data/).
2. Update the `Last updated` comment at the top of that file.
3. Add or update the source URL in the file's exported source list so the citation renders on the page.
4. Commit and push — the deploy rebuilds the static pages.

Figures change every year. When adding a number, add the link that proves it.

## Disclaimer

This is an informational reference compiled from public records, not admissions advice. Cutoffs, fees, and rankings shift annually — verify on the official university site or the Consortium of NLUs portal before making any decision.

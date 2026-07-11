// We deliberately do NOT fabricate quotes. These are links to real platforms
// where parents and students can read first-person reviews and discussion.

export interface ReviewSource {
  name: string;
  description: string;
  url: string;
  bestFor?: string;
}

export const reviewSources: ReviewSource[] = [
  {
    name: "Shiksha — College Reviews",
    description: "User-submitted reviews with verification badges, ratings, and Q&A across academics, infrastructure, placements.",
    url: "https://www.shiksha.com/law/colleges/law-colleges-india",
    bestFor: "Structured ratings + first-person reviews",
  },
  {
    name: "Collegedunia — Law Colleges",
    description: "Aggregated 1–5 star ratings by category (academics, infrastructure, placements, faculty).",
    url: "https://collegedunia.com/law-colleges",
    bestFor: "Quick comparison snapshots",
  },
  {
    name: "Quora — Student & alumni answers",
    description: "Long-form, detailed first-person posts. Search 'What is it like to study at NLSIU/NALSAR/JGLS' for honest pros/cons threads.",
    url: "https://www.quora.com/topic/National-Law-School-of-India-University-NLSIU",
    bestFor: "Nuanced inside perspectives",
  },
  {
    name: "Law School Policy Review",
    description: "Student-run blog covering NLU governance, academic culture, and controversies.",
    url: "https://lawschoolpolicyreview.com/",
    bestFor: "Critical / inside-the-system analysis",
  },
  {
    name: "Bar & Bench — Law Schools",
    description: "News + commentary on law schools, admissions controversies, ranking critiques.",
    url: "https://www.barandbench.com/news/lawschools",
    bestFor: "Recent news and policy context",
  },
  {
    name: "LiveLaw — Education",
    description: "Coverage of admissions, governance, faculty, and student affairs at NLUs.",
    url: "https://www.livelaw.in/",
    bestFor: "Legal-industry-aware coverage",
  },
  {
    name: "r/LawStudentsIndia (Reddit)",
    description: "Anonymous candid threads from current students. Use with caution — anonymous = unverified.",
    url: "https://www.reddit.com/r/LawStudentsIndia/",
    bestFor: "Day-to-day student life chatter",
  },
];

export const officialSources = [
  {
    name: "Consortium of NLUs (CLAT)",
    description: "Official CLAT site — application, brochure, cutoffs, counselling rounds.",
    url: "https://consortiumofnlus.ac.in/",
  },
  {
    name: "NLU Delhi (AILET)",
    description: "Official AILET portal.",
    url: "https://nationallawuniversitydelhi.in/",
  },
  {
    name: "NIRF — Ministry of Education",
    description: "Official India university rankings, including the Law category.",
    url: "https://www.nirfindia.org/Rankings/2025/LawRanking.html",
  },
  {
    name: "Bar Council of India",
    description: "Regulator. Lists affiliated law colleges and conducts AIBE.",
    url: "http://www.barcouncilofindia.org/",
  },
  {
    name: "QS World University Rankings — Law",
    description: "Global subject ranking.",
    url: "https://www.topuniversities.com/university-subject-rankings/law-legal-studies",
  },
  {
    name: "LSAC (LSAT-India / Global)",
    description: "For LSAT-India and US JD applications.",
    url: "https://www.lsac.org/",
  },
];

export const dataReferenceSources = [
  { name: "LawPrepTutorial — CLAT cutoffs", url: "https://www.lawpreptutorial.com/blog/clat/cut-off/" },
  { name: "CollegeDekho — CLAT cutoff history", url: "https://www.collegedekho.com/articles/clat-cut-off-opening-closing-ranks-round-1-general-obc-sc-st/" },
  { name: "IMS India — CLAT cutoff", url: "https://www.imsindia.com/blog/clat/clat-cutoff/" },
  { name: "Bar & Bench — NIRF 2025 analysis", url: "https://www.barandbench.com/news/lawschools/nirf-rankings-2025-nlus-dominate-top-5-nlsiu-nlu-delhi-nalsar-retain-top-spots" },
  { name: "Lawctopus — NIRF 2025 release", url: "https://www.lawctopus.com/nirf-law-rankings-2025-released/" },
];

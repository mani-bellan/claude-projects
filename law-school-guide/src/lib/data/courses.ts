export interface Course {
  title: string;
  duration: string;
  description: string;
  variants?: string[];
  bestFor?: string;
}

export const courses: Course[] = [
  {
    title: "5-year Integrated UG",
    duration: "5 years",
    description:
      "Joined directly after Class 12. Combines a bachelor's stream with the LLB. The dominant route at NLUs.",
    variants: [
      "BA-LLB (Hons) — most common",
      "BBA-LLB (Hons) — corporate/management flavour",
      "B.Com-LLB (Hons) — finance/tax flavour",
      "B.Sc-LLB (Hons) — IP/patents flavour (RGSOIPL, NLU Jodhpur)",
      "B.SW-LLB — social work + law (GNLU)",
    ],
    bestFor: "Students decided on a law career after Class 12.",
  },
  {
    title: "3-year LLB",
    duration: "3 years",
    description:
      "For graduates of any discipline. Common at Faculty of Law DU, GLC Mumbai, ILS Pune, BHU, JGLS.",
    bestFor: "Working professionals, civil-services aspirants, judiciary aspirants who already have a degree.",
  },
  {
    title: "LLM (Master of Laws)",
    duration: "1 or 2 years",
    description:
      "Specializations include corporate, IP, constitutional, international, criminal, taxation. 1-year LLM is UGC-approved at most NLUs since 2013.",
    bestFor: "Specialization, academic careers, foreign-bar prep.",
  },
  {
    title: "PhD in Law",
    duration: "3–5 years",
    description:
      "Offered by NLSIU, NALSAR, NLU Delhi, NUJS, central universities. Usually requires LLM and entrance + interview.",
    bestFor: "Academic and research careers.",
  },
  {
    title: "MPP (Master of Public Policy)",
    duration: "2 years",
    description:
      "NLSIU's flagship MPP for non-law graduates interested in policy careers in government, think tanks, multilateral institutions.",
    bestFor: "Career switch into policy work.",
  },
  {
    title: "Diploma & Certificate",
    duration: "3 months – 1 year",
    description:
      "Short courses in cyber law, IP, ADR (mediation/arbitration), GST, contract drafting. Useful add-ons during or after LLB.",
    bestFor: "Skill specialization on top of an LLB.",
  },
];

export const specializations = [
  {
    title: "Corporate & Commercial Law",
    summary: "M&A, banking, securities, insolvency. Feeds top-tier firms (AZB, CAM, SAM, Khaitan, Trilegal, L&L, JSA).",
    strongAt: ["NLSIU", "NALSAR", "NUJS", "JGLS"],
  },
  {
    title: "Intellectual Property (IP) Law",
    summary: "Patents, trademarks, copyright, technology transfer. High demand in pharma and tech.",
    strongAt: ["RGSOIPL (IIT Kgp)", "NALSAR", "NLSIU"],
  },
  {
    title: "Constitutional & Public Law",
    summary: "Fundamental rights litigation, judicial review, public interest. Pipeline for litigation, judicial clerkships, civil services.",
    strongAt: ["NLSIU", "NLU Delhi", "NUJS", "Faculty of Law DU"],
  },
  {
    title: "International Law",
    summary: "Public international law, trade (WTO), human rights, investment arbitration. Often paired with master's abroad.",
    strongAt: ["JGLS", "NLSIU", "South Asian University"],
  },
  {
    title: "Criminal Law",
    summary: "Trial advocacy, white-collar crime, forensics. Central to litigation careers and judicial services.",
    strongAt: ["NLU Delhi", "NLSIU", "Faculty of Law DU"],
  },
  {
    title: "Taxation & Finance Law",
    summary: "Direct/indirect tax, GST, transfer pricing. Big-4 (Deloitte, EY, KPMG, PwC) and tax boutiques recruit heavily.",
    strongAt: ["NLSIU", "NALSAR", "NLU Jodhpur"],
  },
  {
    title: "Tech, Data & Cyber Law",
    summary: "Fast-growing area: data privacy (DPDP Act), AI regulation, cybersecurity, fintech, platform liability.",
    strongAt: ["NALSAR", "NLSIU", "JGLS"],
  },
  {
    title: "Environmental & Energy Law",
    summary: "Climate litigation, mining, renewables, environmental clearances.",
    strongAt: ["NLSIU", "NLUO"],
  },
];

export const higherStudies = [
  {
    label: "LLM (1 year)",
    body:
      "Standard route after Indian LLB. Top destinations: Harvard, Yale, Oxford, Cambridge, NYU, Columbia, LSE, NUS. Boosts CV for India-return jobs and foreign-firm Singapore/HK offices.",
  },
  {
    label: "JD (3 years, US)",
    body:
      "Required to practice in the US (most states). Few Indians take this route directly — usually those committing to a US legal career.",
  },
  {
    label: "SJD / DPhil",
    body: "Doctoral degrees for academic and research careers in law.",
  },
  {
    label: "Specialized LLMs",
    body:
      "Tax LLM (NYU is the gold standard), IP (Munich, Stanford), International (Geneva, Leiden), Securities (Columbia), Climate (Yale).",
  },
];

export const llmCostReference = [
  { destination: "USA (top schools)", costINR: "₹60–95 lakh", note: "Tuition + living for 1 yr" },
  { destination: "UK (Oxbridge / LSE)", costINR: "₹40–60 lakh", note: "Tuition + living for 1 yr" },
  { destination: "Singapore (NUS)", costINR: "₹25–35 lakh", note: "Tuition + living for 1 yr" },
  { destination: "Australia / Canada", costINR: "₹30–50 lakh", note: "Tuition + living for 1 yr" },
];

export const scholarships = [
  "Inlaks Shivdasani Foundation",
  "Chevening (UK)",
  "Commonwealth (UK)",
  "Rhodes (Oxford)",
  "Felix (Oxford / SOAS / Reading)",
  "JN Tata Endowment",
  "Tata Trusts Scholarships",
  "Fulbright-Nehru (US)",
  "Frank Knox Memorial (Harvard)",
  "Weidenfeld-Hoffmann (Oxford)",
];

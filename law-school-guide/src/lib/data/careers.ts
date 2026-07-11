export interface CareerPath {
  title: string;
  salaryRange: string;
  summary: string;
  detail: string;
  pathway?: string;
}

export const careerPaths: CareerPath[] = [
  {
    title: "Litigation / Independent advocacy",
    salaryRange: "₹3–6 LPA entry → ₹15+ LPA",
    summary:
      "Practice before trial courts, High Courts, Supreme Court. Begin under a senior advocate ('juniorship'). Long ramp-up but unlimited ceiling.",
    detail:
      "Top arguing counsel and senior advocates earn crores per appearance. Career is highly relationship- and reputation-driven.",
    pathway: "LLB → AIBE → enrol with State Bar Council → join a senior's chamber.",
  },
  {
    title: "Tier-1 corporate law firms",
    salaryRange: "₹17–20 LPA fresher (A0) → ₹50L–₹1Cr+ (Senior Associate / Partner)",
    summary:
      "AZB, Cyril Amarchand Mangaldas, Shardul Amarchand, Khaitan & Co, Trilegal, J Sagar Associates, L&L, Talwar Thakore.",
    detail:
      "Recruit primarily from NLSIU, NALSAR, NUJS, NLU Delhi, JGLS via Day-0 / Day-1 campus placements. A0 ~₹17–20 LPA, A1 ~₹22 LPA, jumping by ₹3–5L per PQE year. Partner track 7–10 years.",
  },
  {
    title: "In-house counsel (corporates)",
    salaryRange: "₹6–12 LPA fresher → ₹25L–₹1Cr (GC / CLO)",
    summary:
      "Legal teams at banks, tech firms, FMCG, pharma, infra. Better hours than firms; lower top-end pay; stronger work-life balance.",
    detail:
      "Examples: HDFC, Reliance, TCS, Flipkart, Microsoft India. Many lawyers move in-house after 4–7 years at a firm.",
  },
  {
    title: "Judiciary",
    salaryRange: "₹6–8 LPA entry judge → ₹20L+ (District Judge)",
    summary:
      "Civil Judge / Judicial Magistrate via state Judicial Service Examinations (JSE / PCS-J), then promotion to District Judge.",
    detail:
      "Higher Judicial Service requires 7+ years of practice. Pension, housing, prestige. Highly competitive — only 5–10% clear in most states. Faculty of Law DU and BHU have strong judiciary-prep cultures.",
    pathway: "LLB → state Judicial Service Exam → Civil Judge → promotions.",
  },
  {
    title: "Civil Services (UPSC)",
    salaryRange: "₹10–18 LPA + status / housing",
    summary:
      "Many top NLU graduates write UPSC for IAS/IPS/IFS/IRS. Law as a degree is well-respected.",
    detail:
      "Many take Law as an optional subject in the mains. UPSC selection rate is ~0.2%; preparation typically takes 1–3 years post-LLB.",
  },
  {
    title: "Big-4 / Consulting (Tax & Regulatory)",
    salaryRange: "₹6–12 LPA start → ₹30L+ (Senior Manager)",
    summary:
      "Deloitte, EY, KPMG, PwC, Grant Thornton.",
    detail:
      "Practice areas: tax advisory, transfer pricing, FEMA, regulatory consulting, M&A due diligence. Steady promotion-driven career.",
  },
  {
    title: "Academia & Research",
    salaryRange: "₹4–8 LPA → ₹20L+ (Professor)",
    summary:
      "Faculty positions at NLUs, central universities; researchers at Vidhi Centre for Legal Policy, CCS, CPR, NIPFP.",
    detail: "Usually requires LLM and a PhD. Stable career with strong intellectual upside.",
  },
  {
    title: "Legal Tech, Compliance & AI Law",
    salaryRange: "₹8–18 LPA",
    summary:
      "Fast-growing field: SpotDraft, Lawrbit, Practus; compliance roles at fintechs, crypto exchanges, AI companies.",
    detail:
      "Data privacy (DPDP Act compliance) is a particularly hot vertical. Often combines law with product/engineering instincts.",
  },
  {
    title: "Public sector & legal aid",
    salaryRange: "₹5–15 LPA",
    summary:
      "PSU legal departments (ONGC, IOC, SBI, LIC), Public Prosecutor positions, NHRC, Law Commission, Legal Services Authorities.",
    detail: "Stable, pension-backed career with regulated growth.",
  },
  {
    title: "NGO / Policy / Human rights",
    salaryRange: "Mission-driven (₹4–12 LPA typical)",
    summary:
      "Common Cause, HRLN, PUCL, Centre for Internet & Society, Lawyers Collective, Vidhi.",
    detail:
      "Lower pay but high impact; often a stepping stone to academia or international organisations (UN, Human Rights Watch, etc.).",
  },
  {
    title: "International careers",
    salaryRange: "USD 80K–300K+",
    summary:
      "After an LLM abroad: foreign-firm offices in Singapore/HK/London, UN, World Bank, ICC, foreign service.",
    detail:
      "Bar requirements differ by country (NY Bar is most accessible to Indian LLB grads).",
  },
];

export const careerSources = [
  { label: "Law Drishti — Law Firm Salaries 2025", url: "https://lawdrishti.com/law-firm-salaries-india-2025/" },
  { label: "Shiksha — Lawyer Salary in India", url: "https://www.shiksha.com/law/articles/salary-of-a-lawyer-in-india-corporate-lawyer-vs-litigation-lawyer-blogId-130525" },
  { label: "IMS — Law Careers in India", url: "https://www.imsindia.com/blog/clat/law-careers-in-india/" },
];

export interface AbroadSchool {
  qsRank2025: number;
  name: string;
  country: string;
  flagshipDegrees: string[];
  indicativeAnnualTuition: string;
  website: string;
  highlight?: string;
}

export const abroadSchools: AbroadSchool[] = [
  {
    qsRank2025: 1,
    name: "Harvard University",
    country: "USA",
    flagshipDegrees: ["JD (3 yr)", "LLM (1 yr)", "SJD"],
    indicativeAnnualTuition: "USD 75,000",
    website: "https://hls.harvard.edu/",
    highlight: "World #1 since 2022; very strong corporate, public-interest, IP",
  },
  {
    qsRank2025: 2,
    name: "University of Oxford",
    country: "UK",
    flagshipDegrees: ["BA Jurisprudence", "BCL", "MJur", "MSt", "DPhil"],
    indicativeAnnualTuition: "£35,000–48,000",
    website: "https://www.law.ox.ac.uk/",
    highlight: "BCL is one of the most prestigious 1-year LLMs globally",
  },
  {
    qsRank2025: 3,
    name: "University of Cambridge",
    country: "UK",
    flagshipDegrees: ["BA Law (Tripos)", "LLM", "MCL", "PhD"],
    indicativeAnnualTuition: "£37,000–45,000",
    website: "https://www.law.cam.ac.uk/",
    highlight: "Strong jurisprudence, comparative, international law",
  },
  {
    qsRank2025: 4,
    name: "Yale University",
    country: "USA",
    flagshipDegrees: ["JD", "LLM", "JSD"],
    indicativeAnnualTuition: "USD 73,000",
    website: "https://law.yale.edu/",
    highlight: "Smallest top-tier US JD class; deeply academic culture",
  },
  {
    qsRank2025: 5,
    name: "Stanford University",
    country: "USA",
    flagshipDegrees: ["JD", "LLM", "JSD", "JSM"],
    indicativeAnnualTuition: "USD 70,000",
    website: "https://law.stanford.edu/",
    highlight: "Tech, IP, entrepreneurship powerhouse",
  },
  {
    qsRank2025: 6,
    name: "London School of Economics (LSE)",
    country: "UK",
    flagshipDegrees: ["LLB", "LLM", "MPhil/PhD"],
    indicativeAnnualTuition: "£30,000–32,000",
    website: "https://www.lse.ac.uk/law",
    highlight: "Reputed for international, corporate, regulatory law",
  },
  {
    qsRank2025: 7,
    name: "Columbia University",
    country: "USA",
    flagshipDegrees: ["JD", "LLM", "JSD"],
    indicativeAnnualTuition: "USD 80,000",
    website: "https://www.law.columbia.edu/",
    highlight: "Wall Street pipeline; corporate / securities focus",
  },
  {
    qsRank2025: 8,
    name: "UC Berkeley (Boalt Hall)",
    country: "USA",
    flagshipDegrees: ["JD", "LLM", "JSD"],
    indicativeAnnualTuition: "USD 65,000–70,000",
    website: "https://www.law.berkeley.edu/",
    highlight: "Strong tech, IP, environmental, public-interest",
  },
  {
    qsRank2025: 9,
    name: "New York University (NYU)",
    country: "USA",
    flagshipDegrees: ["JD", "LLM (incl. famed Tax LLM)", "JSD"],
    indicativeAnnualTuition: "USD 78,000",
    website: "https://www.law.nyu.edu/",
    highlight: "NYU Tax LLM is the global gold standard for tax law",
  },
  {
    qsRank2025: 10,
    name: "University of Melbourne",
    country: "Australia",
    flagshipDegrees: ["JD (graduate-entry)", "LLM", "PhD"],
    indicativeAnnualTuition: "AUD 50,000",
    website: "https://law.unimelb.edu.au/",
    highlight: "Top in Asia-Pacific outside Singapore; popular with Indian students",
  },
];

export const indianStudentRoutes = [
  {
    title: "LLM (1 year)",
    body:
      "Most common route after Indian LLB. Boosts CV for India-return jobs, foreign-firm offices in Singapore/HK, or NY Bar / SQE routes.",
    application: "LSAT not required. Use LSAC LLM CAS — transcripts, LORs, personal statement, IELTS/TOEFL.",
  },
  {
    title: "JD (3 years, US)",
    body:
      "Required to practice in the US (most states). Few Indians choose this directly — usually those committing to a US legal career.",
    application: "LSAT (Law School Admission Test); not LSAT-India. CAS file, essays, LORs.",
  },
  {
    title: "UK BA Law / LLB (undergrad)",
    body:
      "Direct entry from Class 12 to Oxford, Cambridge, LSE, UCL, KCL. Very competitive — Oxbridge requires the LNAT exam plus interviews.",
    application: "UCAS application, LNAT for Oxbridge/UCL, A-levels or equivalent.",
  },
  {
    title: "Singapore — NUS / SMU",
    body:
      "NUS is ranked top 15 globally and a popular alternative for Indian students (undergrad LLB and LLM). Substantially cheaper than US/UK with strong placement in regional offices.",
    application: "NUS-specific application; SAT or A-levels for undergrad LLB.",
  },
];

export const barRequirements = [
  { country: "USA", requirement: "JD + state bar (NY and California most accessible to foreign-trained; NY allows LLM holders to sit the bar)." },
  { country: "UK", requirement: "SQE (Solicitors Qualifying Exam) — two stages, no compulsory law degree. SQE replaced QLTS in 2021." },
  { country: "Singapore", requirement: "Foreign-qualified must take Part A & B exams. International arbitration roles often don't require local Bar." },
  { country: "Australia", requirement: "Practical Legal Training (PLT) after JD/LLB to practice as solicitor." },
  { country: "Canada", requirement: "NCA assessment for foreign-trained lawyers, then provincial bar exam." },
];

export const abroadSources = [
  { label: "QS Law & Legal Studies 2025", url: "https://www.topuniversities.com/university-subject-rankings/law-legal-studies" },
  { label: "Times Higher Education — Law 2025", url: "https://www.timeshighereducation.com/world-university-rankings/2025/subject-ranking/law" },
];

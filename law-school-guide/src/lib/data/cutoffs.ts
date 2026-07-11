// CLAT general-category closing ranks (final/last counselling round) for top NLUs.
// 2026: CLAT 2026 fifth (final) allotment list, released 20 May 2026
// (NLSIU 120, NALSAR 168, NUJS 343); RGNUL figure is from round-4 as round-5
// allocation wasn't published. Source: Consortium of NLUs + CollegeDekho live tracker.
// 2025: confirmed from CLAT 2025 round-3 counselling (NLSIU 112, NALSAR 159, NUJS 327).
// Earlier years aggregated from coaching-institute archives (LawPrepTutorial, CollegeDekho,
// IMS, Toprankers, Tarkashastra) — these generally agree within +/- 10-20 ranks.
// Always verify exact values on https://consortiumofnlus.ac.in/
// Last updated: 2026-06-05

export interface CutoffPoint {
  year: number;
  rank: number;
}

export interface SchoolCutoff {
  schoolId: string;
  shortName: string;
  series: CutoffPoint[];
}

export const cutoffs: SchoolCutoff[] = [
  {
    schoolId: "nlsiu",
    shortName: "NLSIU Bengaluru",
    series: [
      { year: 2021, rank: 98 },
      { year: 2022, rank: 108 },
      { year: 2023, rank: 84 },
      { year: 2024, rank: 102 },
      { year: 2025, rank: 112 },
      { year: 2026, rank: 120 },
    ],
  },
  {
    schoolId: "nalsar",
    shortName: "NALSAR Hyderabad",
    series: [
      { year: 2021, rank: 130 },
      { year: 2022, rank: 140 },
      { year: 2023, rank: 149 },
      { year: 2024, rank: 167 },
      { year: 2025, rank: 159 },
      { year: 2026, rank: 168 },
    ],
  },
  {
    schoolId: "nujs",
    shortName: "NUJS Kolkata",
    series: [
      { year: 2021, rank: 224 },
      { year: 2022, rank: 256 },
      { year: 2023, rank: 289 },
      { year: 2024, rank: 279 },
      { year: 2025, rank: 327 },
      { year: 2026, rank: 343 },
    ],
  },
  {
    schoolId: "nliu-bhopal",
    shortName: "NLIU Bhopal",
    series: [
      { year: 2021, rank: 309 },
      { year: 2022, rank: 316 },
      { year: 2023, rank: 334 },
      { year: 2024, rank: 387 },
      { year: 2025, rank: 395 },
      { year: 2026, rank: 459 },
    ],
  },
  {
    schoolId: "gnlu",
    shortName: "GNLU Gandhinagar",
    series: [
      { year: 2021, rank: 414 },
      { year: 2022, rank: 436 },
      { year: 2023, rank: 430 },
      { year: 2024, rank: 464 },
      { year: 2025, rank: 470 },
      { year: 2026, rank: 398 },
    ],
  },
  {
    schoolId: "nlu-jodhpur",
    shortName: "NLU Jodhpur",
    series: [
      { year: 2021, rank: 450 },
      { year: 2022, rank: 466 },
      { year: 2023, rank: 485 },
      { year: 2024, rank: 508 },
      { year: 2025, rank: 520 },
      { year: 2026, rank: 364 },
    ],
  },
  {
    schoolId: "hnlu",
    shortName: "HNLU Raipur",
    series: [
      { year: 2021, rank: 590 },
      { year: 2022, rank: 625 },
      { year: 2023, rank: 640 },
      { year: 2024, rank: 700 },
      { year: 2025, rank: 720 },
      { year: 2026, rank: 806 },
    ],
  },
  {
    schoolId: "rmlnlu",
    shortName: "RMLNLU Lucknow",
    series: [
      { year: 2021, rank: 688 },
      { year: 2022, rank: 712 },
      { year: 2023, rank: 720 },
      { year: 2024, rank: 764 },
      { year: 2025, rank: 810 },
      { year: 2026, rank: 799 },
    ],
  },
  {
    schoolId: "rgnul",
    shortName: "RGNUL Patiala",
    series: [
      { year: 2021, rank: 754 },
      { year: 2022, rank: 790 },
      { year: 2023, rank: 810 },
      { year: 2024, rank: 860 },
      { year: 2025, rank: 900 },
      { year: 2026, rank: 1281 },
    ],
  },
  {
    schoolId: "cnlu",
    shortName: "CNLU Patna",
    series: [
      { year: 2021, rank: 960 },
      { year: 2022, rank: 1010 },
      { year: 2023, rank: 1050 },
      { year: 2024, rank: 1100 },
      { year: 2025, rank: 1180 },
      { year: 2026, rank: 1235 },
    ],
  },
];

// AILET 2026 closing ranks for NLU Delhi BA-LLB (Hons).
// General/OBC/SC from Third Merit List, 4 Feb 2026 (the final round with new allotments
// for these categories). EWS/ST from earlier rounds — those categories did not see fresh
// allotment in Round 3 ("–" in the official list). Verify on nationallawuniversitydelhi.in
export const ailet2026 = {
  total_seats: 110,
  rounds: "Round 3 (final), 2026; EWS/ST from earlier rounds",
  by_category: [
    { category: "General", rank: 71 },
    { category: "OBC", rank: 373 },
    { category: "EWS", rank: 206 },
    { category: "ST", rank: 2018 },
    { category: "SC", rank: 1731 },
  ],
};

export const cutoffSources = [
  { label: "Consortium of NLUs (official)", url: "https://consortiumofnlus.ac.in/" },
  { label: "NLU Delhi (AILET official)", url: "https://nationallawuniversitydelhi.in/" },
  { label: "CLAT 2026 5th allotment list — CollegeDekho", url: "https://www.collegedekho.com/news/clat-ug-5th-allotment-list-2026-cutof-live-updates-78890/" },
  { label: "AILET 2026 Third Merit List — Careers360", url: "https://law.careers360.com/articles/ailet-2026-third-merit-list" },
  { label: "CLAT cutoffs — LawPrepTutorial", url: "https://www.lawpreptutorial.com/blog/clat/cut-off/" },
  { label: "CLAT cutoff history — CollegeDekho", url: "https://www.collegedekho.com/articles/clat-cut-off-opening-closing-ranks-round-1-general-obc-sc-st/" },
  { label: "IMS India CLAT cutoffs", url: "https://www.imsindia.com/blog/clat/clat-cutoff/" },
];

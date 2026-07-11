export interface Exam {
  code: string;
  fullName: string;
  conductedBy: string;
  schools: string;
  whenHeld: string;
  format?: string;
  website: string;
}

export const exams: Exam[] = [
  {
    code: "CLAT",
    fullName: "Common Law Admission Test",
    conductedBy: "Consortium of National Law Universities",
    schools: "24+ NLUs (UG and PG)",
    whenHeld: "December (annual)",
    format: "120 questions, 2 hours, 5 sections; -0.25 negative marking",
    website: "https://consortiumofnlus.ac.in/",
  },
  {
    code: "AILET",
    fullName: "All India Law Entrance Test",
    conductedBy: "NLU Delhi",
    schools: "NLU Delhi only",
    whenHeld: "December",
    format: "150 questions, 2 hours; English, Current Affairs/GK, Logical Reasoning",
    website: "https://nationallawuniversitydelhi.in/",
  },
  {
    code: "LSAT-India",
    fullName: "Law School Admission Test — India",
    conductedBy: "LSAC / Pearson VUE",
    schools: "JGLS, UPES, Bennett, several private schools",
    whenHeld: "January and May (two windows)",
    format: "92 questions, 2 hr 20 min; Logical, Analytical, Reading; no negative marking",
    website: "https://www.discoverlaw.in/",
  },
  {
    code: "SLAT",
    fullName: "Symbiosis Law Admission Test",
    conductedBy: "Symbiosis International University",
    schools: "Symbiosis Law Schools (Pune, Noida, Hyderabad, Nagpur)",
    whenHeld: "Multiple slots in April–May",
    website: "https://www.set-test.org/",
  },
  {
    code: "MH-CET Law",
    fullName: "Maharashtra Common Entrance Test — Law",
    conductedBy: "Maharashtra State CET Cell",
    schools: "Maharashtra state law colleges (GLC Mumbai, ILS Pune, etc.)",
    whenHeld: "March–April",
    website: "https://cetcell.mahacet.org/",
  },
  {
    code: "DU LLB",
    fullName: "Delhi University LLB Entrance",
    conductedBy: "Delhi University (via CUET-PG)",
    schools: "Faculty of Law, DU (3-year LLB only)",
    whenHeld: "May–June (CUET-PG window)",
    website: "https://lawfaculty.du.ac.in/",
  },
  {
    code: "AP/TS LAWCET",
    fullName: "Andhra / Telangana Common Law Entrance Test",
    conductedBy: "Respective state councils",
    schools: "Andhra / Telangana state colleges",
    whenHeld: "May–June",
    website: "https://sche.ap.gov.in/",
  },
  {
    code: "CUET-UG / CUET-PG",
    fullName: "Common University Entrance Test",
    conductedBy: "National Testing Agency",
    schools: "Central universities (BHU, JMI, AMU, etc.)",
    whenHeld: "May–June",
    website: "https://cuet.nta.nic.in/",
  },
  {
    code: "AIBE",
    fullName: "All India Bar Examination",
    conductedBy: "Bar Council of India",
    schools: "Post-LLB; required to practice in courts",
    whenHeld: "Twice a year",
    format: "Open book; minimum qualifying score required to receive Certificate of Practice",
    website: "https://www.allindiabarexamination.com/",
  },
];

export const admissionTimeline = [
  { phase: "Aug–Sept", milestone: "CLAT registration opens on the Consortium portal." },
  { phase: "Dec", milestone: "CLAT exam (typically first or second Sunday)." },
  { phase: "Late Dec", milestone: "Provisional answer key, objections, final result published." },
  { phase: "Jan", milestone: "Counselling registration; preference filling for NLUs." },
  { phase: "Jan–May", milestone: "Multiple counselling rounds (usually 4 allotment lists)." },
  { phase: "Jul–Aug", milestone: "Academic sessions begin." },
];

export const eligibility = [
  {
    program: "5-year integrated UG (BA-LLB, BBA-LLB, etc.)",
    rule: "Class 12 with min. 45% (40% for SC/ST). Varies by school.",
  },
  {
    program: "3-year LLB",
    rule: "Bachelor's degree in any discipline with min. 45% aggregate.",
  },
  {
    program: "LLM",
    rule: "LLB / equivalent with min. 50% (varies).",
  },
  {
    program: "Practice as advocate",
    rule: "Pass AIBE after LLB and enrol with State Bar Council (mandatory under BCI rules).",
  },
];

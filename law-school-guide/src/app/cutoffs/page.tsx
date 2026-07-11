import { PageHero } from "@/components/page-hero";
import { CutoffTrendChart } from "@/components/cutoff-trend-chart";
import { Card } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Disclaimer } from "@/components/disclaimer";
import { SourceCitation } from "@/components/source-citation";
import { cutoffs, ailet2026, cutoffSources } from "@/lib/data/cutoffs";

export const metadata = { title: "CLAT & AILET Cutoffs — Last 5 Years" };

const ruleOfThumb = [
  { rank: "AIR 1–100", outcome: "NLSIU Bengaluru is realistic." },
  { rank: "100–200", outcome: "NALSAR; some chance at NLSIU." },
  { rank: "200–500", outcome: "NUJS, NLIU Bhopal, GNLU." },
  { rank: "500–1000", outcome: "NLU Jodhpur, RMLNLU, HNLU, RGNUL." },
  { rank: "1000–2500", outcome: "CNLU, NUSRL, MNLUs, DSNLU, HPNLU." },
  { rank: "2500–5000", outcome: "Newer NLUs (Tripura, Jabalpur, etc.) and many private schools." },
];

const feeComparison = [
  { school: "NLSIU Bengaluru", perYear: "₹3.2–5 lakh", total: "₹24–25 lakh", hostel: "Yes (mandatory on-campus)" },
  { school: "NLU Delhi", perYear: "~₹1.4 lakh", total: "~₹6.8 lakh", hostel: "Yes (subsidised state-funded)" },
  { school: "NALSAR Hyderabad", perYear: "~₹3.1 lakh", total: "~₹15.6 lakh", hostel: "Yes" },
  { school: "NUJS Kolkata", perYear: "~₹3.3 lakh", total: "~₹16.6 lakh", hostel: "Yes" },
  { school: "JGLS Sonipat", perYear: "~₹6.25 lakh tuition + ~₹3.1 lakh hostel", total: "~₹47–55 lakh", hostel: "Separate fee" },
  { school: "Symbiosis Law School Pune", perYear: "~₹3.5–4 lakh", total: "~₹18–22 lakh", hostel: "Separate" },
];

export default function Page() {
  const years = [2021, 2022, 2023, 2024, 2025];

  return (
    <>
      <PageHero
        eyebrow="Section 4"
        title="Cutoffs & CLAT Ranks"
        description="5-year CLAT general-category closing ranks for top NLUs, plus AILET and fee comparisons. Interactive chart below."
      />

      <section className="mx-auto max-w-6xl px-4 py-10 space-y-10">
        <CutoffTrendChart />

        <div>
          <h2 className="font-serif mb-3">CLAT closing ranks — General category (final round)</h2>
          <Card>
            <Table>
              <TableHeader>
                <TableRow className="bg-primary hover:bg-primary">
                  <TableHead className="text-primary-foreground">NLU</TableHead>
                  {years.map((y) => (
                    <TableHead key={y} className="text-primary-foreground text-right">{y}</TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {cutoffs.map((c) => (
                  <TableRow key={c.schoolId}>
                    <TableCell className="font-semibold">{c.shortName}</TableCell>
                    {years.map((y) => {
                      const point = c.series.find((s) => s.year === y);
                      return (
                        <TableCell key={y} className="text-right tabular-nums">
                          {point ? `~${point.rank}` : "—"}
                        </TableCell>
                      );
                    })}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
          <div className="mt-3">
            <SourceCitation sources={cutoffSources}>
              <strong>2025 figures confirmed</strong> (NLSIU 112 / NALSAR 159 / NUJS 327 — CLAT 2025 round-3 counselling). Earlier years aggregated from coaching-institute archives; they generally agree within ±10–20 ranks.
              {" "}<strong>Always verify exact numbers on the Consortium of NLUs site.</strong>
            </SourceCitation>
          </div>
        </div>

        <div className="grid gap-6 md:grid-cols-2">
          <Card className="p-6">
            <h3 className="font-serif text-xl mb-3">AILET 2026 — NLU Delhi BA-LLB (Round 3, final)</h3>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Category</TableHead>
                  <TableHead className="text-right">Closing rank</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {ailet2026.by_category.map((c) => (
                  <TableRow key={c.category}>
                    <TableCell className="font-medium">{c.category}</TableCell>
                    <TableCell className="text-right tabular-nums">{c.rank}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <p className="text-xs text-muted-foreground mt-3">
              Total NLU Delhi BA-LLB seats: <strong>{ailet2026.total_seats}</strong>
            </p>
            <SourceCitation
              sources={[
                { label: "AILET 2026 Third Merit List — Careers360", url: "https://law.careers360.com/articles/ailet-2026-third-merit-list" },
                { label: "NLU Delhi (official)", url: "https://nationallawuniversitydelhi.in/" },
              ]}
            >
              {""}
            </SourceCitation>
          </Card>

          <Card className="p-6">
            <h3 className="font-serif text-xl mb-3">What rank gets you what NLU? (rule of thumb)</h3>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Rank range</TableHead>
                  <TableHead>Realistic outcome</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {ruleOfThumb.map((r) => (
                  <TableRow key={r.rank}>
                    <TableCell className="font-medium whitespace-nowrap">{r.rank}</TableCell>
                    <TableCell className="text-sm">{r.outcome}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </div>

        <div>
          <h2 className="font-serif mb-3">Fee comparison — top schools</h2>
          <Card>
            <Table>
              <TableHeader>
                <TableRow className="bg-primary hover:bg-primary">
                  <TableHead className="text-primary-foreground">School</TableHead>
                  <TableHead className="text-primary-foreground">Per year (BA-LLB)</TableHead>
                  <TableHead className="text-primary-foreground">5-yr total (approx.)</TableHead>
                  <TableHead className="text-primary-foreground">Hostel</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {feeComparison.map((f) => (
                  <TableRow key={f.school}>
                    <TableCell className="font-medium">{f.school}</TableCell>
                    <TableCell>{f.perYear}</TableCell>
                    <TableCell className="font-semibold">{f.total}</TableCell>
                    <TableCell className="text-sm">{f.hostel}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
          <SourceCitation
            sources={[
              { label: "NLSIU fees", url: "https://www.lawpreptutorial.com/blog/national-law-universities/nlsiu-bangalore/fee-structure/" },
              { label: "JGLS fees", url: "https://www.collegesearch.in/colleges/jindal-global-law-school-jgls-sonepat/courses-fees" },
              { label: "All NLU fees — Careers360", url: "https://law.careers360.com/articles/nlu-fee-structure" },
            ]}
          >
            From official sites and aggregator sources, June 2026. Annual fee revisions of 5–10% are typical, especially at private schools.
          </SourceCitation>
        </div>

        <Disclaimer variant="warning" title="Important caveat">
          Cutoffs depend on the counselling round, candidate withdrawals, and home-state quotas. The numbers shown are from final rounds. State-domicile and reserved-category cutoffs are higher (you can get in with a worse rank). Always verify on{" "}
          <a className="underline text-destructive" href="https://consortiumofnlus.ac.in/" target="_blank" rel="noopener">consortiumofnlus.ac.in</a>.
        </Disclaimer>
      </section>
    </>
  );
}

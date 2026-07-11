import { PageHero } from "@/components/page-hero";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Disclaimer } from "@/components/disclaimer";
import { SourceCitation } from "@/components/source-citation";
import { reviewSources } from "@/lib/data/reviews";
import { schools } from "@/lib/data/schools";
import { ExternalLink } from "lucide-react";

export const metadata = { title: "Law School Rankings — NIRF 2025 + Reviews" };

const top10 = schools.filter((s) => s.nirfRank2025).sort((a, b) => (a.nirfRank2025! - b.nirfRank2025!));

const notes: Record<number, string> = {
  1: "#1 for the 8th consecutive year",
  2: "Holds #2 spot",
  3: "Strong corporate / IP focus",
  4: "Retains #4",
  5: "Climbed into the top 5",
  6: "Only IIT-hosted law school; IP-focused (jumped from #10 in 2024)",
  7: "Top private NIRF entrant",
  8: "Central university — climbed up",
  9: "Central university — climbed up",
  10: "New top-10 entrant (Bhubaneswar private)",
};

export default function Page() {
  return (
    <>
      <PageHero
        eyebrow="Section 2"
        title="Rankings & Reviews"
        description="The most authoritative ranking in India is NIRF (National Institutional Ranking Framework), published annually by the Ministry of Education."
      />

      <section className="mx-auto max-w-6xl px-4 py-10 space-y-10">
        <div>
          <h2 className="font-serif mb-4">NIRF 2025 — Law (Top 10)</h2>
          <Card>
            <Table>
              <TableHeader>
                <TableRow className="bg-primary hover:bg-primary">
                  <TableHead className="text-primary-foreground w-20">Rank</TableHead>
                  <TableHead className="text-primary-foreground">Institution</TableHead>
                  <TableHead className="text-primary-foreground">City</TableHead>
                  <TableHead className="text-primary-foreground">Notes</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {top10.map((s) => (
                  <TableRow key={s.id}>
                    <TableCell><Badge className="bg-primary text-primary-foreground">{s.nirfRank2025}</Badge></TableCell>
                    <TableCell>
                      <div className="font-medium">{s.shortName}</div>
                      <div className="text-xs text-muted-foreground">{s.name}</div>
                    </TableCell>
                    <TableCell>{s.city}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">{notes[s.nirfRank2025!] ?? ""}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
          <div className="mt-3">
            <SourceCitation
              sources={[
                { label: "NIRF 2025 Law (official)", url: "https://www.nirfindia.org/Rankings/2025/LawRanking.html" },
                { label: "Bar & Bench analysis", url: "https://www.barandbench.com/news/lawschools/nirf-rankings-2025-nlus-dominate-top-5-nlsiu-nlu-delhi-nalsar-retain-top-spots" },
                { label: "Lawctopus release", url: "https://www.lawctopus.com/nirf-law-rankings-2025-released/" },
              ]}
            >
              267 law schools participated in NIRF 2025; only 13 NLUs made the top 40.
            </SourceCitation>
          </div>
        </div>

        <div>
          <h2 className="font-serif mb-3">Where to read real student &amp; parent reviews</h2>
          <p className="text-muted-foreground mb-5 max-w-3xl">
            We deliberately do not paste fabricated quotes here. The links below are vetted public sources where you can read first-person accounts from current students, alumni, and parents.
          </p>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {reviewSources.map((r) => (
              <Card key={r.url}>
                <CardHeader className="pb-3">
                  <CardTitle className="font-serif text-lg">{r.name}</CardTitle>
                  {r.bestFor && <CardDescription className="text-xs">Best for: {r.bestFor}</CardDescription>}
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground mb-3">{r.description}</p>
                  <a
                    href={r.url}
                    target="_blank"
                    rel="noopener"
                    className="inline-flex items-center gap-1 text-sm text-destructive hover:underline font-medium"
                  >
                    Visit <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        <Disclaimer variant="tip" title="Tip for parents.">
          Read reviews from at least 3 sources before forming a view. If multiple reviewers flag the same hostel issue or placement weakness, it&apos;s likely real. Single glowing or scathing reviews are usually outliers.
        </Disclaimer>
      </section>
    </>
  );
}

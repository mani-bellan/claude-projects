import { PageHero } from "@/components/page-hero";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Disclaimer } from "@/components/disclaimer";
import { SourceCitation } from "@/components/source-citation";
import { abroadSchools, indianStudentRoutes, barRequirements, abroadSources } from "@/lib/data/abroad";
import { ExternalLink } from "lucide-react";

export const metadata = { title: "Top Law Universities Abroad — QS 2025" };

export default function Page() {
  return (
    <>
      <PageHero
        eyebrow="Section 8"
        title="Top 10 Law Universities Abroad"
        description="Based on QS World University Rankings 2025 — Law & Legal Studies. The top 10 is dominated by US and UK schools."
      />
      <section className="mx-auto max-w-6xl px-4 py-10 space-y-10">
        <div>
          <Card>
            <Table>
              <TableHeader>
                <TableRow className="bg-primary hover:bg-primary">
                  <TableHead className="text-primary-foreground w-20">QS '25</TableHead>
                  <TableHead className="text-primary-foreground">University</TableHead>
                  <TableHead className="text-primary-foreground">Country</TableHead>
                  <TableHead className="text-primary-foreground">Flagship degrees</TableHead>
                  <TableHead className="text-primary-foreground">Tuition / yr</TableHead>
                  <TableHead className="text-primary-foreground"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {abroadSchools.map((s) => (
                  <TableRow key={s.name}>
                    <TableCell><Badge className="bg-primary text-primary-foreground">{s.qsRank2025}</Badge></TableCell>
                    <TableCell>
                      <div className="font-semibold">{s.name}</div>
                      {s.highlight && <div className="text-xs text-muted-foreground mt-0.5">{s.highlight}</div>}
                    </TableCell>
                    <TableCell>{s.country}</TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {s.flagshipDegrees.map((d) => (
                          <Badge key={d} variant="outline" className="text-xs">{d}</Badge>
                        ))}
                      </div>
                    </TableCell>
                    <TableCell className="text-sm">{s.indicativeAnnualTuition}</TableCell>
                    <TableCell>
                      <a href={s.website} target="_blank" rel="noopener" className="inline-flex items-center gap-1 text-destructive hover:underline text-xs">
                        Site <ExternalLink className="h-3 w-3" />
                      </a>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
          <SourceCitation sources={abroadSources}>
            Tuition is approximate; living costs add 30–60%. THE and US News rankings differ slightly; most schools fall in the same broad tier.
          </SourceCitation>
        </div>

        <div>
          <h2 className="font-serif mb-4">What Indian students typically apply for abroad</h2>
          <div className="grid gap-4 md:grid-cols-2">
            {indianStudentRoutes.map((r) => (
              <Card key={r.title}>
                <CardHeader><CardTitle className="font-serif text-lg">{r.title}</CardTitle></CardHeader>
                <CardContent className="text-sm space-y-2">
                  <p>{r.body}</p>
                  <p className="text-xs text-muted-foreground"><span className="font-semibold">Application:</span> {r.application}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        <div>
          <h2 className="font-serif mb-4">Practising abroad — bar requirements</h2>
          <Card>
            <Table>
              <TableHeader>
                <TableRow className="bg-primary hover:bg-primary">
                  <TableHead className="text-primary-foreground">Country</TableHead>
                  <TableHead className="text-primary-foreground">Requirement</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {barRequirements.map((b) => (
                  <TableRow key={b.country}>
                    <TableCell className="font-semibold">{b.country}</TableCell>
                    <TableCell className="text-sm">{b.requirement}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </div>

        <Disclaimer variant="tip" title="Scholarships to know.">
          Inlaks, Chevening, Commonwealth, Rhodes, Felix, Tata Scholarships, Fulbright, JN Tata Endowment — plus school-specific programmes (Harvard&apos;s Frank Knox, Oxford&apos;s Weidenfeld-Hoffmann, etc.).
        </Disclaimer>
      </section>
    </>
  );
}

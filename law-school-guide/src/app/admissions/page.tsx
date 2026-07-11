import { PageHero } from "@/components/page-hero";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Disclaimer } from "@/components/disclaimer";
import { exams, admissionTimeline, eligibility } from "@/lib/data/exams";
import { ExternalLink, Calendar } from "lucide-react";

export const metadata = { title: "Admission Procedure — Indian Law Schools" };

export default function Page() {
  return (
    <>
      <PageHero
        eyebrow="Section 3"
        title="Admission Procedure"
        description="Admission to law schools in India is almost entirely via standardized entrance exams. The school you target determines the exam."
      />
      <section className="mx-auto max-w-6xl px-4 py-10 space-y-10">
        <div>
          <h2 className="font-serif mb-4">Entrance exams at a glance</h2>
          <Card>
            <Table>
              <TableHeader>
                <TableRow className="bg-primary hover:bg-primary">
                  <TableHead className="text-primary-foreground">Exam</TableHead>
                  <TableHead className="text-primary-foreground">Conducted by</TableHead>
                  <TableHead className="text-primary-foreground">Schools accepting</TableHead>
                  <TableHead className="text-primary-foreground">When held</TableHead>
                  <TableHead className="text-primary-foreground"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {exams.map((e) => (
                  <TableRow key={e.code}>
                    <TableCell>
                      <div className="font-semibold">{e.code}</div>
                      <div className="text-xs text-muted-foreground">{e.fullName}</div>
                    </TableCell>
                    <TableCell className="text-sm">{e.conductedBy}</TableCell>
                    <TableCell className="text-sm">{e.schools}</TableCell>
                    <TableCell className="text-sm">{e.whenHeld}</TableCell>
                    <TableCell>
                      <a href={e.website} target="_blank" rel="noopener" className="inline-flex items-center gap-1 text-destructive hover:underline text-xs">
                        Site <ExternalLink className="h-3 w-3" />
                      </a>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </div>

        <div className="grid gap-6 md:grid-cols-2">
          <Card>
            <CardHeader><CardTitle className="font-serif">CLAT — the dominant route</CardTitle></CardHeader>
            <CardContent className="text-sm space-y-2">
              <p>CLAT is a single online test for both UG and PG admissions to most NLUs.</p>
              <p>The UG paper has 5 sections:</p>
              <ul className="list-disc pl-5 space-y-0.5">
                <li>English Language</li>
                <li>Current Affairs &amp; GK</li>
                <li>Legal Reasoning</li>
                <li>Logical Reasoning</li>
                <li>Quantitative Techniques</li>
              </ul>
              <p>120 questions, 2 hours. Negative marking: <strong>−0.25</strong> per wrong answer.</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle className="font-serif">Eligibility — quick reference</CardTitle></CardHeader>
            <CardContent className="text-sm space-y-3">
              {eligibility.map((e) => (
                <div key={e.program}>
                  <p className="font-semibold">{e.program}</p>
                  <p className="text-muted-foreground">{e.rule}</p>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>

        <div>
          <h2 className="font-serif mb-4">Typical CLAT admission timeline</h2>
          <div className="space-y-3">
            {admissionTimeline.map((t, i) => (
              <div key={t.phase} className="flex gap-4 items-start bg-card border rounded-lg p-4">
                <div className="flex flex-col items-center">
                  <div className="bg-primary text-primary-foreground rounded-full w-8 h-8 flex items-center justify-center font-semibold text-sm">{i + 1}</div>
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <Calendar className="h-4 w-4 text-muted-foreground" />
                    <span className="font-semibold text-primary">{t.phase}</span>
                  </div>
                  <p className="text-sm text-muted-foreground">{t.milestone}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <Disclaimer variant="info" title="Reservation rules">
          NLUs follow central reservations (SC, ST, OBC-NCL, EWS, PwD) plus often a <em>state domicile</em> quota at their home-state NLU (e.g., Karnataka residents at NLSIU, UP residents at RMLNLU). This significantly affects the achievable cutoff at your home-state NLU.
        </Disclaimer>
      </section>
    </>
  );
}

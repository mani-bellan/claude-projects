import { PageHero } from "@/components/page-hero";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Disclaimer } from "@/components/disclaimer";
import { specializations, higherStudies, llmCostReference, scholarships } from "@/lib/data/courses";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

export const metadata = { title: "Specializations & Higher Studies" };

export default function Page() {
  return (
    <>
      <PageHero
        eyebrow="Section 6"
        title="Specializations & Higher Studies"
        description="Specialization typically begins in the 4th–5th year through electives, internships, and seminar papers, then deepens in LLM or practice."
      />
      <section className="mx-auto max-w-6xl px-4 py-10 space-y-12">
        <div>
          <h2 className="font-serif mb-5">Major specializations within Indian law</h2>
          <div className="grid gap-4 md:grid-cols-2">
            {specializations.map((sp) => (
              <Card key={sp.title}>
                <CardHeader>
                  <CardTitle className="font-serif text-lg">{sp.title}</CardTitle>
                </CardHeader>
                <CardContent className="text-sm space-y-3">
                  <p>{sp.summary}</p>
                  <div>
                    <p className="text-xs font-medium text-muted-foreground mb-1">Strong at:</p>
                    <div className="flex flex-wrap gap-1">
                      {sp.strongAt.map((s) => (
                        <Badge key={s} variant="outline" className="text-xs">{s}</Badge>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        <div>
          <h2 className="font-serif mb-5">Higher studies abroad</h2>
          <div className="grid gap-4 md:grid-cols-2">
            {higherStudies.map((h) => (
              <Card key={h.label}>
                <CardHeader className="pb-2"><CardTitle className="font-serif text-lg">{h.label}</CardTitle></CardHeader>
                <CardContent className="text-sm">{h.body}</CardContent>
              </Card>
            ))}
          </div>
        </div>

        <div>
          <h3 className="font-serif text-xl mb-3">Cost reference for LLM abroad</h3>
          <Card>
            <Table>
              <TableHeader>
                <TableRow className="bg-primary hover:bg-primary">
                  <TableHead className="text-primary-foreground">Destination</TableHead>
                  <TableHead className="text-primary-foreground">1-yr LLM cost</TableHead>
                  <TableHead className="text-primary-foreground">Note</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {llmCostReference.map((r) => (
                  <TableRow key={r.destination}>
                    <TableCell className="font-medium">{r.destination}</TableCell>
                    <TableCell className="font-semibold">{r.costINR}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">{r.note}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
          <p className="text-xs text-muted-foreground mt-2">Total cost includes tuition + living. Scholarships are limited but exist.</p>
        </div>

        <Disclaimer variant="tip" title="Scholarships to know">
          <div className="flex flex-wrap gap-1.5 mt-1">
            {scholarships.map((s) => (
              <Badge key={s} variant="secondary" className="text-xs">{s}</Badge>
            ))}
          </div>
        </Disclaimer>
      </section>
    </>
  );
}

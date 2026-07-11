import { PageHero } from "@/components/page-hero";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { officialSources, reviewSources, dataReferenceSources } from "@/lib/data/reviews";
import { ExternalLink } from "lucide-react";

export const metadata = { title: "Reviews, Sources & Disclaimers" };

const SourceGrid = ({ items }: { items: { name: string; description?: string; url: string }[] }) => (
  <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
    {items.map((it) => (
      <Card key={it.url}>
        <CardHeader className="pb-2">
          <CardTitle className="font-serif text-base">{it.name}</CardTitle>
          {it.description && <CardDescription className="text-xs">{it.description}</CardDescription>}
        </CardHeader>
        <CardContent>
          <a href={it.url} target="_blank" rel="noopener" className="inline-flex items-center gap-1 text-sm text-destructive hover:underline font-medium break-all">
            {it.url.replace(/^https?:\/\//, "").split("/")[0]}
            <ExternalLink className="h-3.5 w-3.5 shrink-0" />
          </a>
        </CardContent>
      </Card>
    ))}
  </div>
);

export default function Page() {
  return (
    <>
      <PageHero
        eyebrow="Section 9"
        title="Reviews, Sources & Disclaimers"
        description="Authoritative sources for verification, real review platforms (no fabricated quotes), and the data references used throughout this site."
      />
      <section className="mx-auto max-w-6xl px-4 py-10 space-y-12">
        <div>
          <h2 className="font-serif mb-4">Authoritative / official sources</h2>
          <SourceGrid items={officialSources} />
        </div>

        <div>
          <h2 className="font-serif mb-4">Real reviews &amp; community discussion</h2>
          <p className="text-sm text-muted-foreground mb-4 max-w-3xl">
            We deliberately do not paste fabricated quotes here. The platforms below carry first-person reviews from current students, alumni, and parents.
          </p>
          <SourceGrid items={reviewSources} />
        </div>

        <div>
          <h2 className="font-serif mb-4">Data reference sources used on this site</h2>
          <SourceGrid items={dataReferenceSources} />
        </div>

        <div>
          <h2 className="font-serif mb-4">Honest disclaimers</h2>
          <Accordion className="bg-card rounded-lg border">
            <AccordionItem value="cutoffs" className="px-5">
              <AccordionTrigger className="font-semibold">About cutoffs</AccordionTrigger>
              <AccordionContent className="text-sm text-muted-foreground">
                CLAT 2025 round-3 figures are confirmed from public counselling lists. Earlier-year cutoffs are aggregated from multiple coaching-institute archives (LawPrepTutorial, CollegeDekho, IMS, Toprankers, Tarkashastra) that generally agree within ±10–20 ranks. Always verify the exact number on the Consortium of NLUs site before relying on it for decisions.
              </AccordionContent>
            </AccordionItem>
            <AccordionItem value="fees" className="px-5">
              <AccordionTrigger className="font-semibold">About fees</AccordionTrigger>
              <AccordionContent className="text-sm text-muted-foreground">
                Fees are from each university&apos;s published fee structure or major aggregators (Shiksha, Careers360, LawPrepTutorial). Universities revise fees annually, often by 5–10%. Some figures here are point estimates; please refer to the official site for the latest fee circular.
              </AccordionContent>
            </AccordionItem>
            <AccordionItem value="salaries" className="px-5">
              <AccordionTrigger className="font-semibold">About salary ranges</AccordionTrigger>
              <AccordionContent className="text-sm text-muted-foreground">
                Salary ranges are general-market estimates, not guaranteed offers. Top-tier-firm A0 numbers (₹17–20 LPA) apply primarily to top-5 NLU graduates; ranges narrow significantly outside the top 10–12 schools. Litigation and judiciary careers have very wide variability.
              </AccordionContent>
            </AccordionItem>
            <AccordionItem value="reviews" className="px-5">
              <AccordionTrigger className="font-semibold">About reviews</AccordionTrigger>
              <AccordionContent className="text-sm text-muted-foreground">
                We explicitly do not reproduce or paraphrase student/parent reviews on this site, because synthesising AI-generated quotes would be misleading. Instead, we link directly to the source platforms (Shiksha, Quora, LawSchoolPolicyReview, etc.) so you read first-person accounts in context.
              </AccordionContent>
            </AccordionItem>
            <AccordionItem value="abroad" className="px-5">
              <AccordionTrigger className="font-semibold">About abroad rankings</AccordionTrigger>
              <AccordionContent className="text-sm text-muted-foreground">
                Rankings shown are QS World University Rankings 2025 — Law &amp; Legal Studies. Times Higher Education and US News rankings differ in detail; most top schools fall within the same broad tier across all three rankings.
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        </div>
      </section>
    </>
  );
}

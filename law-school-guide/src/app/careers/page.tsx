import { PageHero } from "@/components/page-hero";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { SourceCitation } from "@/components/source-citation";
import { careerPaths, careerSources } from "@/lib/data/careers";

export const metadata = { title: "Career Options After Law in India" };

export default function Page() {
  return (
    <>
      <PageHero
        eyebrow="Section 7"
        title="Career Options After Law"
        description="An LLB opens up a much wider range of careers than just 'becoming a lawyer'. Salary numbers below are general ranges; actual figures depend heavily on school tier, network, and city."
      />
      <section className="mx-auto max-w-6xl px-4 py-10 space-y-6">
        {careerPaths.map((p) => (
          <Card key={p.title} className="overflow-hidden">
            <div className="grid md:grid-cols-[200px_1fr]">
              <div className="bg-secondary p-5 flex flex-col justify-center items-center text-center border-r">
                <Badge className="bg-primary text-primary-foreground hover:bg-primary mb-2">Salary</Badge>
                <p className="font-semibold text-sm leading-tight">{p.salaryRange}</p>
              </div>
              <div className="p-5">
                <h3 className="font-serif text-xl mb-2">{p.title}</h3>
                <p className="text-sm text-muted-foreground mb-2">{p.summary}</p>
                <p className="text-sm">{p.detail}</p>
                {p.pathway && (
                  <p className="text-xs text-muted-foreground mt-3 pt-3 border-t">
                    <span className="font-semibold">Pathway: </span>
                    {p.pathway}
                  </p>
                )}
              </div>
            </div>
          </Card>
        ))}

        <SourceCitation sources={careerSources}>
          Salary ranges from Law Drishti (Law Firm Salaries 2025), Shiksha (Lawyer Salary in India), and IMS (Law Careers in India).
        </SourceCitation>
      </section>
    </>
  );
}

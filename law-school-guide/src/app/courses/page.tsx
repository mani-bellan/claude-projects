import { PageHero } from "@/components/page-hero";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { courses } from "@/lib/data/courses";

export const metadata = { title: "Courses Available — Law in India" };

export default function Page() {
  return (
    <>
      <PageHero
        eyebrow="Section 5"
        title="Courses Available"
        description="Indian law education has three main entry routes and several advanced options."
      />
      <section className="mx-auto max-w-6xl px-4 py-10">
        <div className="grid gap-5 md:grid-cols-2">
          {courses.map((c) => (
            <Card key={c.title} className="h-full">
              <CardHeader>
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <CardTitle className="font-serif text-xl">{c.title}</CardTitle>
                  <Badge variant="secondary" className="font-mono">{c.duration}</Badge>
                </div>
                {c.bestFor && <CardDescription className="text-sm">Best for: {c.bestFor}</CardDescription>}
              </CardHeader>
              <CardContent className="text-sm space-y-3">
                <p>{c.description}</p>
                {c.variants && (
                  <ul className="list-disc pl-5 space-y-0.5 text-muted-foreground">
                    {c.variants.map((v) => <li key={v}>{v}</li>)}
                  </ul>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      </section>
    </>
  );
}

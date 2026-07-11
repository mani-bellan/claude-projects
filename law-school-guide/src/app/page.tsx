import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Disclaimer } from "@/components/disclaimer";
import {
  School,
  Trophy,
  ClipboardList,
  TrendingDown,
  BookOpen,
  Briefcase,
  Globe,
  GitCompare,
  BookMarked,
  Scale,
} from "lucide-react";

const sections = [
  { href: "/india-schools", title: "India Schools", desc: "Searchable directory of NLUs, private and traditional law schools.", icon: School },
  { href: "/rankings", title: "Rankings", desc: "NIRF 2025 top law schools and where to read real student/parent reviews.", icon: Trophy },
  { href: "/admissions", title: "Admission Procedure", desc: "CLAT, AILET, LSAT-India, SLAT and other entrance routes explained.", icon: ClipboardList },
  { href: "/cutoffs", title: "Cutoffs & Trends", desc: "5-year CLAT closing-rank trends with interactive chart.", icon: TrendingDown },
  { href: "/courses", title: "Courses", desc: "5-year integrated UG, 3-year LLB, LLM, PhD and more.", icon: BookOpen },
  { href: "/specializations", title: "Specializations", desc: "Corporate, IP, constitutional, tech law — and where they're strong.", icon: BookMarked },
  { href: "/careers", title: "Careers", desc: "Litigation, tier-1 firms, judiciary, in-house — with salary ranges.", icon: Briefcase },
  { href: "/abroad", title: "Top 10 Abroad", desc: "QS-ranked global law schools and routes for Indian students.", icon: Globe },
  { href: "/compare", title: "Compare Schools", desc: "Side-by-side comparison of any 2 or 3 law schools.", icon: GitCompare },
];

export default function Home() {
  return (
    <>
      <section className="bg-gradient-to-br from-primary via-primary to-[oklch(0.22_0.06_255)] text-primary-foreground py-16 md:py-24">
        <div className="mx-auto max-w-5xl px-4 text-center">
          <div className="flex justify-center mb-4">
            <Badge className="bg-accent text-accent-foreground hover:bg-accent">
              For parents · For students · Sourced data
            </Badge>
          </div>
          <h1 className="font-serif text-4xl md:text-5xl font-semibold mb-4 text-white leading-tight">
            A Parent&apos;s Guide to Law Schools <br className="hidden md:block" />in India &amp; Abroad
          </h1>
          <p className="text-primary-foreground/85 text-lg md:text-xl max-w-3xl mx-auto leading-relaxed">
            Rankings, admissions, cutoffs, fees, courses, specializations, and career paths — sourced from public records and linked to authoritative sources you can verify.
          </p>
          <div className="flex flex-wrap gap-3 justify-center mt-8">
            <Link
              href="/india-schools"
              className={cn(
                buttonVariants({ size: "lg" }),
                "h-11 px-6 text-base bg-accent text-accent-foreground hover:bg-accent/90"
              )}
            >
              Explore Indian Law Schools
            </Link>
            <Link
              href="/compare"
              className={cn(
                buttonVariants({ size: "lg", variant: "outline" }),
                "h-11 px-6 text-base bg-transparent border-white/40 text-white hover:bg-white/10"
              )}
            >
              Compare Schools
            </Link>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-12">
        <Disclaimer variant="info" title="How to use this guide.">
          Every data point links to its public source. Cutoffs, fees, and rankings change yearly — always verify on the official university site or the Consortium of NLUs portal before making decisions. For reviews, we link to the platforms (Shiksha, Quora, LawSchoolPolicyReview) where parents and students post first-person accounts. We do not invent quotes.
        </Disclaimer>

        <h2 className="font-serif mt-10 mb-6">Browse by topic</h2>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {sections.map((s) => {
            const Icon = s.icon;
            return (
              <Link key={s.href} href={s.href} className="group">
                <Card className="h-full transition-all group-hover:-translate-y-0.5 group-hover:shadow-lg group-hover:border-primary">
                  <CardHeader>
                    <div className="flex items-start gap-3">
                      <div className="bg-secondary p-2 rounded-md text-primary">
                        <Icon className="h-5 w-5" />
                      </div>
                      <CardTitle className="font-serif text-lg leading-tight pt-1">{s.title}</CardTitle>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <CardDescription className="text-sm">{s.desc}</CardDescription>
                  </CardContent>
                </Card>
              </Link>
            );
          })}
        </div>

        <div className="mt-12 grid gap-6 md:grid-cols-3">
          <Card className="bg-secondary border-primary/10">
            <CardHeader className="pb-2">
              <Scale className="h-6 w-6 text-primary mb-2" />
              <CardTitle className="font-serif text-lg">50+ schools indexed</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                23 NLUs, traditional faculties (DU, BHU, GLC, AMU, Jamia), top private schools (JGLS, Symbiosis Pune/Hyd/Noida, BITS Law, NMIMS, KIIT, Bennett).
              </p>
            </CardContent>
          </Card>
          <Card className="bg-secondary border-primary/10">
            <CardHeader className="pb-2">
              <TrendingDown className="h-6 w-6 text-primary mb-2" />
              <CardTitle className="font-serif text-lg">5 years of cutoffs</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                CLAT general-category closing ranks (2021–2025) for top NLUs, with interactive trend chart.
              </p>
            </CardContent>
          </Card>
          <Card className="bg-secondary border-primary/10">
            <CardHeader className="pb-2">
              <Globe className="h-6 w-6 text-primary mb-2" />
              <CardTitle className="font-serif text-lg">Top 10 abroad</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                QS-ranked Harvard, Oxford, Cambridge through Melbourne — with routes for Indian students and bar requirements.
              </p>
            </CardContent>
          </Card>
        </div>
      </section>
    </>
  );
}

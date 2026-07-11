import Link from "next/link";
import { Scale } from "lucide-react";

export function SiteFooter() {
  return (
    <footer className="bg-primary text-primary-foreground/85 mt-12 py-10 text-sm">
      <div className="mx-auto max-w-7xl px-4 grid gap-8 md:grid-cols-3">
        <div>
          <div className="flex items-center gap-2 mb-3">
            <Scale className="h-5 w-5 text-accent" />
            <span className="font-serif text-base text-accent">Law School Guide</span>
          </div>
          <p className="leading-relaxed">
            A sourced reference for parents and students navigating law school decisions in India and abroad. This is an information aggregation, not a counselling service.
          </p>
        </div>

        <div>
          <p className="text-accent font-medium mb-2">Quick links</p>
          <ul className="space-y-1.5">
            <li><Link href="/india-schools" className="hover:underline">India Schools</Link></li>
            <li><Link href="/cutoffs" className="hover:underline">CLAT Cutoffs &amp; Trends</Link></li>
            <li><Link href="/compare" className="hover:underline">Compare Schools</Link></li>
            <li><Link href="/abroad" className="hover:underline">Top 10 Abroad</Link></li>
            <li><Link href="/resources" className="hover:underline">Reviews &amp; Sources</Link></li>
          </ul>
        </div>

        <div>
          <p className="text-accent font-medium mb-2">Verify on official sources</p>
          <p className="leading-relaxed">
            Cutoffs, fees, and seat counts change yearly. Always cross-check on the relevant official site before any decision —
            {" "}<a className="underline hover:text-accent" href="https://consortiumofnlus.ac.in/" target="_blank" rel="noopener">CLAT Consortium</a>,{" "}
            <a className="underline hover:text-accent" href="https://nationallawuniversitydelhi.in/" target="_blank" rel="noopener">NLU Delhi (AILET)</a>,{" "}
            <a className="underline hover:text-accent" href="https://www.nirfindia.org/Rankings/2025/LawRanking.html" target="_blank" rel="noopener">NIRF</a>.
          </p>
          <p className="mt-3 text-primary-foreground/65">Last data refresh: <strong className="text-accent">June 2026</strong></p>
        </div>
      </div>
    </footer>
  );
}

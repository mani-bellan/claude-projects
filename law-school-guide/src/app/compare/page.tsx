import { PageHero } from "@/components/page-hero";
import { SchoolCompare } from "@/components/school-compare";
import { Disclaimer } from "@/components/disclaimer";

export const metadata = { title: "Compare Law Schools — Side by Side" };

export default function Page() {
  return (
    <>
      <PageHero
        eyebrow="Tool"
        title="Compare Law Schools"
        description="Pick any two or three schools and see them side-by-side — NIRF rank, entrance exam, fees, CLAT 2025 cutoff, programs, and notable strengths."
      />
      <section className="mx-auto max-w-6xl px-4 py-10">
        <SchoolCompare />

        <Disclaimer variant="info" title="What's missing from this view (and why)">
          Placement medians and cohort statistics are intentionally not shown — these are reported inconsistently and often selectively by schools. For a real comparison, ask each school&apos;s placement cell for the most recent <strong>NIRF Data Capture Report</strong>, which is the format mandated by the Ministry of Education and is usually accurate.
        </Disclaimer>
      </section>
    </>
  );
}

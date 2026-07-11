import { PageHero } from "@/components/page-hero";
import { SchoolDirectoryTable } from "@/components/school-directory-table";
import { Disclaimer } from "@/components/disclaimer";

export const metadata = { title: "Law Schools in India — Directory" };

export default function Page() {
  return (
    <>
      <PageHero
        eyebrow="Section 1"
        title="Law Schools in India"
        description="Search and filter across National Law Universities (NLUs), traditional university law faculties, and top private/deemed schools."
      />
      <section className="mx-auto max-w-6xl px-4 py-10">
        <div className="prose prose-slate max-w-none mb-6">
          <p>
            India has three broad categories of law institutions: <strong>National Law Universities (NLUs)</strong> — autonomous public universities admitting through CLAT/AILET; <strong>traditional university law faculties</strong> like Faculty of Law DU and GLC Mumbai with deep judicial-track reputations; and <strong>private and deemed universities</strong> like Jindal Global Law School and Symbiosis. There are 25+ NLUs across India today.
          </p>
        </div>

        <SchoolDirectoryTable />

        <Disclaimer variant="tip" title="Tip">
          Some excellent law schools (e.g., Faculty of Law DU, GLC Mumbai, BHU) charge under ₹1 lakh total — central- and state-funded universities are dramatically more affordable than private schools. Worth shortlisting both tiers.
        </Disclaimer>
      </section>
    </>
  );
}

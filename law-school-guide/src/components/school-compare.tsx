"use client";

import { useState } from "react";
import { schools, type School } from "@/lib/data/schools";
import { cutoffs } from "@/lib/data/cutoffs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Briefcase, ExternalLink, GraduationCap, Info, MapPin, Trophy, Users, Wallet } from "lucide-react";

const sortedSchools = [...schools].sort((a, b) => {
  // Ranked schools first, then alphabetical
  if (a.nirfRank2025 && b.nirfRank2025) return a.nirfRank2025 - b.nirfRank2025;
  if (a.nirfRank2025) return -1;
  if (b.nirfRank2025) return 1;
  return a.shortName.localeCompare(b.shortName);
});

function getCutoff2025(id: string) {
  const c = cutoffs.find((c) => c.schoolId === id);
  return c?.series.find((s) => s.year === 2025)?.rank;
}

function SchoolColumn({ school }: { school: School | null }) {
  if (!school) {
    return (
      <Card className="border-dashed border-2 min-h-[400px] flex items-center justify-center">
        <p className="text-muted-foreground text-sm">Pick a school above to compare</p>
      </Card>
    );
  }
  const cutoff = getCutoff2025(school.id);

  return (
    <Card className="overflow-hidden">
      <CardHeader className="bg-secondary border-b">
        <div className="flex items-start justify-between gap-2">
          <div>
            <CardTitle className="font-serif text-lg leading-tight">{school.shortName}</CardTitle>
            <p className="text-xs text-muted-foreground mt-1">{school.name}</p>
          </div>
          {school.nirfRank2025 && (
            <Badge className="bg-primary text-primary-foreground shrink-0">
              NIRF #{school.nirfRank2025}
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4 pt-4 text-sm">
        <Row
          icon={MapPin}
          label="Location"
          value={
            <>
              {school.city} · est. {school.established}
              {school.establishedNote && (
                <span title={school.establishedNote} className="inline-flex items-center gap-1 ml-1 text-muted-foreground cursor-help">
                  <Info className="h-3 w-3" />
                </span>
              )}
            </>
          }
        />
        {(school.studentsTotal || school.facultyTotal) && (
          <Row
            icon={Users}
            label="Size (approx.)"
            value={
              <>
                {school.studentsTotal && <><strong>{school.studentsTotal.toLocaleString()}</strong> students</>}
                {school.studentsTotal && school.facultyTotal && " · "}
                {school.facultyTotal && <><strong>{school.facultyTotal}</strong> faculty</>}
                {school.facultyNote && <p className="text-[10px] text-muted-foreground mt-0.5 italic">{school.facultyNote}</p>}
              </>
            }
          />
        )}
        <Row icon={Trophy} label="Type" value={
          <Badge variant={school.type === "public" ? "default" : school.type === "private" ? "destructive" : "secondary"} className="capitalize">
            {school.type === "public" ? "NLU / Public" : school.type === "private" ? "Private" : "Traditional"}
          </Badge>
        } />
        <Row icon={GraduationCap} label="Entrance" value={school.entrance.join(", ")} />
        {cutoff && (
          <Row
            icon={Trophy}
            label="CLAT 2025 closing rank (Gen)"
            value={<span className="font-semibold">~{cutoff}</span>}
          />
        )}
        <Row
          icon={Wallet}
          label="Approx. 5-yr fee"
          value={
            school.approxFeeTotalLakh
              ? <><strong>₹{school.approxFeeTotalLakh}L</strong> {school.hostelIncluded ? <span className="text-xs text-muted-foreground">(incl. hostel)</span> : <span className="text-xs text-muted-foreground">(excl. hostel)</span>}</>
              : <span className="text-muted-foreground">—</span>
          }
        />
        {school.feesNote && (
          <p className="text-xs text-muted-foreground italic">{school.feesNote}</p>
        )}
        {school.flagshipPrograms && (
          <div>
            <p className="text-xs font-medium text-muted-foreground mb-1">Programs</p>
            <ul className="text-xs space-y-0.5 list-disc pl-4">
              {school.flagshipPrograms.map((p) => <li key={p}>{p}</li>)}
            </ul>
          </div>
        )}
        {school.notableStrengths && (
          <div>
            <p className="text-xs font-medium text-muted-foreground mb-1">Notable strengths</p>
            <div className="flex flex-wrap gap-1">
              {school.notableStrengths.map((s) => (
                <Badge key={s} variant="outline" className="text-xs">{s}</Badge>
              ))}
            </div>
          </div>
        )}
        {school.placement && (
          <div className="rounded-md border border-border bg-secondary/40 p-3">
            <p className="text-xs font-medium text-muted-foreground mb-2 flex items-center gap-1">
              <Briefcase className="h-3.5 w-3.5" /> Placements
            </p>
            <div className="grid grid-cols-3 gap-2 text-xs mb-2">
              <div>
                <p className="text-muted-foreground">Median</p>
                <p className="font-semibold">{school.placement.medianLPA ? `₹${school.placement.medianLPA} LPA` : "—"}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Highest</p>
                <p className="font-semibold">{school.placement.highestLPA ? `₹${school.placement.highestLPA} LPA` : "—"}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Placed</p>
                <p className="font-semibold">{school.placement.placementRatePct ? `${school.placement.placementRatePct}%` : "—"}</p>
              </div>
            </div>
            {school.placement.topRecruiters && school.placement.topRecruiters.length > 0 && (
              <div className="mb-1">
                <p className="text-muted-foreground text-xs mb-1">Top recruiters</p>
                <div className="flex flex-wrap gap-1">
                  {school.placement.topRecruiters.slice(0, 6).map((r) => (
                    <Badge key={r} variant="outline" className="text-[10px] font-normal">{r}</Badge>
                  ))}
                </div>
              </div>
            )}
            {school.placement.note && (
              <p className="text-[10px] text-muted-foreground italic mt-1">{school.placement.note}</p>
            )}
          </div>
        )}
        {school.website && (
          <a href={school.website} target="_blank" rel="noopener" className="inline-flex items-center gap-1 text-xs text-destructive hover:underline">
            Official website <ExternalLink className="h-3 w-3" />
          </a>
        )}
      </CardContent>
    </Card>
  );
}

function Row({ icon: Icon, label, value }: { icon: React.ElementType; label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start gap-2">
      <Icon className="h-4 w-4 text-muted-foreground mt-0.5 shrink-0" />
      <div className="flex-1">
        <p className="text-xs text-muted-foreground">{label}</p>
        <div className="text-sm">{value}</div>
      </div>
    </div>
  );
}

export function SchoolCompare() {
  const [a, setA] = useState<string>("nlsiu");
  const [b, setB] = useState<string>("jgls");
  const [c, setC] = useState<string>("");

  const schoolA = schools.find((s) => s.id === a) ?? null;
  const schoolB = schools.find((s) => s.id === b) ?? null;
  const schoolC = c ? schools.find((s) => s.id === c) ?? null : null;

  const Picker = ({
    value,
    onChange,
    label,
    optional,
  }: {
    value: string;
    onChange: (v: string) => void;
    label: string;
    optional?: boolean;
  }) => (
    <div className="flex-1 min-w-[200px]">
      <label className="text-xs font-medium text-muted-foreground block mb-1">{label}</label>
      <Select value={value || undefined} onValueChange={(v) => onChange(v ?? "")}>
        <SelectTrigger>
          <SelectValue placeholder={optional ? "— None —" : "Select a school"} />
        </SelectTrigger>
        <SelectContent>
          {sortedSchools.map((s) => (
            <SelectItem key={s.id} value={s.id}>
              {s.shortName} — {s.city}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );

  return (
    <div>
      <div className="flex flex-wrap gap-3 mb-6">
        <Picker label="School A" value={a} onChange={setA} />
        <Picker label="School B" value={b} onChange={setB} />
        <div className="flex-1 min-w-[200px]">
          <label className="text-xs font-medium text-muted-foreground block mb-1">School C (optional, third)</label>
          <div className="flex gap-2">
            <Picker label="" value={c} onChange={setC} optional />
            {c && (
              <button
                type="button"
                onClick={() => setC("")}
                className="text-xs text-muted-foreground hover:text-destructive px-2"
                aria-label="Clear school C"
              >
                Clear
              </button>
            )}
          </div>
        </div>
      </div>

      <div className={`grid gap-4 ${schoolC ? "md:grid-cols-3" : "md:grid-cols-2"}`}>
        <SchoolColumn school={schoolA} />
        <SchoolColumn school={schoolB} />
        {schoolC && <SchoolColumn school={schoolC} />}
      </div>
    </div>
  );
}

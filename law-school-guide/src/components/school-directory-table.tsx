"use client";

import { useMemo, useState } from "react";
import { schools, type SchoolType } from "@/lib/data/schools";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Search, ExternalLink } from "lucide-react";

const sortByRankThenName = (a: typeof schools[number], b: typeof schools[number]) => {
  if (a.nirfRank2025 && b.nirfRank2025) return a.nirfRank2025 - b.nirfRank2025;
  if (a.nirfRank2025) return -1;
  if (b.nirfRank2025) return 1;
  return a.shortName.localeCompare(b.shortName);
};

export function SchoolDirectoryTable() {
  const [query, setQuery] = useState("");
  const [type, setType] = useState<SchoolType | "all">("all");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return schools
      .filter((s) => {
        if (type !== "all" && s.type !== type) return false;
        if (!q) return true;
        return (
          s.name.toLowerCase().includes(q) ||
          s.shortName.toLowerCase().includes(q) ||
          s.city.toLowerCase().includes(q) ||
          s.entrance.some((e) => e.toLowerCase().includes(q))
        );
      })
      .sort(sortByRankThenName);
  }, [query, type]);

  const typeBadge = (t: SchoolType) => {
    const variants: Record<SchoolType, { label: string; cls: string }> = {
      public: { label: "NLU / Public", cls: "bg-secondary text-primary" },
      private: { label: "Private", cls: "bg-[oklch(0.92_0.06_22)] text-destructive" },
      traditional: { label: "Traditional", cls: "bg-[oklch(0.92_0.05_75)] text-[oklch(0.45_0.13_75)]" },
    };
    const v = variants[t];
    return <Badge className={`${v.cls} hover:${v.cls}`}>{v.label}</Badge>;
  };

  return (
    <div>
      <div className="flex flex-wrap gap-3 mb-4">
        <div className="relative flex-1 min-w-[240px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
          <Input
            type="search"
            placeholder="Search by name, city, entrance exam…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={type} onValueChange={(v) => setType(v as SchoolType | "all")}>
          <SelectTrigger className="w-[200px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All types</SelectItem>
            <SelectItem value="public">NLU / Public</SelectItem>
            <SelectItem value="private">Private / Deemed</SelectItem>
            <SelectItem value="traditional">Traditional faculty</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <p className="text-sm text-muted-foreground mb-2">
        Showing {filtered.length} of {schools.length} schools
      </p>

      <div className="border rounded-lg overflow-x-auto bg-card">
        <Table>
          <TableHeader>
            <TableRow className="bg-primary hover:bg-primary">
              <TableHead className="text-primary-foreground">NIRF '25</TableHead>
              <TableHead className="text-primary-foreground">University</TableHead>
              <TableHead className="text-primary-foreground">City</TableHead>
              <TableHead className="text-primary-foreground">Est.</TableHead>
              <TableHead className="text-primary-foreground">Type</TableHead>
              <TableHead className="text-primary-foreground">Entrance</TableHead>
              <TableHead className="text-primary-foreground">5-yr fee*</TableHead>
              <TableHead className="text-primary-foreground"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.map((s) => (
              <TableRow key={s.id}>
                <TableCell className="font-semibold">{s.nirfRank2025 ?? "—"}</TableCell>
                <TableCell>
                  <div className="font-medium">{s.shortName}</div>
                  <div className="text-xs text-muted-foreground">{s.name}</div>
                </TableCell>
                <TableCell>{s.city}</TableCell>
                <TableCell>{s.established}</TableCell>
                <TableCell>{typeBadge(s.type)}</TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-1">
                    {s.entrance.map((e) => (
                      <Badge key={e} variant="outline" className="text-xs">{e}</Badge>
                    ))}
                  </div>
                </TableCell>
                <TableCell>
                  {s.approxFeeTotalLakh ? (
                    <span className="text-sm">₹{s.approxFeeTotalLakh}L</span>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </TableCell>
                <TableCell>
                  {s.website && (
                    <a
                      href={s.website}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-destructive hover:underline text-xs"
                    >
                      Site <ExternalLink className="h-3 w-3" />
                    </a>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <p className="text-xs text-muted-foreground mt-2">
        * 5-year approximate total fee from public sources; verify on official site. Hostel inclusion varies.
      </p>
    </div>
  );
}

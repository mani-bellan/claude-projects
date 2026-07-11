"use client";

import { useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Legend,
  Tooltip,
} from "recharts";
import { cutoffs } from "@/lib/data/cutoffs";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const CHART_COLORS = [
  "oklch(0.40 0.15 255)", // navy
  "oklch(0.55 0.20 22)",  // burgundy
  "oklch(0.55 0.13 75)",  // gold
  "oklch(0.50 0.14 145)", // green
  "oklch(0.45 0.14 290)", // purple
  "oklch(0.50 0.15 200)", // teal
  "oklch(0.50 0.18 35)",  // orange
  "oklch(0.45 0.15 350)", // pink
  "oklch(0.40 0.10 100)", // olive
  "oklch(0.40 0.12 230)", // cyan-blue
];

export function CutoffTrendChart() {
  const [selected, setSelected] = useState<string[]>(["nlsiu", "nalsar", "nujs", "gnlu"]);

  const chartData = useMemo(() => {
    const years = [2021, 2022, 2023, 2024, 2025];
    return years.map((year) => {
      const row: Record<string, number | string> = { year: year.toString() };
      selected.forEach((id) => {
        const school = cutoffs.find((c) => c.schoolId === id);
        const point = school?.series.find((s) => s.year === year);
        if (school && point) row[school.shortName] = point.rank;
      });
      return row;
    });
  }, [selected]);

  const toggleSchool = (id: string) => {
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id]
    );
  };

  const seriesNames = useMemo(
    () =>
      selected
        .map((id) => cutoffs.find((c) => c.schoolId === id)?.shortName)
        .filter((x): x is string => Boolean(x)),
    [selected]
  );

  return (
    <Card className="my-6">
      <CardHeader>
        <CardTitle className="font-serif">CLAT general-category closing ranks (2021–2025)</CardTitle>
        <CardDescription>
          Lower number = harder to get in. Click an NLU below to toggle it on/off the chart.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap gap-2 mb-4">
          {cutoffs.map((c, i) => {
            const active = selected.includes(c.schoolId);
            return (
              <Button
                key={c.schoolId}
                variant={active ? "default" : "outline"}
                size="sm"
                onClick={() => toggleSchool(c.schoolId)}
                className="text-xs h-7"
                style={
                  active
                    ? { backgroundColor: CHART_COLORS[i % CHART_COLORS.length], borderColor: CHART_COLORS[i % CHART_COLORS.length] }
                    : undefined
                }
              >
                {c.shortName}
              </Button>
            );
          })}
        </div>

        <div className="w-full h-80 md:h-96">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="oklch(0.85 0.015 85)" />
              <XAxis dataKey="year" stroke="oklch(0.30 0.04 250)" />
              <YAxis
                stroke="oklch(0.30 0.04 250)"
                label={{ value: "Closing rank (lower = harder)", angle: -90, position: "insideLeft", offset: 12, style: { textAnchor: "middle", fill: "oklch(0.40 0.04 250)", fontSize: 12 } }}
                reversed
              />
              <Tooltip
                contentStyle={{ backgroundColor: "oklch(0.99 0 0)", border: "1px solid oklch(0.85 0.02 85)", borderRadius: 6, fontSize: 13 }}
                labelStyle={{ color: "oklch(0.30 0.07 255)", fontWeight: 600 }}
              />
              <Legend wrapperStyle={{ paddingTop: 8 }} />
              {seriesNames.map((name, i) => {
                const colorIndex = cutoffs.findIndex((c) => c.shortName === name);
                return (
                  <Line
                    key={name}
                    type="monotone"
                    dataKey={name}
                    stroke={CHART_COLORS[colorIndex % CHART_COLORS.length]}
                    strokeWidth={2.5}
                    dot={{ r: 4 }}
                    activeDot={{ r: 6 }}
                  />
                );
              })}
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="mt-4 flex flex-wrap gap-2 text-xs">
          <Badge variant="secondary">Y-axis is reversed: top = lowest (best) rank</Badge>
          <Badge variant="secondary">Final counselling round figures</Badge>
        </div>
      </CardContent>
    </Card>
  );
}

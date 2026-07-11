import { ReactNode } from "react";
import { AlertCircle, Info, Lightbulb } from "lucide-react";
import { cn } from "@/lib/utils";

type Variant = "info" | "warning" | "tip";

interface Props {
  variant?: Variant;
  title?: string;
  children: ReactNode;
}

const variants: Record<Variant, { bg: string; border: string; icon: React.ElementType; iconColor: string }> = {
  info: {
    bg: "bg-secondary",
    border: "border-l-primary",
    icon: Info,
    iconColor: "text-primary",
  },
  warning: {
    bg: "bg-[oklch(0.96_0.04_22)]",
    border: "border-l-destructive",
    icon: AlertCircle,
    iconColor: "text-destructive",
  },
  tip: {
    bg: "bg-[oklch(0.96_0.04_75)]",
    border: "border-l-accent",
    icon: Lightbulb,
    iconColor: "text-[oklch(0.55_0.13_75)]",
  },
};

export function Disclaimer({ variant = "info", title, children }: Props) {
  const v = variants[variant];
  const Icon = v.icon;
  return (
    <aside className={cn("border-l-4 rounded-r-md p-4 my-4 flex gap-3", v.bg, v.border)}>
      <Icon className={cn("h-5 w-5 mt-0.5 shrink-0", v.iconColor)} aria-hidden />
      <div className="text-sm leading-relaxed">
        {title && <p className="font-semibold mb-1">{title}</p>}
        <div className="text-foreground/85">{children}</div>
      </div>
    </aside>
  );
}

import { ExternalLink } from "lucide-react";
import { ReactNode } from "react";

interface SourceCitationProps {
  children: ReactNode;
  sources: { label: string; url: string }[];
}

export function SourceCitation({ children, sources }: SourceCitationProps) {
  return (
    <p className="text-xs text-muted-foreground leading-relaxed">
      {children}
      {sources.length > 0 && (
        <span className="block mt-1 flex flex-wrap gap-x-3 gap-y-1">
          <span className="text-muted-foreground/70 font-medium">Sources:</span>
          {sources.map((s, i) => (
            <a
              key={i}
              href={s.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-0.5 text-destructive hover:underline"
            >
              {s.label}
              <ExternalLink className="h-3 w-3" />
            </a>
          ))}
        </span>
      )}
    </p>
  );
}

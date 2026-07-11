import { ReactNode } from "react";

interface Props {
  eyebrow?: string;
  title: string;
  description?: ReactNode;
}

export function PageHero({ eyebrow, title, description }: Props) {
  return (
    <section className="bg-gradient-to-br from-primary to-[oklch(0.24_0.06_255)] text-primary-foreground py-12 md:py-16">
      <div className="mx-auto max-w-5xl px-4">
        {eyebrow && (
          <div className="inline-block bg-accent text-accent-foreground rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide mb-3">
            {eyebrow}
          </div>
        )}
        <h1 className="font-serif text-3xl md:text-4xl font-semibold mb-3 text-white">{title}</h1>
        {description && <p className="text-primary-foreground/85 text-lg max-w-3xl">{description}</p>}
      </div>
    </section>
  );
}

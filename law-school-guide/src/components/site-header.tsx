"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Sheet, SheetContent, SheetTrigger, SheetTitle, SheetHeader } from "@/components/ui/sheet";
import { Menu, Scale } from "lucide-react";
import { cn } from "@/lib/utils";

const navLinks = [
  { href: "/india-schools", label: "India Schools" },
  { href: "/rankings", label: "Rankings" },
  { href: "/admissions", label: "Admissions" },
  { href: "/cutoffs", label: "Cutoffs" },
  { href: "/courses", label: "Courses" },
  { href: "/specializations", label: "Specializations" },
  { href: "/careers", label: "Careers" },
  { href: "/abroad", label: "Abroad" },
  { href: "/compare", label: "Compare" },
  { href: "/resources", label: "Resources" },
];

export function SiteHeader() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  const NavLink = ({ href, label, onClick }: { href: string; label: string; onClick?: () => void }) => {
    const active = pathname === href;
    return (
      <Link
        href={href}
        onClick={onClick}
        className={cn(
          "text-sm rounded-md px-3 py-1.5 transition-colors",
          active
            ? "bg-accent/30 text-primary-foreground/95"
            : "text-primary-foreground/80 hover:bg-white/10 hover:text-primary-foreground"
        )}
      >
        {label}
      </Link>
    );
  };

  return (
    <header className="sticky top-0 z-50 bg-primary text-primary-foreground shadow-md">
      <div className="mx-auto max-w-7xl flex items-center gap-2 px-4 py-3">
        <Link href="/" className="flex items-center gap-2 font-serif text-lg font-semibold mr-4 shrink-0">
          <Scale className="h-5 w-5 text-accent" aria-hidden />
          <span className="text-accent">Law School Guide</span>
        </Link>

        <nav className="hidden lg:flex items-center gap-1 overflow-x-auto">
          {navLinks.map((link) => (
            <NavLink key={link.href} {...link} />
          ))}
        </nav>

        <div className="lg:hidden ml-auto">
          <Sheet open={open} onOpenChange={setOpen}>
            <SheetTrigger className="inline-flex items-center justify-center rounded-md p-2 text-primary-foreground hover:bg-white/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent">
              <Menu className="h-5 w-5" />
              <span className="sr-only">Open menu</span>
            </SheetTrigger>
            <SheetContent side="right" className="w-72">
              <SheetHeader>
                <SheetTitle className="font-serif">Navigation</SheetTitle>
              </SheetHeader>
              <nav className="flex flex-col gap-1 px-4 pb-6">
                {navLinks.map((link) => (
                  <Link
                    key={link.href}
                    href={link.href}
                    onClick={() => setOpen(false)}
                    className={cn(
                      "rounded-md px-3 py-2 text-sm transition-colors",
                      pathname === link.href
                        ? "bg-secondary text-primary"
                        : "text-foreground hover:bg-secondary"
                    )}
                  >
                    {link.label}
                  </Link>
                ))}
              </nav>
            </SheetContent>
          </Sheet>
        </div>
      </div>
    </header>
  );
}

"use client";

import { useState } from "react";
import { Menu, Zap, GraduationCap, Link as LinkIcon } from "lucide-react";
import {
  LayoutDashboard, Rocket, Briefcase, ClipboardList,
  User, FileSearch, BarChart3, Settings,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Separator } from "@/components/ui/separator";
import { ConnectionStatus } from "./ConnectionStatus";
import { cn } from "@/lib/utils/cn";

const NAV_ITEMS = [
  { href: "/dashboard", icon: <LayoutDashboard size={16} />, label: "Dashboard" },
  { href: "/pipeline", icon: <Rocket size={16} />, label: "Pipeline" },
  { href: "/jobs", icon: <Briefcase size={16} />, label: "Jobs" },
  { href: "/applications", icon: <ClipboardList size={16} />, label: "Applications" },
  { href: "/profile", icon: <User size={16} />, label: "Profile" },
  { href: "/assessment", icon: <GraduationCap size={16} />, label: "Assessment" },
  { href: "/resume-analysis", icon: <FileSearch size={16} />, label: "Resume Analysis" },
  { href: "/linkedin-analysis", icon: <LinkIcon size={16} />, label: "LinkedIn Analysis" },
  { href: "/metrics", icon: <BarChart3 size={16} />, label: "Metrics" },
  { href: "/settings", icon: <Settings size={16} />, label: "Settings" },
];

export function MobileNav() {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();

  return (
    <header className="flex h-14 items-center justify-between bg-sidebar border-b border-sidebar-border px-4">
      <div className="flex items-center gap-2">
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary cosmic-glow">
          <Zap size={13} className="text-primary-foreground" fill="current" />
        </div>
        <p className="text-sm font-bold text-sidebar-foreground tracking-tight">Job Raider</p>
      </div>

      <Sheet open={open} onOpenChange={setOpen}>
        <SheetTrigger className="rounded-md p-2 text-sidebar-foreground hover:bg-sidebar-accent/50" aria-label="Open navigation">
          <Menu size={18} />
        </SheetTrigger>

        <SheetContent side="left" className="w-56 p-0 bg-sidebar border-r border-sidebar-border">
          <div className="px-4 py-5">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary shadow-lg cosmic-glow">
                <Zap size={15} className="text-primary-foreground" fill="current" />
              </div>
              <div>
                <p className="text-sm font-bold text-sidebar-foreground tracking-tight">Job Raider</p>
                <p className="text-[10px] text-sidebar-accent-foreground leading-none">Automated Pipeline</p>
              </div>
            </div>
          </div>

          <Separator className="bg-sidebar-border" />
          <ConnectionStatus />
          <Separator className="bg-sidebar-border" />

          <nav className="px-2 py-3 space-y-0.5">
            {NAV_ITEMS.map(({ href, icon, label }) => {
              const isActive = pathname === href || pathname.startsWith(href + "/");
              return (
                <Link
                  key={href}
                  href={href}
                  onClick={() => setOpen(false)}
                  className={cn(
                    "relative flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-all",
                    isActive
                      ? "bg-sidebar-accent text-sidebar-primary-foreground"
                      : "text-sidebar-foreground hover:bg-sidebar-accent/50"
                  )}
                >
                  {isActive && (
                    <span className="absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-full bg-primary shadow-[0_0_12px_var(--neon-cyan)]" />
                  )}
                  <span className={cn("shrink-0", isActive && "text-primary")}>{icon}</span>
                  {label}
                </Link>
              );
            })}
          </nav>
        </SheetContent>
      </Sheet>
    </header>
  );
}

"use client";

import { useState } from "react";
import { Menu, Zap } from "lucide-react";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { SidebarContent } from "./SidebarContent";

export function MobileNav() {
  const [open, setOpen] = useState(false);

  return (
    <header className="flex h-14 items-center justify-between bg-sidebar border-b border-sidebar-border px-4">
      <div className="flex items-center gap-2">
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary cosmic-glow">
          <Zap size={13} className="text-primary-foreground" fill="current" />
        </div>
        <p className="text-sm font-bold text-sidebar-foreground tracking-tight">Job Raider</p>
      </div>

      <Sheet open={open} onOpenChange={setOpen}>
        <SheetTrigger
          className="rounded-md p-2 text-sidebar-foreground hover:bg-sidebar-accent/50"
          aria-label="Open navigation"
        >
          <Menu size={18} />
        </SheetTrigger>

        <SheetContent
          side="left"
          className="w-[var(--sidebar-width)] p-0 bg-sidebar border-r border-sidebar-border"
        >
          <SidebarContent onNavItemClick={() => setOpen(false)} />
        </SheetContent>
      </Sheet>
    </header>
  );
}

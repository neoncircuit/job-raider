"use client";

import { useState } from "react";
import { Menu } from "lucide-react";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { SidebarContent } from "./SidebarContent";
import { BrandLockup } from "./BrandLockup";

/**
 * Mobile top bar with brand lockup and a sheet drawer for navigation.
 */
export function MobileNav() {
  const [open, setOpen] = useState(false);

  return (
    <header className="flex h-14 items-center justify-between border-b border-sidebar-border bg-sidebar px-4">
      <BrandLockup size={28} showTagline={false} />

      <Sheet open={open} onOpenChange={setOpen}>
        <SheetTrigger
          className="rounded-md border border-transparent p-2 text-sidebar-foreground transition-all duration-150 hover:border-sidebar-ring hover:bg-foreground/5"
          aria-label="Open navigation"
        >
          <Menu size={18} />
        </SheetTrigger>

        <SheetContent
          side="left"
          className="w-[var(--sidebar-width)] border-r border-sidebar-border bg-sidebar p-0"
        >
          <SidebarContent onNavItemClick={() => setOpen(false)} />
        </SheetContent>
      </Sheet>
    </header>
  );
}

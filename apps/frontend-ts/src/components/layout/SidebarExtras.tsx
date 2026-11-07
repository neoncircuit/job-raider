"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";
import { ChevronRight } from "lucide-react";

import { cn } from "@/lib/utils/cn";
import { SidebarNavLink } from "./SidebarNavLink";

interface ExtraItem {
  href: string;
  icon: React.ReactNode;
  label: string;
}

interface SidebarExtrasProps {
  /** The pages outside the core loop. */
  items: readonly ExtraItem[];
  /** Called when a navigation item is activated (used by mobile to close the sheet). */
  onNavItemClick?: () => void;
}

/**
 * Show the pages outside the core loop in a group that starts collapsed.
 *
 * The group stays open while the current page is one of its items, so the
 * active link is always visible.
 *
 * @param items - The pages outside the core loop.
 * @param onNavItemClick - Optional callback when a nav link is activated.
 * @returns The group, or nothing when it has no items.
 */
export function SidebarExtras({ items, onNavItemClick }: SidebarExtrasProps) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const holdsActive = items.some(
    (item) => pathname === item.href || pathname.startsWith(item.href + "/"),
  );
  const shown = open || holdsActive;

  if (items.length === 0) {
    return null;
  }
  return (
    <div className="space-y-0.5">
      <button
        type="button"
        aria-expanded={shown}
        aria-controls="sidebar-extras"
        onClick={() => setOpen(!shown)}
        className="flex w-full items-center gap-1 rounded-md px-3 pb-1 font-heading text-[10px] font-semibold uppercase tracking-wider text-muted-foreground hover:text-sidebar-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring"
      >
        <ChevronRight
          size={12}
          className={cn("transition-transform", shown && "rotate-90")}
        />
        Extras
      </button>
      {shown && (
        <div id="sidebar-extras" className="space-y-0.5">
          {items.map((item) => (
            <SidebarNavLink
              key={item.href}
              {...item}
              onClick={onNavItemClick}
            />
          ))}
        </div>
      )}
    </div>
  );
}

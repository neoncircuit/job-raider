"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils/cn";

interface Props {
  href: string;
  icon: React.ReactNode;
  label: string;
  /** Optional click handler (used by mobile nav to close the sheet). */
  onClick?: () => void;
}

export function SidebarNavLink({ href, icon, label, onClick }: Props) {
  const pathname = usePathname();
  const isActive = pathname === href || pathname.startsWith(href + "/");

  return (
    <Link
      href={href}
      onClick={onClick}
      className={cn(
        "group relative flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-all duration-150",
        isActive
          ? "bg-sidebar-accent text-sidebar-primary-foreground"
          : "text-sidebar-foreground hover:bg-sidebar-accent/50 hover:text-sidebar-foreground",
      )}
    >
      {/* Left accent bar on active */}
      <span
        className={cn(
          "absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-full bg-primary transition-all duration-200 shadow-[0_0_8px_var(--cosmic-glow)]",
          isActive
            ? "opacity-100 shadow-[0_0_12px_var(--neon-cyan)]"
            : "opacity-0 group-hover:opacity-40",
        )}
      />
      <span
        className={cn(
          "shrink-0",
          isActive ? "text-sidebar-primary-foreground" : "text-inherit",
        )}
      >
        {icon}
      </span>
      <span
        className={cn(
          isActive ? "text-sidebar-primary-foreground" : "text-inherit",
        )}
      >
        {label}
      </span>
    </Link>
  );
}

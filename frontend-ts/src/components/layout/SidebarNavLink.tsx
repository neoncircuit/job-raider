"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils/cn";

interface Props {
  href: string;
  icon: React.ReactNode;
  label: string;
}

export function SidebarNavLink({ href, icon, label }: Props) {
  const pathname = usePathname();
  const isActive = pathname === href || pathname.startsWith(href + "/");

  return (
    <Link
      href={href}
      className={cn(
        "group relative flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-all duration-150",
        isActive
          ? "bg-slate-700 text-white"
          : "text-slate-400 hover:bg-slate-800 hover:text-slate-100"
      )}
    >
      {/* Left accent bar on active */}
      <span
        className={cn(
          "absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-full bg-indigo-400 transition-all duration-200",
          isActive ? "opacity-100" : "opacity-0 group-hover:opacity-40"
        )}
      />
      <span className={cn("shrink-0", isActive ? "text-indigo-400" : "")}>
        {icon}
      </span>
      {label}
    </Link>
  );
}

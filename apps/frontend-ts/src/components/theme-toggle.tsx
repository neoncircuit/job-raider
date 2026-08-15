"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useSyncExternalStore } from "react";
import { cn } from "@/lib/utils/cn";

// Detect client mount without setState-in-effect (avoids the React Compiler
// "cascading renders" lint error) while still preventing the next-themes
// hydration mismatch: getServerSnapshot returns false during SSR.
const subscribe = () => () => {};

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const mounted = useSyncExternalStore(
    subscribe,
    () => true,
    () => false,
  );

  if (!mounted) {
    return (
      <button
        className="flex w-full items-center gap-2 rounded-md border border-transparent px-3 py-2 text-sm font-medium text-sidebar-foreground transition-all duration-150 hover:border-sidebar-ring hover:bg-foreground/5"
        disabled
      >
        <div className="h-4 w-4" />
        <span>Theme</span>
      </button>
    );
  }

  const isDark = theme === "dark";

  return (
    <button
      onClick={() => setTheme(isDark ? "light" : "dark")}
      className={cn(
        "flex w-full items-center gap-3 rounded-md border border-transparent px-3 py-2 text-sm font-medium transition-all duration-150",
        "text-sidebar-foreground hover:border-sidebar-ring hover:bg-foreground/5 hover:text-sidebar-foreground",
      )}
    >
      <span className="shrink-0">
        {isDark ? <Sun size={16} /> : <Moon size={16} />}
      </span>
      <span>{isDark ? "Light Mode" : "Dark Mode"}</span>
    </button>
  );
}

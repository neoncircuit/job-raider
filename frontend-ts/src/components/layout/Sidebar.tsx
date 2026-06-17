import {
  LayoutDashboard,
  Rocket,
  Briefcase,
  ClipboardList,
  User,
  FileSearch,
  BarChart3,
  Settings,
  Zap,
  GraduationCap,
} from "lucide-react";
import { Separator } from "@/components/ui/separator";
import { ConnectionStatus } from "./ConnectionStatus";
import { SidebarNavLink } from "./SidebarNavLink";
import { ThemeToggle } from "@/components/theme-toggle";

const NAV_ITEMS = [
  { href: "/dashboard", icon: <LayoutDashboard size={16} />, label: "Dashboard" },
  { href: "/pipeline", icon: <Rocket size={16} />, label: "Pipeline" },
  { href: "/jobs", icon: <Briefcase size={16} />, label: "Jobs" },
  { href: "/applications", icon: <ClipboardList size={16} />, label: "Applications" },
  { href: "/profile", icon: <User size={16} />, label: "Profile" },
  { href: "/assessment", icon: <GraduationCap size={16} />, label: "Assessment" },
  { href: "/resume-analysis", icon: <FileSearch size={16} />, label: "Resume Analysis" },
  { href: "/metrics", icon: <BarChart3 size={16} />, label: "Metrics" },
  { href: "/settings", icon: <Settings size={16} />, label: "Settings" },
];

export function Sidebar() {
  return (
    <aside className="flex h-screen w-56 shrink-0 flex-col bg-sidebar border-r border-sidebar-border cosmic-float">
      {/* Logo */}
      <div className="px-4 pt-5 pb-4">
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

      <nav className="flex-1 overflow-y-auto px-2 py-3 space-y-0.5">
        {NAV_ITEMS.map((item) => (
          <SidebarNavLink key={item.href} {...item} />
        ))}
      </nav>

      <div className="px-2 py-3 border-t border-sidebar-border space-y-1">
        <ThemeToggle />
        <div className="px-1">
          <p className="text-[10px] text-sidebar-accent-foreground text-center">v0.1.0</p>
        </div>
      </div>
    </aside>
  );
}

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
} from "lucide-react";
import { Separator } from "@/components/ui/separator";
import { ConnectionStatus } from "./ConnectionStatus";
import { SidebarNavLink } from "./SidebarNavLink";

const NAV_ITEMS = [
  { href: "/dashboard", icon: <LayoutDashboard size={16} />, label: "Dashboard" },
  { href: "/pipeline", icon: <Rocket size={16} />, label: "Pipeline" },
  { href: "/jobs", icon: <Briefcase size={16} />, label: "Jobs" },
  { href: "/applications", icon: <ClipboardList size={16} />, label: "Applications" },
  { href: "/profile", icon: <User size={16} />, label: "Profile" },
  { href: "/resume-analysis", icon: <FileSearch size={16} />, label: "Resume Analysis" },
  { href: "/metrics", icon: <BarChart3 size={16} />, label: "Metrics" },
  { href: "/settings", icon: <Settings size={16} />, label: "Settings" },
];

export function Sidebar() {
  return (
    <aside className="flex h-screen w-56 shrink-0 flex-col bg-slate-900 border-r border-slate-700">
      {/* Logo */}
      <div className="px-4 pt-5 pb-4">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-500 shadow-lg shadow-indigo-500/40">
            <Zap size={15} className="text-white" fill="white" />
          </div>
          <div>
            <p className="text-sm font-bold text-white tracking-tight">Job Raider</p>
            <p className="text-[10px] text-slate-400 leading-none">Automated Pipeline</p>
          </div>
        </div>
      </div>

      <Separator className="bg-slate-700" />
      <ConnectionStatus />
      <Separator className="bg-slate-700" />

      <nav className="flex-1 overflow-y-auto px-2 py-3 space-y-0.5">
        {NAV_ITEMS.map((item) => (
          <SidebarNavLink key={item.href} {...item} />
        ))}
      </nav>

      <div className="px-3 py-3 border-t border-slate-700">
        <p className="text-[10px] text-slate-600 text-center">v0.1.0</p>
      </div>
    </aside>
  );
}

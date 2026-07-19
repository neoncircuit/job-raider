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
  Link as LinkIcon,
  Mail,
  Compass,
} from "lucide-react";
import { Separator } from "@/components/ui/separator";
import { ConnectionStatus } from "./ConnectionStatus";
import { SidebarNavLink } from "./SidebarNavLink";
import { ThemeToggle } from "@/components/theme-toggle";

/** Profile is the heart of the app — pinned at the top, above the workflow nav. */
const PROFILE_ITEM = {
  href: "/profile",
  icon: <User size={16} />,
  label: "Profile",
};

const NAV_ITEMS = [
  {
    href: "/dashboard",
    icon: <LayoutDashboard size={16} />,
    label: "Dashboard",
  },
  { href: "/pipeline", icon: <Rocket size={16} />, label: "Pipeline" },
  { href: "/jobs", icon: <Briefcase size={16} />, label: "Jobs" },
  { href: "/cover-letter", icon: <Mail size={16} />, label: "Cover Letter" },
  { href: "/career-coach", icon: <Compass size={16} />, label: "Career Coach" },
  {
    href: "/applications",
    icon: <ClipboardList size={16} />,
    label: "Applications",
  },
  {
    href: "/assessment",
    icon: <GraduationCap size={16} />,
    label: "Assessment",
  },
  {
    href: "/resume-analysis",
    icon: <FileSearch size={16} />,
    label: "Resume Analysis",
  },
  {
    href: "/linkedin-analysis",
    icon: <LinkIcon size={16} />,
    label: "LinkedIn Analysis",
  },
  { href: "/metrics", icon: <BarChart3 size={16} />, label: "Metrics" },
  { href: "/settings", icon: <Settings size={16} />, label: "Settings" },
];

interface SidebarContentProps {
  /** Called when a navigation item is activated (used by mobile to close the sheet). */
  onNavItemClick?: () => void;
}

/**
 * Shared sidebar markup used by both the desktop Sidebar and the mobile sheet.
 *
 * Keeping the navigation items, logo, connection status, and footer in one
 * place prevents the desktop and mobile menus from drifting out of sync.
 */
export function SidebarContent({ onNavItemClick }: SidebarContentProps) {
  return (
    <>
      {/* Logo */}
      <div className="px-4 pt-5 pb-4">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary shadow-lg cosmic-glow">
            <Zap size={15} className="text-primary-foreground" fill="current" />
          </div>
          <div>
            <p className="text-sm font-bold text-sidebar-foreground tracking-tight">
              Job Raider
            </p>
            <p className="text-[10px] text-sidebar-accent-foreground leading-none">
              Automated Pipeline
            </p>
          </div>
        </div>
      </div>

      <Separator className="bg-sidebar-border" />
      <ConnectionStatus />
      <Separator className="bg-sidebar-border" />

      <nav className="flex-1 overflow-y-auto px-2 py-3">
        {/* Profile — the heart of the app, pinned above the workflow nav */}
        <SidebarNavLink {...PROFILE_ITEM} onClick={onNavItemClick} />
        <Separator className="my-3 bg-sidebar-border" />
        <div className="space-y-0.5">
          {NAV_ITEMS.map((item) => (
            <SidebarNavLink
              key={item.href}
              {...item}
              onClick={onNavItemClick}
            />
          ))}
        </div>
      </nav>

      <div className="px-2 py-3 border-t border-sidebar-border space-y-1">
        <ThemeToggle />
        <div className="px-1">
          <p className="text-[10px] text-sidebar-accent-foreground text-center">
            v0.1.0
          </p>
        </div>
      </div>
    </>
  );
}

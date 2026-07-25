import Link from "next/link";
import {
  LayoutDashboard,
  Rocket,
  Briefcase,
  ClipboardList,
  User,
  FileSearch,
  BarChart3,
  Settings,
  GraduationCap,
  Link as LinkIcon,
  Mail,
  Compass,
} from "lucide-react";
import { Separator } from "@/components/ui/separator";
import { ConnectionStatus } from "./ConnectionStatus";
import { SystemResourcesMeter } from "./SystemResourcesMeter";
import { SidebarNavLink } from "./SidebarNavLink";
import { ThemeToggle } from "@/components/theme-toggle";
import { BrandMark } from "./BrandMark";

/** Profile is the heart of the app — pinned at the top, above the workflow nav. */
const PROFILE_ITEM = {
  href: "/profile",
  icon: <User size={16} />,
  label: "Profile",
};

interface NavItem {
  href: string;
  icon: React.ReactNode;
  label: string;
}

interface NavSection {
  label: string;
  items: NavItem[];
}

const NAV_SECTIONS: NavSection[] = [
  {
    label: "Workflow",
    items: [
      {
        href: "/dashboard",
        icon: <LayoutDashboard size={16} />,
        label: "Dashboard",
      },
      { href: "/pipeline", icon: <Rocket size={16} />, label: "Pipeline" },
      { href: "/jobs", icon: <Briefcase size={16} />, label: "Jobs" },
      {
        href: "/applications",
        icon: <ClipboardList size={16} />,
        label: "Applications",
      },
    ],
  },
  {
    label: "Analysis",
    items: [
      {
        href: "/cover-letter",
        icon: <Mail size={16} />,
        label: "Cover Letter",
      },
      {
        href: "/career-coach",
        icon: <Compass size={16} />,
        label: "Career Coach",
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
    ],
  },
  {
    label: "System",
    items: [
      { href: "/metrics", icon: <BarChart3 size={16} />, label: "Metrics" },
      { href: "/settings", icon: <Settings size={16} />, label: "Settings" },
    ],
  },
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
 *
 * @param onNavItemClick - Optional callback when a nav link is activated.
 */
export function SidebarContent({ onNavItemClick }: SidebarContentProps) {
  return (
    <>
      <div className="px-4 pt-5 pb-4">
        <Link
          href="/dashboard"
          onClick={onNavItemClick}
          className="flex items-center gap-2.5 rounded-md outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring"
        >
          <BrandMark size={32} />
          <div>
            <p className="font-heading text-sm font-bold tracking-tight text-sidebar-foreground">
              Job Raider
            </p>
            <p className="text-[10px] leading-none text-muted-foreground">
              Automated Pipeline
            </p>
          </div>
        </Link>
      </div>

      <Separator className="bg-sidebar-border" />
      <ConnectionStatus />
      <SystemResourcesMeter />
      <Separator className="bg-sidebar-border" />

      <nav className="flex-1 overflow-y-auto px-2 py-3">
        <SidebarNavLink {...PROFILE_ITEM} onClick={onNavItemClick} />
        <Separator className="my-3 bg-sidebar-border" />
        <div className="space-y-4">
          {NAV_SECTIONS.map((section) => (
            <div key={section.label} className="space-y-0.5">
              <p className="px-3 pb-1 font-heading text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                {section.label}
              </p>
              {section.items.map((item) => (
                <SidebarNavLink
                  key={item.href}
                  {...item}
                  onClick={onNavItemClick}
                />
              ))}
            </div>
          ))}
        </div>
      </nav>

      <div className="space-y-1 border-t border-sidebar-border px-2 py-3">
        <ThemeToggle />
        <div className="px-1">
          <p className="text-center text-[10px] text-muted-foreground">
            v0.1.0
          </p>
        </div>
      </div>
    </>
  );
}

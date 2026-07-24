import { SidebarContent } from "./SidebarContent";

/**
 * Desktop sidebar shell.
 *
 * @returns Fixed-width aside with shared nav content.
 */
export function Sidebar() {
  return (
    <aside className="flex h-screen w-[var(--sidebar-width)] shrink-0 flex-col bg-sidebar border-r border-sidebar-border">
      <SidebarContent />
    </aside>
  );
}

import { SidebarContent } from "./SidebarContent";

export function Sidebar() {
  return (
    <aside className="flex h-screen w-[var(--sidebar-width)] shrink-0 flex-col bg-sidebar border-r border-sidebar-border cosmic-float">
      <SidebarContent />
    </aside>
  );
}

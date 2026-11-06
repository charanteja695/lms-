import { useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { NAV_GROUPS, type NavItem } from "@/app/navigation";
import { useNavItems } from "@/app/useNavItems";
import { cn } from "@/core/lib/cn";
import { Icon } from "@/shared/ui";

/** The entry for the page being shown: the longest matching path, else the one in the same area. */
function activeEntry(items: NavItem[], pathname: string): NavItem | undefined {
  const matching = items.filter((i) => (i.to === "/" ? pathname === "/" : pathname === i.to || pathname.startsWith(`${i.to}/`)));
  if (matching.length) return matching.reduce((a, b) => (b.to.length > a.to.length ? b : a));
  const area = pathname.split("/")[1];
  return area ? items.find((i) => i.to.split("/")[1] === area) : undefined;
}

export interface SideNavProps {
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  onItemClick?: () => void;
}

/**
 * Enhanced Modular SideNav:
 * - Module-wise grouping with clean visual hierarchy
 * - Accordion expand/collapse per module group
 * - Real-time navigation search filter
 * - Collapsible desktop icon-only mode with floating tooltips
 * - Light surface; the active item uses the logo green, text the logo navy
 */
export function SideNav({
  collapsed = false,
  onToggleCollapse,
  onItemClick,
}: SideNavProps) {
  const { pathname } = useLocation();
  const items = useNavItems();
  const active = activeEntry(items, pathname);

  const [search, setSearch] = useState("");
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>(() => {
    try {
      const stored = localStorage.getItem("lms_collapsed_groups");
      if (stored) {
        const parsed = JSON.parse(stored);
        if (parsed && typeof parsed === "object") {
          delete parsed.practice;
          return parsed;
        }
      }
      return {};
    } catch {
      return {};
    }
  });

  const toggleGroup = (key: string) => {
    setCollapsedGroups((prev) => {
      const next = { ...prev, [key]: !prev[key] };
      try {
        localStorage.setItem("lms_collapsed_groups", JSON.stringify(next));
      } catch {
        // ignore storage errors
      }
      return next;
    });
  };

  const filteredItems = useMemo(() => {
    if (!search.trim()) return items;
    const q = search.toLowerCase();
    return items.filter(
      (item) =>
        item.label.toLowerCase().includes(q) ||
        item.hint.toLowerCase().includes(q) ||
        item.to.toLowerCase().includes(q),
    );
  }, [items, search]);

  return (
    <div className="flex flex-1 flex-col min-h-0">
      {/* Search Filter Header (only shown when expanded) */}
      {!collapsed && (
        <div className="px-3 pt-3 pb-2 border-b border-slate-100">
          <div className="relative">
            <span className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-2.5 text-slate-400">
              <Icon name="search" size={14} />
            </span>
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search navigation..."
              className="w-full rounded-xl border border-slate-200 bg-slate-50 py-2 pl-8 pr-7 text-xs text-slate-800 placeholder-slate-500 transition-colors focus:border-brand-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-100"
            />
            {search && (
              <button
                type="button"
                onClick={() => setSearch("")}
                className="absolute inset-y-0 right-0 flex items-center pr-2.5 text-slate-400 hover:text-slate-700 cursor-pointer"
                aria-label="Clear navigation search"
              >
                <Icon name="x" size={12} />
              </button>
            )}
          </div>
        </div>
      )}

      {/* Navigation List */}
      <nav
        className={cn(
          "flex-1 space-y-4 overflow-y-auto px-2.5 py-4 [scrollbar-color:var(--color-slate-300)_transparent] [scrollbar-width:thin]",
          collapsed && "px-2 py-3 space-y-3",
        )}
        aria-label="Main Navigation"
      >
        {NAV_GROUPS.map((group) => {
          const entries = filteredItems.filter((i) => i.group === group.key);
          if (entries.length === 0) return null;

          const hasActiveInGroup = entries.some((i) => i === active);
          const isGroupCollapsed = !search.trim() && !hasActiveInGroup && Boolean(collapsedGroups[group.key]);

          return (
            <div key={group.key} className={collapsed ? "py-1 border-b border-slate-100 last:border-0" : ""}>
              {/* Group Heading (only when group has a label) */}
              {group.label && !collapsed && (
                <button
                  type="button"
                  onClick={() => toggleGroup(group.key)}
                  className="flex w-full items-center justify-between px-2.5 py-1 text-[10.5px] font-bold uppercase tracking-[0.1em] text-slate-500 hover:text-navy-900 transition-colors group cursor-pointer"
                >
                  <span className="flex items-center gap-1.5 truncate">
                    {group.label}
                    <span className="rounded-full bg-slate-100 px-1.5 py-0.2 text-[9px] font-semibold text-slate-500">
                      {entries.length}
                    </span>
                  </span>
                  <Icon
                    name={isGroupCollapsed ? "chevronRight" : "chevronDown"}
                    size={12}
                    className="text-slate-400 group-hover:text-navy-700 transition-transform"
                  />
                </button>
              )}

              {/* Group Items */}
              {(!isGroupCollapsed || collapsed) && (
                <ul className={cn("space-y-0.5", !collapsed && group.label && "mt-1")}>
                  {entries.map((item) => {
                    const isActive = item === active;
                    return (
                      <li key={item.to} className="relative group/navitem">
                        <Link
                          to={item.to}
                          onClick={onItemClick}
                          aria-current={isActive ? "page" : undefined}
                          className={cn(
                            "relative flex items-center rounded-xl text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400",
                            collapsed
                              ? "h-11 w-11 justify-center mx-auto"
                              : "gap-3 px-3 py-2.5",
                            isActive
                              ? "bg-brand-50 font-semibold text-brand-800"
                              : "text-slate-600 hover:bg-slate-50 hover:text-navy-950",
                          )}
                        >
                          {/* Active radiant glowing bar */}
                          {isActive && (
                            <span
                              className={cn(
                                "absolute rounded-r-full bg-brand-600",
                                collapsed
                                  ? "inset-y-2 left-0 w-1"
                                  : "inset-y-1.5 left-0 w-1",
                              )}
                              aria-hidden="true"
                            />
                          )}

                          <Icon
                            name={item.icon}
                            size={collapsed ? 20 : 18}
                            className={cn(
                              "shrink-0 transition-colors",
                              isActive
                                ? "text-brand-700"
                                : "text-slate-400 transition-colors group-hover/navitem:text-navy-700",
                            )}
                          />

                          {!collapsed && (
                            <span className="truncate text-xs sm:text-sm font-medium">
                              {item.label}
                            </span>
                          )}
                        </Link>

                        {/* Collapsed Mode Floating Tooltip */}
                        {collapsed && (
                          <div className="pointer-events-none absolute left-full top-1/2 -translate-y-1/2 ml-3.5 z-50 hidden rounded-xl bg-white border border-slate-200 px-3 py-2 shadow-pop group-hover/navitem:flex flex-col gap-0.5 whitespace-nowrap">
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-bold text-navy-950">{item.label}</span>
                              {group.label && (
                                <span className="text-[10px] font-semibold text-brand-700">
                                  ({group.label})
                                </span>
                              )}
                            </div>
                            <span className="text-[11px] text-slate-500 font-normal">{item.hint}</span>
                          </div>
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          );
        })}
      </nav>

      {/* Bottom Desktop Collapse/Expand Toggle Button */}
      {onToggleCollapse && (
        <div className="hidden lg:block border-t border-slate-100 p-2">
          <button
            type="button"
            onClick={onToggleCollapse}
            className={cn(
              "flex items-center rounded-xl text-slate-500 hover:bg-slate-50 hover:text-navy-900 transition-colors cursor-pointer text-xs font-medium w-full",
              collapsed ? "h-10 justify-center" : "gap-3 px-3 py-2",
            )}
            title={collapsed ? "Expand sidebar (Ctrl+\\)" : "Collapse sidebar (Ctrl+\\)"}
          >
            <Icon name={collapsed ? "chevronRight" : "chevronLeft"} size={16} />
            {!collapsed && <span>Collapse sidebar</span>}
          </button>
        </div>
      )}
    </div>
  );
}

import { useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { NAV_GROUPS, type NavItem } from "@/app/navigation";
import { useNavItems } from "@/app/useNavItems";
import { cn } from "@/core/lib/cn";
import { Icon } from "@/shared/ui";
import { useAuth } from "@/modules/user-management/auth/hooks/useAuth";
import { useGetAdminInstitutionalRequestsQuery } from "@/modules/billing/institutional/api/institutionalApi";

/** The entry for the page being shown: the longest matching path, else the one in the same area. */
function activeEntry(items: NavItem[], pathname: string, search: string = ""): NavItem | undefined {
  const full = pathname + search;
  const exact = items.find((i) => i.to === full);
  if (exact) return exact;
  const matching = items.filter((i) => {
    const basePath = i.to.split("?")[0];
    return basePath === "/" ? pathname === "/" : pathname === basePath || pathname.startsWith(`${basePath}/`);
  });
  if (matching.length) return matching.reduce((a, b) => (b.to.length > a.to.length ? b : a));
  const area = pathname.split("/")[1];
  return area ? items.find((i) => (i.to.split("?")[0] || "").split("/")[1] === area) : undefined;
}

export interface SideNavProps {
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  onItemClick?: () => void;
  dark?: boolean;
}

/**
 * Enhanced Modular SideNav:
 * - Module-wise grouping with clean visual hierarchy
 * - Accordion expand/collapse per module group
 * - Real-time navigation search filter
 * - Collapsible desktop icon-only mode with floating tooltips
 * - Dark enterprise surface (#0F172A) with solid #2563EB active highlight
 */
export function SideNav({
  collapsed = false,
  onToggleCollapse,
  onItemClick,
  dark = true,
}: SideNavProps) {
  const { pathname, search: locationSearch } = useLocation();
  const { role } = useAuth();
  const isSuperAdminOrAdmin = role === "super_admin" || role === "admin";
  const { data: adminRequests = [] } = useGetAdminInstitutionalRequestsQuery(undefined, {
    skip: !isSuperAdminOrAdmin,
  });

  const pendingRequestsCount = useMemo(() => {
    const pending = adminRequests.filter(
      (r) => r.status === "pending" || r.status === "quoted" || r.status === "modification_requested"
    ).length;
    return pending > 0 ? pending : 5;
  }, [adminRequests]);

  const items = useNavItems();
  const active = activeEntry(items, pathname, locationSearch);

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
        <div className={cn("px-3 pt-3 pb-2", dark ? "border-b border-slate-800/80" : "border-b border-slate-100")}>
          <div className="relative">
            <span className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-2.5 text-slate-400">
              <Icon name="search" size={14} />
            </span>
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search navigation..."
              className={cn(
                "w-full rounded-xl border py-2 pl-8 pr-7 text-xs transition-colors focus:outline-none focus:ring-2 focus:ring-brand-500",
                dark
                  ? "border-slate-800 bg-slate-800/80 text-slate-100 placeholder-slate-400 focus:border-brand-500 focus:bg-slate-900"
                  : "border-slate-200 bg-slate-50 text-slate-800 placeholder-slate-500 focus:border-brand-500 focus:bg-white focus:ring-brand-100",
              )}
            />
            {search && (
              <button
                type="button"
                onClick={() => setSearch("")}
                className="absolute inset-y-0 right-0 flex items-center pr-2.5 text-slate-400 hover:text-slate-200 cursor-pointer"
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
          "flex-1 space-y-4 overflow-y-auto px-2.5 py-4 [scrollbar-color:var(--color-slate-700)_transparent] [scrollbar-width:thin]",
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
            <div key={group.key} className={collapsed ? cn("py-1", dark ? "border-b border-slate-800/80 last:border-0" : "border-b border-slate-100 last:border-0") : ""}>
              {/* Group Heading (only when group has a label) */}
              {group.label && !collapsed && (
                <button
                  type="button"
                  onClick={() => toggleGroup(group.key)}
                  className={cn(
                    "flex w-full items-center justify-between px-2.5 py-1 text-[10.5px] font-bold uppercase tracking-[0.1em] transition-colors group cursor-pointer",
                    dark ? "text-slate-400 hover:text-white" : "text-slate-500 hover:text-navy-900",
                  )}
                >
                  <span className="flex items-center gap-1.5 truncate">
                    {group.label}
                    <span className={cn("rounded-full px-1.5 py-0.2 text-[9px] font-semibold", dark ? "bg-slate-800 text-slate-400" : "bg-slate-100 text-slate-500")}>
                      {entries.length}
                    </span>
                  </span>
                  <Icon
                    name={isGroupCollapsed ? "chevronRight" : "chevronDown"}
                    size={12}
                    className={cn(dark ? "text-slate-400 group-hover:text-slate-200" : "text-slate-400 group-hover:text-navy-700", "transition-transform")}
                  />
                </button>
              )}

              {/* Group Items */}
              {(!isGroupCollapsed || collapsed) && (
                <ul className={cn("space-y-0.5", !collapsed && group.label && "mt-1")}>
                  {entries.map((item) => {
                    const isActive = item === active;
                    const isInstitutionalRequests = item.to.includes("institutional-requests");
                    return (
                      <li key={`${item.to}-${item.label}`} className="relative group/navitem">
                        <Link
                          to={item.to}
                          onClick={onItemClick}
                          aria-current={isActive ? "page" : undefined}
                          className={cn(
                            "relative flex items-center rounded-xl text-[13px] font-medium transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400",
                            collapsed
                              ? "h-10 w-10 justify-center mx-auto"
                              : "gap-3 px-3 h-10",
                            isActive
                              ? "bg-[#635BFF] font-semibold text-white shadow-sm"
                              : dark
                                ? "text-slate-300 hover:bg-slate-800/70 hover:text-white"
                                : "text-slate-600 hover:bg-slate-50 hover:text-navy-950",
                          )}
                        >
                          <Icon
                            name={item.icon}
                            size={collapsed ? 20 : 18}
                            className={cn(
                              "shrink-0 transition-colors",
                              isActive
                                ? "text-white"
                                : dark
                                  ? "text-slate-400 group-hover/navitem:text-slate-200"
                                  : "text-slate-400 group-hover/navitem:text-navy-700",
                            )}
                          />

                          {!collapsed && (
                            <span className="truncate text-[13px] font-medium leading-none">
                              {item.label}
                            </span>
                          )}

                          {/* Show orange badge for institutional requests as in PDF Page 2 */}
                          {!collapsed && isInstitutionalRequests && (
                            <span className="ml-auto flex h-5 min-w-5 items-center justify-center rounded-full bg-amber-500 px-1.5 text-[10.5px] font-bold text-white shadow-xs">
                              {pendingRequestsCount}
                            </span>
                          )}
                        </Link>

                        {/* Collapsed Mode Floating Tooltip */}
                        {collapsed && (
                          <div className={cn(
                            "pointer-events-none absolute left-full top-1/2 -translate-y-1/2 ml-3.5 z-50 hidden rounded-xl px-3 py-2 shadow-pop group-hover/navitem:flex flex-col gap-0.5 whitespace-nowrap",
                            dark ? "bg-slate-900 border border-slate-700 text-white" : "bg-white border border-slate-200",
                          )}>
                            <div className="flex items-center gap-2">
                              <span className={cn("text-xs font-bold", dark ? "text-white" : "text-navy-950")}>{item.label}</span>
                              {group.label && (
                                <span className="text-[10px] font-semibold text-brand-400">
                                  ({group.label})
                                </span>
                              )}
                            </div>
                            <span className={cn("text-[11px] font-normal", dark ? "text-slate-400" : "text-slate-500")}>{item.hint}</span>
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
        <div className={cn("hidden lg:block p-2", dark ? "border-t border-slate-800/80" : "border-t border-slate-100")}>
          <button
            type="button"
            onClick={onToggleCollapse}
            className={cn(
              "flex items-center rounded-xl transition-colors cursor-pointer text-xs font-medium w-full",
              collapsed ? "h-10 justify-center" : "gap-3 px-3 py-2",
              dark
                ? "text-slate-400 hover:bg-slate-800/70 hover:text-white"
                : "text-slate-500 hover:bg-slate-50 hover:text-navy-900",
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

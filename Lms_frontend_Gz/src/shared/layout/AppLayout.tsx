import { useEffect, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";

import { NotificationBell } from "@/modules/notifications/inbox/components/NotificationBell";
import { useAuth, useSignOut } from "@/modules/user-management/auth/hooks/useAuth";
import { ROLE_LABELS } from "@/modules/user-management/common/labels";
import { Brand } from "@/shared/layout/Brand";
import { QuickJump } from "@/shared/layout/QuickJump";
import { SideNav } from "@/shared/layout/SideNav";
import { Avatar, Icon, Menu } from "@/shared/ui";
import { cn } from "@/core/lib/cn";

export function AppLayout() {
  const { user, role } = useAuth();
  const { signOut } = useSignOut();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [desktopCollapsed, setDesktopCollapsed] = useState(() => {
    try {
      return localStorage.getItem("lms_sidebar_collapsed") === "true";
    } catch {
      return false;
    }
  });

  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => setMobileOpen(false), [location.pathname]);

  const toggleDesktopCollapsed = () => {
    setDesktopCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem("lms_sidebar_collapsed", String(next));
      } catch {
        // ignore storage errors
      }
      return next;
    });
  };

  // Keyboard shortcut Ctrl+\ to toggle sidebar
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "\\") {
        e.preventDefault();
        toggleDesktopCollapsed();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  if (!user || !role) return null;

  const userFooter = (
    <div
      className={cn(
        "mt-auto border-t border-slate-100 transition-all duration-200",
        desktopCollapsed ? "p-2" : "p-3",
      )}
    >
      <div
        onClick={() => navigate("/account/profile")}
        className={cn(
          "flex cursor-pointer items-center rounded-xl bg-slate-50 ring-1 ring-slate-200/70 transition-colors hover:bg-slate-100",
          desktopCollapsed ? "h-11 w-11 justify-center mx-auto" : "gap-3 p-2.5",
        )}
        title={desktopCollapsed ? `${user.full_name} (${ROLE_LABELS[user.role]})` : undefined}
      >
        <Avatar name={user.full_name} size="sm" />
        {!desktopCollapsed && (
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-semibold text-navy-950">{user.full_name}</p>
            <div className="flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-brand-500" />
              <p className="truncate text-[10.5px] text-slate-500">{ROLE_LABELS[user.role]}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );

  return (
    <div className="min-h-screen lg:flex">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2">
        Skip to content
      </a>

      {/* Desktop Collapsible Sidebar */}
      <aside
        className={cn(
          "sticky top-0 hidden h-screen shrink-0 flex-col border-r border-slate-200/80 bg-white transition-all duration-300 ease-in-out lg:flex z-20",
          desktopCollapsed ? "w-[72px]" : "w-[268px]",
        )}
      >
        <Brand collapsed={desktopCollapsed} />
        <SideNav
          collapsed={desktopCollapsed}
          onToggleCollapse={toggleDesktopCollapsed}
        />
        {userFooter}
      </aside>

      {/* Mobile Slide-Over Drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div
            className="absolute inset-0 bg-navy-950/40 backdrop-blur-sm transition-opacity"
            onClick={() => setMobileOpen(false)}
            aria-hidden="true"
          />
          <aside className="relative flex h-full w-[284px] max-w-[85vw] flex-col bg-white shadow-pop">
            <Brand onCloseMobile={() => setMobileOpen(false)} />
            <SideNav onItemClick={() => setMobileOpen(false)} />
            <div className="mt-auto border-t border-slate-100 p-3">
              <div onClick={() => { setMobileOpen(false); navigate("/account/profile"); }} className="flex cursor-pointer items-center gap-3 rounded-xl bg-slate-50 p-2.5 ring-1 ring-slate-200/70 hover:bg-slate-100">
                <Avatar name={user.full_name} size="sm" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-semibold text-navy-950">{user.full_name}</p>
                  <p className="truncate text-[10.5px] text-slate-500">{ROLE_LABELS[user.role]}</p>
                </div>
              </div>
            </div>
          </aside>
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-slate-200/70 bg-white/85 px-4 backdrop-blur-md sm:px-6 lg:px-8">
          {/* Mobile Menu Open Toggle */}
          <button
            type="button"
            className="-ml-1 flex h-10 w-10 items-center justify-center rounded-xl text-slate-600 transition-colors hover:bg-slate-100 lg:hidden"
            onClick={() => setMobileOpen(true)}
            aria-label="Open navigation menu"
          >
            <Icon name="menu" size={20} />
          </button>

          {/* Desktop Sidebar Open / Close Toggle Button */}
          <button
            type="button"
            onClick={toggleDesktopCollapsed}
            className="hidden lg:flex h-9 w-9 items-center justify-center rounded-xl border border-slate-200/80 bg-white text-slate-600 transition-all hover:bg-slate-100 hover:text-slate-900 active:scale-95 cursor-pointer shadow-xs"
            title={desktopCollapsed ? "Expand sidebar (Ctrl+\\)" : "Collapse sidebar (Ctrl+\\)"}
            aria-label={desktopCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            <Icon name={desktopCollapsed ? "menu" : "chevronLeft"} size={16} />
          </button>

          <QuickJump />

          <div className="ml-auto flex items-center gap-2">
            <NotificationBell />
            <Menu
              trigger={
                <button
                  type="button"
                  className="flex cursor-pointer items-center gap-3 rounded-xl py-1.5 pl-1.5 pr-2 transition-colors hover:bg-slate-100"
                  aria-label="Account menu"
                >
                  <Avatar name={user.full_name} size="sm" />
                  <span className="hidden text-left sm:block">
                    <span className="block text-sm font-semibold text-navy-950">{user.full_name}</span>
                    <span className="block text-xs text-slate-500">
                      {ROLE_LABELS[user.role]}
                      {user.institution ? ` · ${user.institution.name}` : ""}
                    </span>
                  </span>
                  <Icon name="chevronDown" size={16} className="text-slate-400" />
                </button>
              }
              items={[
                { label: "My profile", icon: "user", onSelect: () => navigate("/account/profile") },
                { label: "Security", icon: "key", onSelect: () => navigate("/account/security") },
                { label: "Sign out", icon: "logout", tone: "danger", onSelect: () => void signOut() },
              ]}
            />
          </div>
        </header>

        <main id="main" className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 sm:py-8 lg:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

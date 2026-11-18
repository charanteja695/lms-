import { useEffect, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  GraduationCap,
  Home,
  BookOpen,
  FileCheck2,
  FileText,
  Award,
  Sparkles,
  Briefcase,
  BarChart2,
  Settings as SettingsIcon,
  HelpCircle,
  LogOut,
  Search,
  Menu as MenuIcon,
  X as XIcon,
} from "lucide-react";

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

  const isStudent = role === "student";

  const userFooter = (
    <div
      className={cn(
        "mt-auto border-t border-[#162B5A] transition-all duration-200",
        desktopCollapsed ? "p-2" : "p-3",
      )}
    >
      {/* User profile row */}
      <div
        className={cn(
          "flex items-center rounded-xl bg-[#10234B]/80 border border-[#182E60] transition-colors hover:bg-[#142B5C] p-2",
          desktopCollapsed ? "h-11 w-11 justify-center mx-auto" : "gap-3",
        )}
        title={desktopCollapsed ? `${user.full_name} (${ROLE_LABELS[user.role]})` : undefined}
      >
        <div
          onClick={() => navigate("/account/profile")}
          className="flex h-9 w-9 shrink-0 cursor-pointer items-center justify-center rounded-full bg-purple-600 font-bold text-white text-xs shadow-xs"
        >
          {user.full_name.charAt(0).toUpperCase()}
        </div>
        {!desktopCollapsed && (
          <div
            onClick={() => navigate("/account/profile")}
            className="min-w-0 flex-1 cursor-pointer"
          >
            <p className="truncate text-xs font-semibold text-white">{user.full_name}</p>
            <p className="truncate text-[10.5px] text-slate-300">{ROLE_LABELS[user.role]}</p>
          </div>
        )}
        {!desktopCollapsed && (
          <button
            type="button"
            onClick={() => void signOut()}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-700/60 hover:text-white cursor-pointer"
            title="Sign out"
            aria-label="Sign out"
          >
            <Icon name="logout" size={15} />
          </button>
        )}
      </div>
    </div>
  );

  // Student specific navigation links matching reference mockup
  const studentMainItems = [
    { to: "/", label: "Dashboard", icon: Home },
    { to: "/courses/my", label: "Courses", icon: BookOpen },
    { to: "/my-tests", label: "Tests", icon: FileCheck2 },
    { to: "/my-tests?tab=assignments", label: "Assignments", icon: FileText },
    { to: "/certificates", label: "Certificates", icon: Award },
    { to: "/career/resumes", label: "AI Resume Builder", icon: Sparkles },
    { to: "/jobs", label: "Job Portal", icon: Briefcase },
    { to: "/analytics", label: "Analytics", icon: BarChart2 },
  ];

  const studentBottomItems = [
    { to: "/account/security", label: "Settings", icon: SettingsIcon },
    { to: "/support", label: "Help & Support", icon: HelpCircle },
  ];

  if (isStudent) {
    return (
      <div className="min-h-screen bg-[#F8FAFC] lg:flex">
        <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2">
          Skip to content
        </a>

        {/* Desktop Student Left Sidebar: Exact 250px width */}
        <aside
          className={cn(
            "sticky top-0 hidden h-screen shrink-0 flex-col border-r border-[#E5E7EB] bg-white transition-all duration-300 ease-in-out lg:flex z-20",
            desktopCollapsed ? "w-[72px]" : "w-[250px]",
          )}
        >
          {/* Logo / Brand: Exact 68px height */}
          <div className="flex h-[68px] items-center px-4 border-b border-[#E5E7EB] gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#635BFF] text-white shadow-xs">
              <GraduationCap className="w-5 h-5" />
            </div>
            {!desktopCollapsed && (
              <div className="min-w-0">
                <p className="text-base font-bold tracking-tight text-[#111827]">ExamLMS</p>
                <p className="text-[11px] font-medium text-[#64748B]">Student Portal</p>
              </div>
            )}
          </div>

          {/* Navigation Links: Exact 40px height per item, 13px / 500 font */}
          <div className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
            {studentMainItems.map((item) => {
              const IconComp = item.icon;
              const isActive =
                item.to === "/"
                  ? location.pathname === "/"
                  : item.to.startsWith("/courses")
                  ? location.pathname.startsWith("/courses") || location.pathname.startsWith("/browse-courses") || location.pathname.startsWith("/store")
                  : item.to.includes("?")
                  ? location.pathname + location.search === item.to
                  : location.pathname.startsWith(item.to);

              return (
                <button
                  key={item.to}
                  type="button"
                  onClick={() => navigate(item.to)}
                  title={desktopCollapsed ? item.label : undefined}
                  className={cn(
                    "flex w-full items-center gap-3 rounded-xl px-3 h-10 text-[13px] font-medium transition-all cursor-pointer",
                    isActive
                      ? "bg-[#F5F4FF] text-[#635BFF] font-semibold shadow-xs"
                      : "text-[#64748B] hover:bg-slate-50 hover:text-[#111827]",
                    desktopCollapsed && "justify-center px-2",
                  )}
                >
                  <IconComp
                    className={cn("w-4 h-4 shrink-0", isActive ? "text-[#635BFF]" : "text-[#64748B]")}
                  />
                  {!desktopCollapsed && <span>{item.label}</span>}
                </button>
              );
            })}
          </div>

          {/* Bottom Sidebar Actions & Student Profile */}
          <div className="mt-auto border-t border-[#E5E7EB] p-3 space-y-1">
            {studentBottomItems.map((item) => {
              const IconComp = item.icon;
              const isActive = location.pathname.startsWith(item.to);
              return (
                <button
                  key={item.to}
                  type="button"
                  onClick={() => navigate(item.to)}
                  title={desktopCollapsed ? item.label : undefined}
                  className={cn(
                    "flex w-full items-center gap-3 rounded-xl px-3 h-10 text-[13px] font-medium text-[#64748B] hover:bg-slate-50 hover:text-[#111827] transition-colors cursor-pointer",
                    isActive && "bg-slate-100 text-[#111827] font-semibold",
                    desktopCollapsed && "justify-center px-2",
                  )}
                >
                  <IconComp className="w-4 h-4 text-[#64748B] shrink-0" />
                  {!desktopCollapsed && <span>{item.label}</span>}
                </button>
              );
            })}

            {/* Profile Row */}
            <div
              className={cn(
                "flex items-center rounded-xl bg-slate-50 border border-[#E5E7EB] p-2 mt-2 transition-colors hover:bg-slate-100",
                desktopCollapsed ? "h-11 w-11 justify-center mx-auto p-1" : "gap-3",
              )}
            >
              <div
                onClick={() => navigate("/account/profile")}
                className="flex h-9 w-9 shrink-0 cursor-pointer items-center justify-center rounded-full bg-[#635BFF] font-bold text-white text-xs shadow-xs"
              >
                {user.full_name.charAt(0).toUpperCase()}
              </div>
              {!desktopCollapsed && (
                <div
                  onClick={() => navigate("/account/profile")}
                  className="min-w-0 flex-1 cursor-pointer"
                >
                  <p className="truncate text-xs font-semibold text-[#111827]">{user.full_name}</p>
                  <p className="truncate text-[11px] text-[#64748B]">Student</p>
                </div>
              )}
              {!desktopCollapsed && (
                <button
                  type="button"
                  onClick={() => void signOut()}
                  className="flex h-7 w-7 items-center justify-center rounded-lg text-[#64748B] transition-colors hover:bg-slate-200 hover:text-[#111827] cursor-pointer"
                  title="Sign out"
                  aria-label="Sign out"
                >
                  <LogOut className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>
        </aside>

        {/* Mobile Slide-Over Drawer for Student */}
        {mobileOpen && (
          <div className="fixed inset-0 z-40 lg:hidden">
            <div
              className="absolute inset-0 bg-navy-950/40 backdrop-blur-sm transition-opacity"
              onClick={() => setMobileOpen(false)}
              aria-hidden="true"
            />
            <aside className="relative flex h-full w-[250px] max-w-[85vw] flex-col bg-white shadow-xl">
              <div className="flex h-[68px] items-center justify-between px-4 border-b border-[#E5E7EB]">
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#635BFF] text-white">
                    <GraduationCap className="w-5 h-5" />
                  </div>
                  <div>
                    <p className="text-sm font-bold text-[#111827]">ExamLMS</p>
                    <p className="text-[11px] text-[#64748B]">Student</p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setMobileOpen(false)}
                  className="p-1 rounded-lg text-slate-400 hover:text-slate-600"
                >
                  <XIcon className="w-4 h-4" />
                </button>
              </div>

              <div className="p-3 space-y-1 overflow-y-auto flex-1">
                {studentMainItems.map((item) => {
                  const IconComp = item.icon;
                  return (
                    <button
                      key={item.to}
                      type="button"
                      onClick={() => {
                        setMobileOpen(false);
                        navigate(item.to);
                      }}
                      className={cn(
                        "flex w-full items-center gap-3 rounded-xl px-3 h-10 text-[13px] font-medium transition-colors cursor-pointer",
                        (item.to === "/" ? location.pathname === "/" : location.pathname.startsWith(item.to))
                          ? "bg-[#F5F4FF] text-[#635BFF] font-semibold"
                          : "text-[#64748B] hover:bg-slate-50",
                      )}
                    >
                      <IconComp className="w-4 h-4" />
                      <span>{item.label}</span>
                    </button>
                  );
                })}
              </div>

              <div className="mt-auto border-t border-[#E5E7EB] p-3 space-y-2">
                <div
                  onClick={() => { setMobileOpen(false); navigate("/account/profile"); }}
                  className="flex cursor-pointer items-center gap-3 rounded-xl bg-slate-50 p-2 hover:bg-slate-100"
                >
                  <Avatar name={user.full_name} size="sm" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-semibold text-[#111827]">{user.full_name}</p>
                    <p className="truncate text-[11px] text-[#64748B]">Student</p>
                  </div>
                </div>
              </div>
            </aside>
          </div>
        )}

        {/* Student Content Area with Exact 68px Header & 24px Main Padding */}
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-30 flex h-[68px] items-center justify-between border-b border-[#E5E7EB] bg-white/95 px-6 backdrop-blur-md">
            <div className="flex items-center gap-4 flex-1 max-w-md">
              {/* Mobile menu toggle */}
              <button
                type="button"
                className="flex h-9 w-9 items-center justify-center rounded-xl text-slate-600 hover:bg-slate-100 lg:hidden cursor-pointer"
                onClick={() => setMobileOpen(true)}
                aria-label="Open menu"
              >
                <MenuIcon className="w-5 h-5" />
              </button>

              {/* Global search input: 44px height, 14px font */}
              <div className="relative w-full max-w-sm">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-[#64748B]">
                  <Search className="w-4 h-4" />
                </div>
                <input
                  type="text"
                  placeholder="Search courses..."
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      navigate(`/browse-courses?search=${encodeURIComponent((e.target as HTMLInputElement).value)}`);
                    }
                  }}
                  className="w-full h-11 rounded-xl border border-[#E5E7EB] bg-slate-50/80 py-2 pl-10 pr-4 text-[14px] text-[#111827] placeholder-[#64748B] transition-colors focus:border-[#635BFF] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#635BFF]/15"
                />
              </div>
            </div>

            <div className="flex items-center gap-4">
              <NotificationBell />
              <Menu
                trigger={
                  <button
                    type="button"
                    className="flex cursor-pointer items-center gap-2 rounded-xl py-1 pl-1 pr-2 transition-colors hover:bg-slate-100"
                    aria-label="Account menu"
                  >
                    <Avatar name={user.full_name} size="sm" />
                    <span className="hidden text-left sm:block">
                      <span className="block text-xs font-semibold text-[#111827]">{user.full_name}</span>
                      <span className="block text-[11px] text-[#64748B]">Student</span>
                    </span>
                    <Icon name="chevronDown" size={14} className="text-[#64748B]" />
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

          {/* Student Content Canvas: Exact 24px padding */}
          <main id="main" className="mx-auto w-full max-w-7xl flex-1 p-6">
            <Outlet />
          </main>
        </div>
      </div>
    );
  }

  // Admin, Super Admin, Institution Head, Staff Layout (Pages 2, 3, 4, 5, 12)
  return (
    <div className="min-h-screen bg-canvas lg:flex">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2">
        Skip to content
      </a>

      {/* Desktop Collapsible Dark Sidebar: Exact 250px width */}
      <aside
        className={cn(
          "sticky top-0 hidden h-screen shrink-0 flex-col border-r border-[#162B5A] bg-[#0B1836] transition-all duration-300 ease-in-out lg:flex z-20",
          desktopCollapsed ? "w-[72px]" : "w-[250px]",
        )}
      >
        <Brand collapsed={desktopCollapsed} dark={true} />
        <SideNav
          collapsed={desktopCollapsed}
          onToggleCollapse={toggleDesktopCollapsed}
          dark={true}
        />
        {userFooter}
      </aside>

      {/* Mobile Slide-Over Drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div
            className="absolute inset-0 bg-navy-950/60 backdrop-blur-sm transition-opacity"
            onClick={() => setMobileOpen(false)}
            aria-hidden="true"
          />
          <aside className="relative flex h-full w-[284px] max-w-[85vw] flex-col bg-[#0B1836] shadow-pop border-r border-[#162B5A]">
            <Brand onCloseMobile={() => setMobileOpen(false)} dark={true} />
            <SideNav onItemClick={() => setMobileOpen(false)} dark={true} />
            {userFooter}
          </aside>
        </div>
      )}

      {/* Main Content Area with Exact 68px Header & 24px Main Padding */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-[68px] items-center gap-3 border-b border-[#E5E7EB] bg-white/95 px-6 backdrop-blur-md">
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

          <div className="ml-auto flex items-center gap-3">
            <NotificationBell />
            <Menu
              trigger={
                <button
                  type="button"
                  className="flex cursor-pointer items-center gap-3 rounded-xl py-1.5 pl-1.5 pr-2 transition-colors hover:bg-slate-100"
                  aria-label="Account menu"
                >
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-purple-600 font-bold text-white text-xs shadow-xs">
                    {user.full_name.charAt(0).toUpperCase()}
                  </div>
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

        <main id="main" className="mx-auto w-full max-w-[1600px] flex-1 p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

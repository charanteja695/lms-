import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { PageHeader, Icon, Card } from "@/shared/ui";
import { cn } from "@/core/lib/cn";
import { CourseRequestsListPage } from "@/modules/subscriptions/course-requests/pages/CourseRequestsListPage";
import { InstitutionalPurchasesPage } from "@/modules/billing/institutional/pages/InstitutionalPurchasesPage";
import { SubscriptionsListPage } from "@/modules/subscriptions/subscriptions/pages/SubscriptionsListPage";
import { InstitutionalPurchaseRequestPage } from "@/modules/billing/institutional/pages/InstitutionalPurchaseRequestPage";

type TabId = "requests" | "purchases" | "subscriptions" | "calculator";

interface TabDef {
  id: TabId;
  label: string;
  icon: "fileText" | "award" | "clock" | "plus";
  description: string;
}

const TABS: TabDef[] = [
  {
    id: "requests",
    label: "Course Requests",
    icon: "fileText",
    description: "Manage institutional course requests and quotation reviews",
  },
  {
    id: "purchases",
    label: "Institutional Purchases",
    icon: "award",
    description: "Track purchased course packages, renewals, and student rosters",
  },
  {
    id: "subscriptions",
    label: "Subscriptions & Seats",
    icon: "clock",
    description: "Monitor active course entitlements and seat allocations",
  },
  {
    id: "calculator",
    label: "Bulk Purchase Calculator",
    icon: "plus",
    description: "Calculate dynamic pricing and submit bulk package orders",
  },
];

export function InstitutionalCourseManagementPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const currentTab = (searchParams.get("tab") as TabId) || "requests";

  const activeTab: TabId = useMemo(() => {
    if (TABS.some((t) => t.id === currentTab)) {
      return currentTab;
    }
    return "requests";
  }, [currentTab]);

  const handleSelectTab = (tabId: TabId) => {
    setSearchParams({ tab: tabId });
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <PageHeader
        title="Institutional Course Management"
        description="Comprehensive portal for course purchasing, quotation reviews, seat allocations, and package management."
      />

      {/* Tabs Navigation Bar */}
      <Card bodyClassName="p-2">
        <div className="flex flex-wrap items-center gap-2 border-b border-slate-100 pb-2">
          {TABS.map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => handleSelectTab(tab.id)}
                className={cn(
                  "flex items-center gap-2 rounded-xl px-4 py-2.5 text-xs sm:text-sm font-semibold transition-all duration-200 cursor-pointer",
                  isActive
                    ? "bg-brand-50 text-brand-700 shadow-sm ring-1 ring-brand-200/60"
                    : "text-slate-600 hover:bg-slate-50 hover:text-navy-950",
                )}
                title={tab.description}
              >
                <Icon
                  name={tab.icon}
                  size={16}
                  className={cn(
                    "transition-colors",
                    isActive ? "text-brand-600" : "text-slate-400",
                  )}
                />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* Tab Description bar */}
        <div className="px-3 pt-2 text-xs text-slate-500">
          {TABS.find((t) => t.id === activeTab)?.description}
        </div>
      </Card>

      {/* Tab Panels */}
      <div className="tab-content-area">
        {activeTab === "requests" && (
          <div className="transition-opacity duration-200">
            <CourseRequestsListPage embedded onNavigateTab={(t) => handleSelectTab(t as TabId)} />
          </div>
        )}

        {activeTab === "purchases" && (
          <div className="transition-opacity duration-200">
            <InstitutionalPurchasesPage embedded onNavigateTab={(t) => handleSelectTab(t as TabId)} />
          </div>
        )}

        {activeTab === "subscriptions" && (
          <div className="transition-opacity duration-200">
            <SubscriptionsListPage embedded />
          </div>
        )}

        {activeTab === "calculator" && (
          <div className="transition-opacity duration-200">
            <InstitutionalPurchaseRequestPage embedded onBackToRequests={() => handleSelectTab("requests")} />
          </div>
        )}
      </div>
    </div>
  );
}

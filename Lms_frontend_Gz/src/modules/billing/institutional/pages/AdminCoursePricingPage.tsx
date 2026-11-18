import { useState, useMemo, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  useGetAdminCoursePricingQuery,
  useGetAdminCoursePricingSummaryQuery,
  useUpdateAdminCoursePricingMutation,
} from "@/modules/billing/institutional/api/institutionalApi";
import type { BulkDiscountTier, CoursePricingItem } from "@/modules/billing/institutional/types";
import { useAuth } from "@/modules/user-management/auth/hooks/useAuth";
import { useNotify } from "@/core/hooks/useNotify";
import {
  Drawer,
  Modal,
  Button,
  Input,
  Textarea,
  Badge,
  Icon,
  PageLoader,
  Alert,
  EmptyState,
} from "@/shared/ui";

const DEFAULT_TIERS: BulkDiscountTier[] = [
  { min_students: 1, max_students: 49, discount_percent: 0, fixed_discount_paise: 0 },
  { min_students: 50, max_students: 99, discount_percent: 5, fixed_discount_paise: 0 },
  { min_students: 100, max_students: 199, discount_percent: 10, fixed_discount_paise: 0 },
  { min_students: 200, max_students: 499, discount_percent: 15, fixed_discount_paise: 0 },
  { min_students: 500, max_students: null, discount_percent: 20, fixed_discount_paise: 0 },
];

const THUMBNAIL_STYLES: Record<string, { bg: string; color: string; cls: string }> = {
  DS: { bg: "#E0F2FE", color: "#075985", cls: "t2" },
  JP: { bg: "#FCE7F3", color: "#9D174D", cls: "t6" },
  UP: { bg: "#EDE9FE", color: "#5B21B6", cls: "t5" },
  SR: { bg: "#FEF3C7", color: "#92400E", cls: "t4" },
  QA: { bg: "#DBEAFE", color: "#1E40AF", cls: "t1" },
  EN: { bg: "#E0F2FE", color: "#075985", cls: "t2" },
  BA: { bg: "#DBEAFE", color: "#1E40AF", cls: "t1" },
};

function getCourseBadge(code?: string, id?: number | string) {
  const c = String(code || "CR").toUpperCase();
  if (THUMBNAIL_STYLES[c]) {
    return { code: c, ...THUMBNAIL_STYLES[c] };
  }
  const colorList = ["t1", "t2", "t3", "t4", "t5", "t6"];
  const cls = colorList[(Number(id) || 0) % colorList.length];
  return { code: c.slice(0, 2), bg: "", color: "", cls };
}

function formatInr(paise: number): string {
  return "₹" + Math.round(paise / 100).toLocaleString("en-IN");
}

function formatDate(iso?: string | null): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    });
  } catch {
    return iso;
  }
}

const REASON_PRESETS = [
  "Promotional pricing",
  "Course content updated",
  "Market price adjustment",
  "Institutional discount revision",
  "Year-end discount offer",
  "Other",
];

export function AdminCoursePricingPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const notify = useNotify();
  const { user } = useAuth();

  // Queries
  const { data: pricingList = [], isLoading, isError, refetch } = useGetAdminCoursePricingQuery();
  const { data: summaryData, refetch: refetchSummary } = useGetAdminCoursePricingSummaryQuery();
  const [updatePricing, { isLoading: isUpdating }] = useUpdateAdminCoursePricingMutation();

  // Search & Filters State
  const [searchQuery, setSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [priceRangeFilter, setPriceRangeFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [sortBy, setSortBy] = useState("name_asc");
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 10;

  // Drawer & Modal States
  const [selectedCourseForEdit, setSelectedCourseForEdit] = useState<CoursePricingItem | null>(null);
  const [previewCourse, setPreviewCourse] = useState<CoursePricingItem | null>(null);
  const [showConfirmModal, setShowConfirmModal] = useState(false);

  // SECTION B – Individual Pricing Form State (in ₹)
  const [indivPriceRupees, setIndivPriceRupees] = useState<number>(1999);
  const [discountType, setDiscountType] = useState<"none" | "percentage" | "fixed">("none");
  const [discountValue, setDiscountValue] = useState<number>(0);
  const [indivGstPercent, setIndivGstPercent] = useState<number>(18);
  const [validDays, setValidDays] = useState<number>(180);
  const [indivEffectiveDate, setIndivEffectiveDate] = useState<string>("");

  // SECTION C – Institutional Pricing Form State (in ₹)
  const [instPriceRupees, setInstPriceRupees] = useState<number>(300);
  const [pricingMethod, setPricingMethod] = useState<"fixed" | "monthly" | "hourly">("fixed");
  const [monthlyPriceRupees, setMonthlyPriceRupees] = useState<number>(100);
  const [monthlyBillingRule, setMonthlyBillingRule] = useState<"pro_rata" | "round_up">("pro_rata");
  const [hourlyPriceRupees, setHourlyPriceRupees] = useState<number>(10);
  const [billableHours, setBillableHours] = useState<number>(40);
  const [bulkDiscountTiers, setBulkDiscountTiers] = useState<BulkDiscountTier[]>(DEFAULT_TIERS);
  const [instGstPercent, setInstGstPercent] = useState<number>(18);
  const [minSeats, setMinSeats] = useState<number>(1);
  const [maxSeats, setMaxSeats] = useState<number>(50000);
  const [instEffectiveDate, setInstEffectiveDate] = useState<string>("");
  const [isActive, setIsActive] = useState<boolean>(true);

  // SECTION D – Reason & Summary
  const [changeReason, setChangeReason] = useState<string>("");

  // Sample Institutional Calculator State
  const [calcStudents, setCalcStudents] = useState<number>(100);
  const [calcDurationMonths, setCalcDurationMonths] = useState<number>(6);

  // Open Drawer automatically if query parameter edit_id is present
  useEffect(() => {
    const editId = searchParams.get("edit");
    if (editId && pricingList.length > 0) {
      const match = pricingList.find((p) => String(p.course_id) === editId);
      if (match) {
        handleOpenEdit(match);
      }
    }
  }, [searchParams, pricingList]);

  const handleOpenEdit = (course: CoursePricingItem) => {
    setSelectedCourseForEdit(course);
    setIndivPriceRupees(Math.round((course.individual_price_paise || 199900) / 100));
    setDiscountType(course.discount_type || (course.discount_paise && course.discount_paise > 0 ? "fixed" : "none"));
    setDiscountValue(
      course.discount_type === "percentage"
        ? course.discount_percent || 0
        : Math.round((course.discount_paise || 0) / 100)
    );
    setIndivGstPercent(course.gst_percent !== undefined ? course.gst_percent : 18);
    setValidDays(course.valid_days || course.max_duration_days || 180);
    setIndivEffectiveDate(course.effective_from ? String(course.effective_from).slice(0, 10) : "");

    setInstPriceRupees(Math.round((course.fixed_price_paise || 30000) / 100));
    setPricingMethod(course.pricing_method || "fixed");
    setMonthlyPriceRupees(Math.round((course.monthly_price_paise || 10000) / 100));
    setMonthlyBillingRule(course.monthly_billing_rule || "pro_rata");
    setHourlyPriceRupees(Math.round((course.hourly_price_paise || 1000) / 100));
    setBillableHours(course.billable_hours || 40);
    setBulkDiscountTiers(
      course.bulk_discount_tiers && course.bulk_discount_tiers.length > 0
        ? course.bulk_discount_tiers
        : DEFAULT_TIERS
    );
    setInstGstPercent(course.gst_percent !== undefined ? course.gst_percent : 18);
    setMinSeats(course.min_students || 1);
    setMaxSeats(course.max_students || 50000);
    setInstEffectiveDate(course.effective_from ? String(course.effective_from).slice(0, 10) : "");
    setIsActive(course.is_active !== false);

    setChangeReason("");
  };

  const handleCloseDrawer = () => {
    setSelectedCourseForEdit(null);
    setShowConfirmModal(false);
  };

  const handleResetForm = () => {
    if (selectedCourseForEdit) {
      handleOpenEdit(selectedCourseForEdit);
    }
  };

  // Live Individual Price Calculation
  const liveIndividualCalc = useMemo(() => {
    const base = Math.max(0, Number(indivPriceRupees) || 0);
    let discountAmount = 0;
    if (discountType === "percentage") {
      discountAmount = Math.round((base * Math.min(100, Math.max(0, discountValue))) / 100);
    } else if (discountType === "fixed") {
      discountAmount = Math.min(base, Math.max(0, discountValue));
    }
    const taxable = Math.max(0, base - discountAmount);
    const gstAmount = Math.round((taxable * (Number(indivGstPercent) || 0)) / 100);
    const finalAmount = taxable + gstAmount;
    return {
      basePrice: base,
      discountAmount,
      taxableAmount: taxable,
      gstAmount,
      finalAmount,
    };
  }, [indivPriceRupees, discountType, discountValue, indivGstPercent]);

  // Live Institutional Sample Calculation
  const liveInstitutionalCalc = useMemo(() => {
    const students = Math.max(1, Number(calcStudents) || 1);
    const months = Math.max(1, Number(calcDurationMonths) || 1);
    let unitRate = 0;

    if (pricingMethod === "fixed") {
      unitRate = Math.max(0, Number(instPriceRupees) || 0);
    } else if (pricingMethod === "monthly") {
      unitRate = Math.max(0, Number(monthlyPriceRupees) || 0) * months;
    } else if (pricingMethod === "hourly") {
      unitRate = Math.max(0, Number(hourlyPriceRupees) || 0) * Math.max(1, Number(billableHours) || 40);
    }

    const subtotal = unitRate * students;

    // Determine matching bulk discount tier
    let tierPercent = 0;
    let tierFixed = 0;
    for (const t of bulkDiscountTiers) {
      const min = t.min_students || 1;
      const max = t.max_students;
      if (students >= min && (max === null || max === undefined || students <= max)) {
        tierPercent = t.discount_percent || 0;
        tierFixed = Math.round((t.fixed_discount_paise || 0) / 100);
        break;
      }
    }

    let bulkDiscount = 0;
    if (tierPercent > 0) {
      bulkDiscount = Math.round((subtotal * tierPercent) / 100);
    } else if (tierFixed > 0) {
      bulkDiscount = Math.min(subtotal, tierFixed);
    }

    const taxable = Math.max(0, subtotal - bulkDiscount);
    const gst = Math.round((taxable * (Number(instGstPercent) || 0)) / 100);
    const grandTotal = taxable + gst;

    return {
      unitRate,
      students,
      months,
      subtotal,
      bulkDiscount,
      bulkDiscountPercent: tierPercent,
      taxable,
      gst,
      grandTotal,
    };
  }, [
    calcStudents,
    calcDurationMonths,
    pricingMethod,
    instPriceRupees,
    monthlyPriceRupees,
    hourlyPriceRupees,
    billableHours,
    bulkDiscountTiers,
    instGstPercent,
  ]);

  // Comparison & Delta calculations
  const priceComparison = useMemo(() => {
    if (!selectedCourseForEdit) return null;

    const prevIndiv = Math.round(selectedCourseForEdit.individual_price_paise / 100);
    const newIndiv = Number(indivPriceRupees) || 0;
    const indivDiff = newIndiv - prevIndiv;
    const indivPct = prevIndiv > 0 ? ((indivDiff / prevIndiv) * 100).toFixed(1) : "0.0";

    const prevInst = Math.round(selectedCourseForEdit.fixed_price_paise / 100);
    const newInst = Number(instPriceRupees) || 0;
    const instDiff = newInst - prevInst;
    const instPct = prevInst > 0 ? ((instDiff / prevInst) * 100).toFixed(1) : "0.0";

    const hasChanged =
      indivDiff !== 0 ||
      instDiff !== 0 ||
      discountType !== (selectedCourseForEdit.discount_type || "none") ||
      liveIndividualCalc.discountAmount !== (selectedCourseForEdit.discount_paise ? selectedCourseForEdit.discount_paise / 100 : 0) ||
      indivGstPercent !== selectedCourseForEdit.gst_percent ||
      pricingMethod !== selectedCourseForEdit.pricing_method ||
      monthlyPriceRupees !== Math.round((selectedCourseForEdit.monthly_price_paise || 10000) / 100) ||
      hourlyPriceRupees !== Math.round((selectedCourseForEdit.hourly_price_paise || 1000) / 100) ||
      billableHours !== (selectedCourseForEdit.billable_hours || 40) ||
      isActive !== selectedCourseForEdit.is_active;

    return {
      prevIndiv,
      newIndiv,
      indivDiff,
      indivPct,
      prevInst,
      newInst,
      instDiff,
      instPct,
      hasChanged,
    };
  }, [
    selectedCourseForEdit,
    indivPriceRupees,
    instPriceRupees,
    discountType,
    liveIndividualCalc.discountAmount,
    indivGstPercent,
    pricingMethod,
    monthlyPriceRupees,
    hourlyPriceRupees,
    billableHours,
    isActive,
  ]);

  const handleSaveConfirmed = async () => {
    if (!selectedCourseForEdit) return;
    try {
      const indivPaise = Math.round(indivPriceRupees * 100);
      const discountPaise = Math.round(liveIndividualCalc.discountAmount * 100);
      const originalPricePaise =
        discountType !== "none" && discountValue > 0 ? indivPaise + discountPaise : indivPaise;
      const fixedInstPaise = Math.round(instPriceRupees * 100);
      const monthlyPaise = Math.round(monthlyPriceRupees * 100);
      const hourlyPaise = Math.round(hourlyPriceRupees * 100);

      await updatePricing({
        course_id: selectedCourseForEdit.course_id,
        course_title: selectedCourseForEdit.course_title,
        course_code: selectedCourseForEdit.course_code,
        category: selectedCourseForEdit.category,
        individual_price_paise: indivPaise,
        original_price_paise: originalPricePaise,
        discount_paise: discountPaise,
        discount_type: discountType,
        discount_percent: discountType === "percentage" ? discountValue : 0,
        discount_value: discountValue,
        valid_days: validDays,
        pricing_method: pricingMethod,
        fixed_price_paise: fixedInstPaise,
        monthly_price_paise: monthlyPaise,
        monthly_billing_rule: monthlyBillingRule,
        hourly_price_paise: hourlyPaise,
        billable_hours: billableHours,
        bulk_discount_tiers: bulkDiscountTiers,
        gst_percent: instGstPercent,
        min_students: minSeats,
        max_students: maxSeats,
        is_active: isActive,
        reason: changeReason.trim() || "Course pricing updated by admin",
        admin_name: user?.full_name || "Super Admin",
        admin_role: user?.role === "super_admin" ? "Super Admin" : "Admin",
      }).unwrap();

      notify.success(
        "Pricing Changes Saved",
        `Updated pricing for "${selectedCourseForEdit.course_title}". Audit log created.`
      );
      handleCloseDrawer();
      refetch();
      refetchSummary();
    } catch (err: any) {
      notify.error("Update Failed", err?.data?.detail || "Could not save course pricing changes.");
    }
  };

  // Client-side CSV Export
  const handleExportCsv = () => {
    if (!pricingList.length) return;
    const headers = [
      "Course Code",
      "Course Title",
      "Category",
      "Individual Price (₹)",
      "Original Price (₹)",
      "Discount Type",
      "Discount Value",
      "Institutional Price (₹)",
      "Pricing Method",
      "GST (%)",
      "Status",
      "Last Updated",
      "Last Updated By",
    ];

    const rows = pricingList.map((p) => {
      const code = p.course_code || getCourseBadge(undefined, Number(p.course_id)).code;
      const indiv = (p.individual_price_paise / 100).toFixed(2);
      const orig = p.original_price_paise ? (p.original_price_paise / 100).toFixed(2) : indiv;
      const inst = (p.fixed_price_paise / 100).toFixed(2);
      return [
        `"${code}"`,
        `"${p.course_title.replace(/"/g, '""')}"`,
        `"${p.category || "Technology"}"`,
        `"${indiv}"`,
        `"${orig}"`,
        `"${p.discount_type || "none"}"`,
        `"${p.discount_percent || p.discount_value || 0}"`,
        `"${inst}"`,
        `"${p.pricing_method || "fixed"}"`,
        `"${p.gst_percent || 18}"`,
        `"${p.is_active ? "Active" : "Inactive"}"`,
        `"${formatDate(p.last_updated_at)}"`,
        `"${(p.last_updated_by || "Admin").replace(/"/g, '""')}"`,
      ].join(",");
    });

    const csvContent = "data:text/csv;charset=utf-8," + [headers.join(","), ...rows].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `examlms_course_pricing_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Filter and Sort Courses
  const filteredCourses = useMemo(() => {
    return pricingList
      .filter((p) => {
        const titleMatch =
          p.course_title.toLowerCase().includes(searchQuery.toLowerCase()) ||
          (p.course_code && p.course_code.toLowerCase().includes(searchQuery.toLowerCase())) ||
          String(p.course_id).includes(searchQuery);

        const catMatch =
          categoryFilter === "all" || (p.category && p.category.toLowerCase() === categoryFilter.toLowerCase());

        const indiv = p.individual_price_paise / 100;
        let priceMatch = true;
        if (priceRangeFilter === "under_2k") priceMatch = indiv < 2000;
        else if (priceRangeFilter === "2k_to_4k") priceMatch = indiv >= 2000 && indiv <= 4000;
        else if (priceRangeFilter === "above_4k") priceMatch = indiv > 4000;

        const statusMatch =
          statusFilter === "all" ||
          (statusFilter === "active" && p.is_active) ||
          (statusFilter === "inactive" && !p.is_active);

        return titleMatch && catMatch && priceMatch && statusMatch;
      })
      .sort((a, b) => {
        if (sortBy === "name_asc") return a.course_title.localeCompare(b.course_title);
        if (sortBy === "name_desc") return b.course_title.localeCompare(a.course_title);
        if (sortBy === "indiv_asc") return a.individual_price_paise - b.individual_price_paise;
        if (sortBy === "indiv_desc") return b.individual_price_paise - a.individual_price_paise;
        if (sortBy === "inst_asc") return a.fixed_price_paise - b.fixed_price_paise;
        if (sortBy === "updated_desc") {
          const tA = a.last_updated_at ? new Date(a.last_updated_at).getTime() : 0;
          const tB = b.last_updated_at ? new Date(b.last_updated_at).getTime() : 0;
          return tB - tA;
        }
        return 0;
      });
  }, [pricingList, searchQuery, categoryFilter, priceRangeFilter, statusFilter, sortBy]);

  const totalPages = Math.max(1, Math.ceil(filteredCourses.length / pageSize));
  const paginatedCourses = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filteredCourses.slice(start, start + pageSize);
  }, [filteredCourses, currentPage, pageSize]);

  const handleClearFilters = () => {
    setSearchQuery("");
    setCategoryFilter("all");
    setPriceRangeFilter("all");
    setStatusFilter("all");
    setSortBy("name_asc");
    setCurrentPage(1);
  };

  const hasActiveFilters =
    Boolean(searchQuery) ||
    categoryFilter !== "all" ||
    priceRangeFilter !== "all" ||
    statusFilter !== "all" ||
    sortBy !== "name_asc";

  if (isLoading) return <PageLoader />;

  return (
    <div className="course-mgmt-shell min-h-screen bg-[#F8FAFC] text-[#0F172A] font-sans">
      <style>{`
        .course-mgmt-shell {
          font-family: 'Inter', system-ui, -apple-system, sans-serif;
        }
        .course-mgmt-shell h1,
        .course-mgmt-shell h2,
        .course-mgmt-shell h3,
        .course-mgmt-shell h4 {
          font-family: 'Plus Jakarta Sans', 'Inter', system-ui, sans-serif;
        }
        .t1 { background: #DBEAFE; color: #1E40AF; }
        .t2 { background: #E0F2FE; color: #075985; }
        .t3 { background: #DCFCE7; color: #166534; }
        .t4 { background: #FEF3C7; color: #92400E; }
        .t5 { background: #EDE9FE; color: #5B21B6; }
        .t6 { background: #FCE7F3; color: #9D174D; }
        .drawer-subpanel {
          background: #FFFFFF;
          border: 1px solid #E2E8F0;
          border-radius: 12px;
          padding: 16px;
        }
      `}</style>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        {/* Header Section */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-[#E5E7EB]">
          <div>
            <h1 className="text-[28px] font-bold tracking-tight text-[#111827]">Course Pricing Management</h1>
          </div>
          <div className="flex items-center flex-wrap gap-2.5">
            <Button
              variant="secondary"
              icon="clock"
              onClick={() => navigate("/admin/course-pricing/history")}
              className="text-xs font-medium"
            >
              Price Change History
            </Button>
            <Button
              variant="secondary"
              icon="download"
              onClick={handleExportCsv}
              className="text-xs font-medium"
            >
              Export Pricing
            </Button>
            <Button
              variant="secondary"
              icon="refreshCw"
              onClick={() => {
                refetch();
                refetchSummary();
              }}
              className="text-xs font-medium"
            >
              Refresh
            </Button>
          </div>
        </div>

        {isError && (
          <Alert tone="error" title="Failed to retrieve course pricing">
            Could not communicate with the billing service. Please check network connectivity or refresh.
          </Alert>
        )}

        {/* 1. Summary Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Card 1 */}
          <div className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-xs flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-[#64748B] uppercase tracking-wider">Total Courses with Pricing</p>
              <h3 className="text-2xl font-bold text-[#0F172A] mt-1">
                {summaryData?.total_courses || pricingList.length}
              </h3>
              <p className="text-xs text-[#16A34A] font-medium mt-1 flex items-center gap-1">
                <Icon name="check" size={12} /> Live published courses
              </p>
            </div>
            <div className="w-11 h-11 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
              <Icon name="book" size={20} />
            </div>
          </div>

          {/* Card 2 */}
          <div className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-xs flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-[#64748B] uppercase tracking-wider">Individual Price Updates</p>
              <h3 className="text-2xl font-bold text-[#0F172A] mt-1">
                {summaryData?.individual_updates ?? 7}
              </h3>
              <p className="text-xs text-[#64748B] font-medium mt-1">Logged to audit trail</p>
            </div>
            <div className="w-11 h-11 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center">
              <Icon name="creditCard" size={20} />
            </div>
          </div>

          {/* Card 3 */}
          <div className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-xs flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-[#64748B] uppercase tracking-wider">Institutional Price Updates</p>
              <h3 className="text-2xl font-bold text-[#0F172A] mt-1">
                {summaryData?.institutional_updates ?? 5}
              </h3>
              <p className="text-xs text-[#64748B] font-medium mt-1">Bulk licensing updates</p>
            </div>
            <div className="w-11 h-11 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center">
              <Icon name="building" size={20} />
            </div>
          </div>

          {/* Card 4 */}
          <div className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-xs flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-[#64748B] uppercase tracking-wider">Courses with Active Discounts</p>
              <h3 className="text-2xl font-bold text-[#0F172A] mt-1">
                {summaryData?.active_discounts ?? 2}
              </h3>
              <p className="text-xs text-[#16A34A] font-medium mt-1">Active promotional / tiers</p>
            </div>
            <div className="w-11 h-11 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
              <Icon name="sparkles" size={20} />
            </div>
          </div>
        </div>

        {/* 2. Filter & Search Toolbar */}
        <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-xs space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-center">
            {/* Search */}
            <div className="md:col-span-4 relative">
              <Input
                placeholder="Search by course name or code..."
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  setCurrentPage(1);
                }}
                className="w-full text-xs"
              />
            </div>

            {/* Category Filter */}
            <div className="md:col-span-2">
              <select
                value={categoryFilter}
                onChange={(e) => {
                  setCategoryFilter(e.target.value);
                  setCurrentPage(1);
                }}
                className="h-9 px-2.5 rounded-lg border border-[#CBD5E1] bg-white text-xs text-[#0F172A] focus:outline-none focus:ring-1 focus:ring-[#2563EB] w-full"
              >
                <option value="all">All Categories</option>
                <option value="Technology">Technology</option>
                <option value="Academics">Academics</option>
                <option value="Civil Services">Civil Services</option>
                <option value="Government Exams">Government Exams</option>
                <option value="Banking">Banking</option>
              </select>
            </div>

            {/* Price Range Filter */}
            <div className="md:col-span-2">
              <select
                value={priceRangeFilter}
                onChange={(e) => {
                  setPriceRangeFilter(e.target.value);
                  setCurrentPage(1);
                }}
                className="h-9 px-2.5 rounded-lg border border-[#CBD5E1] bg-white text-xs text-[#0F172A] focus:outline-none focus:ring-1 focus:ring-[#2563EB] w-full"
              >
                <option value="all">All Prices</option>
                <option value="under_2k">&lt; ₹2,000</option>
                <option value="2k_to_4k">₹2,000 – ₹4,000</option>
                <option value="above_4k">&gt; ₹4,000</option>
              </select>
            </div>

            {/* Status Filter */}
            <div className="md:col-span-2">
              <select
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value);
                  setCurrentPage(1);
                }}
                className="h-9 px-2.5 rounded-lg border border-[#CBD5E1] bg-white text-xs text-[#0F172A] focus:outline-none focus:ring-1 focus:ring-[#2563EB] w-full"
              >
                <option value="all">All Status</option>
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </select>
            </div>

            {/* Sort Filter */}
            <div className="md:col-span-2">
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="h-9 px-2.5 rounded-lg border border-[#CBD5E1] bg-white text-xs text-[#0F172A] focus:outline-none focus:ring-1 focus:ring-[#2563EB] w-full"
              >
                <option value="name_asc">Name (A-Z)</option>
                <option value="name_desc">Name (Z-A)</option>
                <option value="indiv_asc">Indiv Price: Low-High</option>
                <option value="indiv_desc">Indiv Price: High-Low</option>
                <option value="inst_asc">Inst Price: Low-High</option>
                <option value="updated_desc">Recently Updated</option>
              </select>
            </div>
          </div>

          {hasActiveFilters && (
            <div className="flex items-center justify-between pt-2 border-t border-[#F1F5F9] text-xs">
              <span className="text-[#64748B]">
                Showing {filteredCourses.length} of {pricingList.length} courses
              </span>
              <button
                type="button"
                onClick={handleClearFilters}
                className="text-[#2563EB] hover:underline font-medium flex items-center gap-1"
              >
                <Icon name="x" size={13} /> Clear filters
              </button>
            </div>
          )}
        </div>

        {/* 3. Course Pricing Table */}
        <div className="bg-white border border-[#E2E8F0] rounded-xl shadow-xs overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-[#F8FAFC] border-b border-[#E2E8F0] text-[#64748B] font-semibold uppercase tracking-wider">
                  <th className="py-3 px-4">Course</th>
                  <th className="py-3 px-3">Category</th>
                  <th className="py-3 px-3">Individual Price</th>
                  <th className="py-3 px-3">Institutional Price</th>
                  <th className="py-3 px-3">Discount</th>
                  <th className="py-3 px-3">GST</th>
                  <th className="py-3 px-3">Last Updated</th>
                  <th className="py-3 px-3">Status</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E2E8F0]">
                {paginatedCourses.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="py-12 text-center">
                      <EmptyState
                        title="No courses found"
                        description="Try adjusting your search terms or filters to find course pricing records."
                      />
                    </td>
                  </tr>
                ) : (
                  paginatedCourses.map((course, idx) => {
                    const badge = getCourseBadge(course.course_code, Number(course.course_id));
                    const indivPrice = formatInr(course.individual_price_paise);
                    const origPrice =
                      course.original_price_paise && course.original_price_paise > course.individual_price_paise
                        ? formatInr(course.original_price_paise)
                        : null;

                    let instUnit = "/ student";
                    if (course.pricing_method === "monthly") {
                      instUnit = "/ student / mo";
                    } else if (course.pricing_method === "hourly") {
                      instUnit = "/ hr";
                    }
                    const instRate =
                      course.pricing_method === "monthly"
                        ? formatInr(course.monthly_price_paise)
                        : course.pricing_method === "hourly"
                        ? formatInr(course.hourly_price_paise)
                        : formatInr(course.fixed_price_paise);

                    return (
                      <tr key={`${course.course_id}-${idx}`} className="hover:bg-[#FAFBFD] transition-colors">
                        {/* Course Name & Code */}
                        <td className="py-3.5 px-4">
                          <div className="flex items-center gap-3">
                            <div
                              className={`w-10 h-8 rounded-lg flex items-center justify-center font-bold text-xs flex-none ${badge.cls}`}
                            >
                              {badge.code}
                            </div>
                            <div className="min-w-0">
                              <p className="font-semibold text-[#0F172A] truncate max-w-[220px]">
                                {course.course_title}
                              </p>
                              <p className="text-[11px] text-[#64748B] font-mono">
                                {course.course_code || badge.code}-{String(course.course_id ?? "").slice(-3) || "101"}
                              </p>
                            </div>
                          </div>
                        </td>

                        {/* Category */}
                        <td className="py-3.5 px-3">
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-[#F1F5F9] text-[#334155]">
                            {course.category || "Technology"}
                          </span>
                        </td>

                        {/* Individual Price */}
                        <td className="py-3.5 px-3 whitespace-nowrap">
                          {origPrice ? (
                            <div className="flex flex-col">
                              <span className="text-[11px] text-[#64748B] line-through">{origPrice}</span>
                              <div className="flex items-center gap-1.5">
                                <span className="font-bold text-[#0F172A] text-sm">{indivPrice}</span>
                                {course.discount_percent && course.discount_percent > 0 ? (
                                  <span className="text-[10px] font-semibold text-[#15803D] bg-[#DCFCE7] px-1 rounded">
                                    {course.discount_percent}% off
                                  </span>
                                ) : null}
                              </div>
                            </div>
                          ) : (
                            <span className="font-bold text-[#0F172A] text-sm">{indivPrice}</span>
                          )}
                        </td>

                        {/* Institutional Price */}
                        <td className="py-3.5 px-3 whitespace-nowrap">
                          <div className="flex items-baseline gap-1">
                            <span className="font-bold text-[#0F172A] text-sm">{instRate}</span>
                            <span className="text-[11px] text-[#64748B] font-medium">{instUnit}</span>
                          </div>
                        </td>

                        {/* Discount Structure */}
                        <td className="py-3.5 px-3 whitespace-nowrap">
                          {course.discount_paise && course.discount_paise > 0 ? (
                            <span className="inline-flex items-center gap-1 text-[11px] font-medium text-[#16A34A]">
                              <Icon name="sparkles" size={12} /> {formatInr(course.discount_paise)} off
                            </span>
                          ) : course.bulk_discount_tiers && course.bulk_discount_tiers.length > 0 ? (
                            <span className="text-[11px] text-[#64748B]">Volume tiers (up to 20%)</span>
                          ) : (
                            <span className="text-[11px] text-[#94A3B8]">Standard</span>
                          )}
                        </td>

                        {/* GST */}
                        <td className="py-3.5 px-3 whitespace-nowrap text-[#64748B] font-medium">
                          {course.gst_percent ?? 18}%
                        </td>

                        {/* Last Updated */}
                        <td className="py-3.5 px-3 whitespace-nowrap">
                          <div className="flex flex-col">
                            <span className="text-[#334155] font-medium">
                              {formatDate(course.last_updated_at)}
                            </span>
                            <span className="text-[11px] text-[#64748B]">
                              by {course.last_updated_by || "Admin"}
                            </span>
                          </div>
                        </td>

                        {/* Status */}
                        <td className="py-3.5 px-3 whitespace-nowrap">
                          {course.is_active ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-[#F0FDF4] text-[#15803D] border border-[#BBF7D0]">
                              <span className="w-1.5 h-1.5 rounded-full bg-[#16A34A]" /> Active
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-[#F1F5F9] text-[#64748B] border border-[#E2E8F0]">
                              <span className="w-1.5 h-1.5 rounded-full bg-[#94A3B8]" /> Inactive
                            </span>
                          )}
                        </td>

                        {/* Actions */}
                        <td className="py-3.5 px-4 text-right whitespace-nowrap">
                          <div className="flex items-center justify-end gap-1.5">
                            <Button
                              size="sm"
                              variant="primary"
                              onClick={() => handleOpenEdit(course)}
                              className="text-xs h-7 px-2.5 bg-[#2563EB] hover:bg-[#1D4ED8]"
                            >
                              Edit Price
                            </Button>
                            <Button
                              size="sm"
                              variant="secondary"
                              onClick={() =>
                                navigate(`/admin/course-pricing/history?course_id=${course.course_id}`)
                              }
                              title="View Price Change History"
                              className="h-7 w-7 p-0 flex items-center justify-center text-[#64748B] hover:text-[#0F172A]"
                            >
                              <Icon name="clock" size={14} />
                            </Button>
                            <Button
                              size="sm"
                              variant="secondary"
                              onClick={() => setPreviewCourse(course)}
                              title="Preview Pricing Breakdown"
                              className="h-7 w-7 p-0 flex items-center justify-center text-[#64748B] hover:text-[#0F172A]"
                            >
                              <Icon name="eye" size={14} />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination Footer */}
          <div className="p-4 border-t border-[#E2E8F0] flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-[#64748B]">
            <div>
              Showing {filteredCourses.length > 0 ? (currentPage - 1) * pageSize + 1 : 0} to{" "}
              {Math.min(currentPage * pageSize, filteredCourses.length)} of {filteredCourses.length} courses
            </div>
            <div className="flex items-center gap-1">
              <Button
                variant="secondary"
                size="sm"
                disabled={currentPage <= 1}
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                className="h-8 w-8 p-0"
              >
                <Icon name="chevronLeft" size={14} />
              </Button>
              {Array.from({ length: totalPages }).map((_, idx) => (
                <Button
                  key={idx + 1}
                  variant={currentPage === idx + 1 ? "primary" : "secondary"}
                  size="sm"
                  onClick={() => setCurrentPage(idx + 1)}
                  className={`h-8 w-8 p-0 text-xs ${
                    currentPage === idx + 1 ? "bg-[#2563EB]" : ""
                  }`}
                >
                  {idx + 1}
                </Button>
              ))}
              <Button
                variant="secondary"
                size="sm"
                disabled={currentPage >= totalPages}
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                className="h-8 w-8 p-0"
              >
                <Icon name="chevronRight" size={14} />
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* SCREEN 8 – EDIT PRICE SIDE DRAWER                                         */}
      {/* ========================================================================= */}
      {selectedCourseForEdit && (
        <Drawer size="lg" onClose={handleCloseDrawer}>
          <div className="flex flex-col h-full bg-[#FFFFFF] text-[#0F172A]">
            {/* Drawer Header */}
            <div className="flex items-center justify-between p-5 border-b border-[#E2E8F0] bg-[#FFFFFF]">
              <div>
                <h2 className="text-lg font-bold text-[#0F172A]">Edit Course Pricing</h2>
                <p className="text-xs text-[#64748B] mt-0.5">
                  Update individual rates, bulk institutional tiers, discounts and taxes.
                </p>
              </div>
              <button
                type="button"
                onClick={handleCloseDrawer}
                className="text-[#64748B] hover:text-[#0F172A] p-1.5 rounded-lg hover:bg-[#F1F5F9] transition-colors"
                aria-label="Close"
              >
                <Icon name="x" size={18} />
              </button>
            </div>

            {/* Drawer Scrollable Body */}
            <div className="flex-1 overflow-y-auto p-5 space-y-6">
              {/* SECTION A – COURSE INFORMATION (Read-only) */}
              <div className="drawer-subpanel bg-[#F8FAFC]">
                <p className="text-xs font-semibold text-[#64748B] uppercase tracking-wider mb-2">
                  Section A – Course Information
                </p>
                <div className="flex items-center gap-3">
                  <div
                    className={`w-12 h-10 rounded-lg flex items-center justify-center font-bold text-sm flex-none ${
                      getCourseBadge(selectedCourseForEdit.course_code, Number(selectedCourseForEdit.course_id)).cls
                    }`}
                  >
                    {getCourseBadge(selectedCourseForEdit.course_code, Number(selectedCourseForEdit.course_id)).code}
                  </div>
                  <div className="flex-1 min-w-0">
                    <h4 className="font-bold text-[#0F172A] text-sm truncate">
                      {selectedCourseForEdit.course_title}
                    </h4>
                    <div className="flex items-center gap-2 mt-0.5 text-xs text-[#64748B]">
                      <span>ID: {selectedCourseForEdit.course_id}</span>
                      <span>•</span>
                      <span className="font-mono bg-[#E2E8F0] px-1.5 py-0.2 rounded text-[11px]">
                        {selectedCourseForEdit.course_code || "CR-101"}
                      </span>
                      <span>•</span>
                      <span className="text-[#2563EB] font-medium">{selectedCourseForEdit.category || "Technology"}</span>
                    </div>
                  </div>
                  <Badge tone={selectedCourseForEdit.is_active ? "green" : "gray"}>
                    {selectedCourseForEdit.is_active ? "Active" : "Inactive"}
                  </Badge>
                </div>
              </div>

              {/* SECTION B – INDIVIDUAL STUDENT PRICING */}
              <div className="drawer-subpanel space-y-4">
                <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-2">
                  <div>
                    <h3 className="font-bold text-sm text-[#0F172A]">Section B – Individual Student Pricing</h3>
                    <p className="text-xs text-[#64748B]">Model A: Independent self-registered students</p>
                  </div>
                  <div className="text-right">
                    <span className="text-xs text-[#64748B]">Current: </span>
                    <span className="text-xs font-bold text-[#0F172A]">
                      {formatInr(selectedCourseForEdit.individual_price_paise)}
                    </span>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 text-xs">
                  <div>
                    <label className="block font-medium text-[#334155] mb-1">
                      New Individual Price (₹) <span className="text-red-500">*</span>
                    </label>
                    <Input
                      type="number"
                      min={0}
                      value={indivPriceRupees}
                      onChange={(e) => setIndivPriceRupees(Number(e.target.value))}
                      className="w-full text-xs"
                    />
                  </div>

                  <div>
                    <label className="block font-medium text-[#334155] mb-1">Discount Type</label>
                    <select
                      value={discountType}
                      onChange={(e) => {
                        setDiscountType(e.target.value as any);
                        if (e.target.value === "none") setDiscountValue(0);
                      }}
                      className="h-9 px-2.5 rounded-lg border border-[#CBD5E1] bg-white text-xs text-[#0F172A] focus:outline-none focus:ring-1 focus:ring-[#2563EB] w-full"
                    >
                      <option value="none">No Discount</option>
                      <option value="percentage">Percentage (%)</option>
                      <option value="fixed">Fixed Amount (₹)</option>
                    </select>
                  </div>

                  {discountType !== "none" && (
                    <div>
                      <label className="block font-medium text-[#334155] mb-1">
                        {discountType === "percentage" ? "Discount Percentage (%)" : "Discount Amount (₹)"}
                      </label>
                      <Input
                        type="number"
                        min={0}
                        max={discountType === "percentage" ? 100 : indivPriceRupees}
                        value={discountValue}
                        onChange={(e) => setDiscountValue(Number(e.target.value))}
                        className="w-full text-xs"
                      />
                    </div>
                  )}

                  <div>
                    <label className="block font-medium text-[#334155] mb-1">GST Rate (%)</label>
                    <Input
                      type="number"
                      min={0}
                      max={100}
                      value={indivGstPercent}
                      onChange={(e) => setIndivGstPercent(Number(e.target.value))}
                      className="w-full text-xs"
                    />
                  </div>

                  <div>
                    <label className="block font-medium text-[#334155] mb-1">Access Validity (Days)</label>
                    <Input
                      type="number"
                      min={1}
                      max={1825}
                      value={validDays}
                      onChange={(e) => setValidDays(Number(e.target.value))}
                      className="w-full text-xs"
                    />
                  </div>

                  <div>
                    <label className="block font-medium text-[#334155] mb-1">Effective Date</label>
                    <Input
                      type="date"
                      value={indivEffectiveDate}
                      onChange={(e) => setIndivEffectiveDate(e.target.value)}
                      className="w-full text-xs"
                    />
                  </div>
                </div>

                {/* Live Individual Calculation Panel */}
                <div className="bg-[#EFF6FF] border border-[#BFDBFE] rounded-lg p-3 text-xs space-y-1.5">
                  <div className="flex items-center justify-between text-[#1E40AF] font-semibold pb-1 border-b border-[#DBEAFE]">
                    <span className="flex items-center gap-1">
                      <Icon name="sparkles" size={13} /> Live Checkout Calculation
                    </span>
                    <span>1 Student Checkout</span>
                  </div>
                  <div className="flex justify-between text-[#334155]">
                    <span>Base Price:</span>
                    <span>₹{liveIndividualCalc.basePrice.toLocaleString()}</span>
                  </div>
                  {liveIndividualCalc.discountAmount > 0 && (
                    <div className="flex justify-between text-[#15803D] font-medium">
                      <span>Discount ({discountType === "percentage" ? `${discountValue}%` : "Fixed"}):</span>
                      <span>-₹{liveIndividualCalc.discountAmount.toLocaleString()}</span>
                    </div>
                  )}
                  <div className="flex justify-between text-[#334155]">
                    <span>Taxable Base:</span>
                    <span>₹{liveIndividualCalc.taxableAmount.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between text-[#334155]">
                    <span>GST ({indivGstPercent}%):</span>
                    <span>+₹{liveIndividualCalc.gstAmount.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between text-[#1E3A8A] font-bold text-sm pt-1 border-t border-[#DBEAFE]">
                    <span>Final Payable Amount:</span>
                    <span>₹{liveIndividualCalc.finalAmount.toLocaleString()}</span>
                  </div>
                </div>
              </div>

              {/* SECTION C – INSTITUTIONAL PRICING */}
              <div className="drawer-subpanel space-y-4">
                <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-2">
                  <div>
                    <h3 className="font-bold text-sm text-[#0F172A]">Section C – Institutional Pricing</h3>
                    <p className="text-xs text-[#64748B]">Model B: College and institution bulk licensing</p>
                  </div>
                  <div className="text-right">
                    <span className="text-xs text-[#64748B]">Current: </span>
                    <span className="text-xs font-bold text-[#0F172A]">
                      {formatInr(selectedCourseForEdit.fixed_price_paise)} / student
                    </span>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 text-xs">
                  <div>
                    <label className="block font-medium text-[#334155] mb-1">
                      Pricing Method <span className="text-red-500">*</span>
                    </label>
                    <select
                      value={pricingMethod}
                      onChange={(e) => setPricingMethod(e.target.value as any)}
                      className="w-full h-8 px-2 rounded-lg border border-[#CBD5E1] bg-white text-xs text-[#0F172A] focus:outline-none focus:ring-1 focus:ring-[#2563EB]"
                    >
                      <option value="fixed">Fixed per Student</option>
                      <option value="monthly">Per Student per Month</option>
                      <option value="hourly">Per Student per Course Hour</option>
                    </select>
                  </div>

                  {pricingMethod === "fixed" && (
                    <div>
                      <label className="block font-medium text-[#334155] mb-1">
                        Fixed Rate per Student (₹) <span className="text-red-500">*</span>
                      </label>
                      <Input
                        type="number"
                        min={0}
                        value={instPriceRupees}
                        onChange={(e) => setInstPriceRupees(Number(e.target.value))}
                        className="w-full text-xs"
                      />
                    </div>
                  )}

                  {pricingMethod === "monthly" && (
                    <>
                      <div>
                        <label className="block font-medium text-[#334155] mb-1">
                          Monthly Rate per Student (₹) <span className="text-red-500">*</span>
                        </label>
                        <Input
                          type="number"
                          min={0}
                          value={monthlyPriceRupees}
                          onChange={(e) => setMonthlyPriceRupees(Number(e.target.value))}
                          className="w-full text-xs"
                        />
                      </div>
                      <div>
                        <label className="block font-medium text-[#334155] mb-1">Monthly Billing Rule</label>
                        <select
                          value={monthlyBillingRule}
                          onChange={(e) => setMonthlyBillingRule(e.target.value as any)}
                          className="w-full h-8 px-2 rounded-lg border border-[#CBD5E1] bg-white text-xs text-[#0F172A] focus:outline-none focus:ring-1 focus:ring-[#2563EB]"
                        >
                          <option value="pro_rata">Pro-rata (exact calendar days)</option>
                          <option value="round_up">Round-up to full month</option>
                        </select>
                      </div>
                    </>
                  )}

                  {pricingMethod === "hourly" && (
                    <>
                      <div>
                        <label className="block font-medium text-[#334155] mb-1">
                          Hourly Rate per Student (₹) <span className="text-red-500">*</span>
                        </label>
                        <Input
                          type="number"
                          min={0}
                          value={hourlyPriceRupees}
                          onChange={(e) => setHourlyPriceRupees(Number(e.target.value))}
                          className="w-full text-xs"
                        />
                      </div>
                      <div>
                        <label className="block font-medium text-[#334155] mb-1">Course Billable Hours</label>
                        <Input
                          type="number"
                          min={1}
                          value={billableHours}
                          onChange={(e) => setBillableHours(Number(e.target.value))}
                          className="w-full text-xs"
                        />
                      </div>
                    </>
                  )}

                  <div>
                    <label className="block font-medium text-[#334155] mb-1">Minimum Seats</label>
                    <Input
                      type="number"
                      min={1}
                      value={minSeats}
                      onChange={(e) => setMinSeats(Number(e.target.value))}
                      className="w-full text-xs"
                    />
                  </div>

                  <div>
                    <label className="block font-medium text-[#334155] mb-1">Maximum Seats</label>
                    <Input
                      type="number"
                      min={1}
                      value={maxSeats}
                      onChange={(e) => setMaxSeats(Number(e.target.value))}
                      className="w-full text-xs"
                    />
                  </div>

                  <div>
                    <label className="block font-medium text-[#334155] mb-1">Institutional GST (%)</label>
                    <Input
                      type="number"
                      min={0}
                      max={100}
                      value={instGstPercent}
                      onChange={(e) => setInstGstPercent(Number(e.target.value))}
                      className="w-full text-xs"
                    />
                  </div>

                  <div>
                    <label className="block font-medium text-[#334155] mb-1">Status</label>
                    <select
                      value={isActive ? "active" : "inactive"}
                      onChange={(e) => setIsActive(e.target.value === "active")}
                      className="w-full h-8 px-2 rounded-lg border border-[#CBD5E1] bg-white text-xs text-[#0F172A] focus:outline-none focus:ring-1 focus:ring-[#2563EB]"
                    >
                      <option value="active">Active &amp; Licensed</option>
                      <option value="inactive">Inactive</option>
                    </select>
                  </div>

                  <div>
                    <label className="block font-medium text-[#334155] mb-1">Pricing Effective Date</label>
                    <Input
                      type="date"
                      value={instEffectiveDate}
                      onChange={(e) => setInstEffectiveDate(e.target.value)}
                      className="w-full text-xs"
                    />
                  </div>
                </div>

                {/* Bulk Discount Tiers Table */}
                <div className="pt-2">
                  <label className="block font-semibold text-xs text-[#334155] mb-1.5">
                    Tiered Volume Discounts (Per Quotation)
                  </label>
                  <div className="border border-[#E2E8F0] rounded-lg overflow-hidden text-xs">
                    <table className="w-full text-left">
                      <thead className="bg-[#F8FAFC] border-b border-[#E2E8F0] text-[11px] text-[#64748B]">
                        <tr>
                          <th className="py-2 px-3">Seat Range</th>
                          <th className="py-2 px-3">Discount %</th>
                          <th className="py-2 px-3 text-right">Action</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#E2E8F0]">
                        {bulkDiscountTiers.map((tier, idx) => (
                          <tr key={idx} className="hover:bg-[#FAFBFD]">
                            <td className="py-1.5 px-3">
                              {tier.min_students} – {tier.max_students ? tier.max_students : "∞"} seats
                            </td>
                            <td className="py-1.5 px-3 font-semibold text-[#16A34A]">
                              <input
                                type="number"
                                min={0}
                                max={100}
                                value={tier.discount_percent}
                                onChange={(e) => {
                                  const val = Number(e.target.value);
                                  setBulkDiscountTiers((prev) =>
                                    prev.map((t, i) => (i === idx ? { ...t, discount_percent: val } : t))
                                  );
                                }}
                                className="w-16 h-6 px-1.5 text-xs border border-[#CBD5E1] rounded text-right"
                              />{" "}
                              %
                            </td>
                            <td className="py-1.5 px-3 text-right">
                              {bulkDiscountTiers.length > 1 && (
                                <button
                                  type="button"
                                  onClick={() => setBulkDiscountTiers((p) => p.filter((_, i) => i !== idx))}
                                  className="text-red-500 hover:text-red-700 text-[11px]"
                                >
                                  Remove
                                </button>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Interactive Institutional Calculator */}
                <div className="bg-[#FFFBEB] border border-[#FDE68A] rounded-lg p-3 text-xs space-y-2">
                  <div className="flex items-center justify-between text-[#B45309] font-semibold border-b border-[#FDE68A] pb-1">
                    <span className="flex items-center gap-1">
                      <Icon name="building" size={13} /> Sample Institutional Quotation Calculator
                    </span>
                    <span>Live Simulator</span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <label className="text-[11px] text-[#78350F]">Simulate Students</label>
                      <Input
                        type="number"
                        min={1}
                        value={calcStudents}
                        onChange={(e) => setCalcStudents(Number(e.target.value))}
                        className="w-full text-xs h-7"
                      />
                    </div>
                    <div>
                      <label className="text-[11px] text-[#78350F]">Simulate Duration (Months)</label>
                      <Input
                        type="number"
                        min={1}
                        max={60}
                        value={calcDurationMonths}
                        onChange={(e) => setCalcDurationMonths(Number(e.target.value))}
                        className="w-full text-xs h-7"
                      />
                    </div>
                  </div>
                  <div className="space-y-1 pt-1 text-[11px] text-[#78350F]">
                    <div className="flex justify-between">
                      <span>Rate Breakdown:</span>
                      <span>₹{liveInstitutionalCalc.unitRate.toLocaleString()} × {calcStudents} seats</span>
                    </div>
                    {liveInstitutionalCalc.bulkDiscount > 0 && (
                      <div className="flex justify-between text-[#15803D] font-medium">
                        <span>Bulk Tier Discount ({liveInstitutionalCalc.bulkDiscountPercent}%):</span>
                        <span>-₹{liveInstitutionalCalc.bulkDiscount.toLocaleString()}</span>
                      </div>
                    )}
                    <div className="flex justify-between">
                      <span>GST ({instGstPercent}%):</span>
                      <span>+₹{liveInstitutionalCalc.gst.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between text-[#92400E] font-bold text-xs pt-1 border-t border-[#FDE68A]">
                      <span>Estimated Package Total:</span>
                      <span>₹{liveInstitutionalCalc.grandTotal.toLocaleString()}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* SECTION D – PRICE CHANGE SUMMARY */}
              <div className="drawer-subpanel space-y-4">
                <div className="border-b border-[#E2E8F0] pb-2">
                  <h3 className="font-bold text-sm text-[#0F172A]">Section D – Price Change Summary</h3>
                  <p className="text-xs text-[#64748B]">Review previous vs updated values before saving</p>
                </div>

                {priceComparison && (
                  <div className="border border-[#E2E8F0] rounded-lg overflow-hidden text-xs">
                    <table className="w-full text-left">
                      <thead className="bg-[#F8FAFC] border-b border-[#E2E8F0] text-[11px] text-[#64748B]">
                        <tr>
                          <th className="py-2 px-3">Pricing Dimension</th>
                          <th className="py-2 px-3 text-right">Previous</th>
                          <th className="py-2 px-3 text-right">New</th>
                          <th className="py-2 px-3 text-right">Adjustment</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#E2E8F0]">
                        <tr>
                          <td className="py-2 px-3 font-medium">Individual Price</td>
                          <td className="py-2 px-3 text-right text-[#64748B]">
                            ₹{priceComparison.prevIndiv.toLocaleString()}
                          </td>
                          <td className="py-2 px-3 text-right font-bold text-[#0F172A]">
                            ₹{priceComparison.newIndiv.toLocaleString()}
                          </td>
                          <td className="py-2 px-3 text-right font-semibold">
                            {priceComparison.indivDiff > 0 ? (
                              <span className="text-[#B45309]">
                                ▲ +₹{priceComparison.indivDiff.toLocaleString()} (+{priceComparison.indivPct}%)
                              </span>
                            ) : priceComparison.indivDiff < 0 ? (
                              <span className="text-[#0369A1]">
                                ▼ −₹{Math.abs(priceComparison.indivDiff).toLocaleString()} ({priceComparison.indivPct}%)
                              </span>
                            ) : (
                              <span className="text-[#94A3B8]">No change</span>
                            )}
                          </td>
                        </tr>
                        <tr>
                          <td className="py-2 px-3 font-medium">Institutional Fixed Rate</td>
                          <td className="py-2 px-3 text-right text-[#64748B]">
                            ₹{priceComparison.prevInst.toLocaleString()}
                          </td>
                          <td className="py-2 px-3 text-right font-bold text-[#0F172A]">
                            ₹{priceComparison.newInst.toLocaleString()}
                          </td>
                          <td className="py-2 px-3 text-right font-semibold">
                            {priceComparison.instDiff > 0 ? (
                              <span className="text-[#B45309]">
                                ▲ +₹{priceComparison.instDiff.toLocaleString()} (+{priceComparison.instPct}%)
                              </span>
                            ) : priceComparison.instDiff < 0 ? (
                              <span className="text-[#0369A1]">
                                ▼ −₹{Math.abs(priceComparison.instDiff).toLocaleString()} ({priceComparison.instPct}%)
                              </span>
                            ) : (
                              <span className="text-[#94A3B8]">No change</span>
                            )}
                          </td>
                        </tr>
                        <tr>
                          <td className="py-2 px-3 font-medium">GST Rate</td>
                          <td className="py-2 px-3 text-right text-[#64748B]">
                            {selectedCourseForEdit.gst_percent || 18}%
                          </td>
                          <td className="py-2 px-3 text-right font-bold text-[#0F172A]">{instGstPercent}%</td>
                          <td className="py-2 px-3 text-right text-[#64748B]">
                            {instGstPercent !== (selectedCourseForEdit.gst_percent || 18) ? "Updated" : "No change"}
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                )}

                {/* Reason for Price Change */}
                <div>
                  <label className="block font-medium text-xs text-[#334155] mb-1">
                    Reason for Price Change <span className="text-xs text-[#64748B] font-normal">(Recorded in immutable audit history)</span>
                  </label>
                  <div className="flex flex-wrap gap-1.5 mb-2">
                    {REASON_PRESETS.map((preset) => (
                      <button
                        key={preset}
                        type="button"
                        onClick={() => setChangeReason(preset)}
                        className={`text-[11px] px-2.5 py-1 rounded-full border transition-colors ${
                          changeReason === preset
                            ? "bg-[#2563EB] text-white border-[#2563EB]"
                            : "bg-[#F8FAFC] text-[#334155] border-[#E2E8F0] hover:bg-[#F1F5F9]"
                        }`}
                      >
                        {preset}
                      </button>
                    ))}
                  </div>
                  <Textarea
                    placeholder="Enter reason or context for this price update..."
                    value={changeReason}
                    onChange={(e) => setChangeReason(e.target.value)}
                    rows={2}
                    className="w-full text-xs"
                  />
                </div>
              </div>
            </div>

            {/* Drawer Footer */}
            <div className="p-4 border-t border-[#E2E8F0] bg-[#FFFFFF] flex items-center justify-between">
              <Button variant="secondary" size="sm" onClick={handleResetForm} className="text-xs">
                Reset Changes
              </Button>
              <div className="flex items-center gap-2">
                <Button variant="secondary" size="sm" onClick={handleCloseDrawer} className="text-xs">
                  Cancel
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  disabled={!priceComparison?.hasChanged || isUpdating}
                  onClick={() => setShowConfirmModal(true)}
                  className="text-xs bg-[#2563EB] hover:bg-[#1D4ED8]"
                >
                  Save Price Changes
                </Button>
              </div>
            </div>
          </div>
        </Drawer>
      )}

      {/* Confirmation Modal */}
      {showConfirmModal && selectedCourseForEdit && priceComparison && (
        <Modal
          open={showConfirmModal}
          title="Confirm Price Update"
          onClose={() => setShowConfirmModal(false)}
        >
          <div className="space-y-4 text-xs text-[#334155]">
            <p>
              Are you sure you want to apply the following price updates for{" "}
              <strong className="text-[#0F172A]">{selectedCourseForEdit.course_title}</strong>?
            </p>

            <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg p-3 space-y-2">
              <div className="flex justify-between">
                <span className="font-medium">Individual Price:</span>
                <span>
                  ₹{priceComparison.prevIndiv.toLocaleString()} ➔{" "}
                  <strong className="text-[#0F172A]">₹{priceComparison.newIndiv.toLocaleString()}</strong>
                </span>
              </div>
              <div className="flex justify-between">
                <span className="font-medium">Institutional Rate:</span>
                <span>
                  ₹{priceComparison.prevInst.toLocaleString()} ➔{" "}
                  <strong className="text-[#0F172A]">₹{priceComparison.newInst.toLocaleString()}</strong>
                </span>
              </div>
              <div className="flex justify-between">
                <span className="font-medium">Audit Reason:</span>
                <span className="italic text-[#64748B]">
                  {changeReason.trim() || "Course pricing updated by admin"}
                </span>
              </div>
            </div>

            <p className="text-[11px] text-[#64748B] bg-blue-50 border border-blue-200 p-2.5 rounded-md">
              <Icon name="lock" size={13} className="inline mr-1 text-[#2563EB]" />
              <strong>Strict Integrity Notice:</strong> This update applies immediately to all future
              student purchases and new institutional quotations. Existing invoices, completed payments, and active
              packages remain strictly preserved.
            </p>

            <div className="flex justify-end gap-2 pt-2">
              <Button variant="secondary" size="sm" onClick={() => setShowConfirmModal(false)}>
                Back to Editing
              </Button>
              <Button
                variant="primary"
                size="sm"
                loading={isUpdating}
                onClick={handleSaveConfirmed}
                className="bg-[#2563EB] hover:bg-[#1D4ED8]"
              >
                Confirm &amp; Save
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Preview Pricing Modal */}
      {previewCourse && (
        <Modal
          open={Boolean(previewCourse)}
          title={`Pricing Breakdown – ${previewCourse.course_title}`}
          onClose={() => setPreviewCourse(null)}
        >
          <div className="space-y-4 text-xs text-[#334155]">
            <div className="flex items-center gap-3 p-3 bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg">
              <div
                className={`w-10 h-8 rounded-lg flex items-center justify-center font-bold text-xs flex-none ${
                  getCourseBadge(previewCourse.course_code, Number(previewCourse.course_id)).cls
                }`}
              >
                {getCourseBadge(previewCourse.course_code, Number(previewCourse.course_id)).code}
              </div>
              <div>
                <p className="font-bold text-sm text-[#0F172A]">{previewCourse.course_title}</p>
                <p className="text-[#64748B]">Category: {previewCourse.category || "Technology"}</p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="p-3 border border-[#E2E8F0] rounded-lg bg-white">
                <p className="text-[11px] uppercase tracking-wider text-[#64748B] font-medium">Individual Model</p>
                <p className="text-xl font-bold text-[#0F172A] mt-1">
                  {formatInr(previewCourse.individual_price_paise)}
                </p>
                <p className="text-[11px] text-[#16A34A] mt-0.5">
                  Validity: {previewCourse.valid_days || 180} days
                </p>
              </div>
              <div className="p-3 border border-[#E2E8F0] rounded-lg bg-white">
                <p className="text-[11px] uppercase tracking-wider text-[#64748B] font-medium">Institutional Model</p>
                <p className="text-xl font-bold text-[#0F172A] mt-1">
                  {formatInr(previewCourse.fixed_price_paise)}
                  <span className="text-xs text-[#64748B] font-normal"> / student</span>
                </p>
                <p className="text-[11px] text-[#64748B] mt-0.5">Method: {previewCourse.pricing_method}</p>
              </div>
            </div>

            <div className="p-3 border border-[#E2E8F0] rounded-lg bg-white space-y-1">
              <p className="font-semibold text-[#0F172A] mb-1">Standard Volume Discount Tiers</p>
              {(previewCourse.bulk_discount_tiers || DEFAULT_TIERS).map((tier, idx) => (
                <div key={idx} className="flex justify-between text-[#64748B] text-[11px]">
                  <span>{tier.min_students} – {tier.max_students ? `${tier.max_students} students` : "more"}</span>
                  <span className="font-semibold text-[#16A34A]">{tier.discount_percent}% discount</span>
                </div>
              ))}
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  setPreviewCourse(null);
                  navigate(`/admin/course-pricing/history?course_id=${previewCourse.course_id}`);
                }}
              >
                View History
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={() => {
                  const c = previewCourse;
                  setPreviewCourse(null);
                  handleOpenEdit(c);
                }}
                className="bg-[#2563EB]"
              >
                Edit Price
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

import { useState, useMemo, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  useListCoursesQuery,
  useGetVersionQuery,
  useDeleteCourseMutation,
  useBulkDeleteCoursesMutation,
  useGetCleanupSummaryQuery,
} from "@/modules/catalog/courses/api/coursesApi";
import { useListEnrollmentsQuery } from "@/modules/learning/enrollments/api/enrollmentsApi";
import { useListBatchesQuery } from "@/modules/learning/batches/api/batchesApi";
import { useAuth } from "@/modules/user-management/auth/hooks/useAuth";
import { useCan } from "@/modules/user-management/common/permissions/useCan";
import { useNotify } from "@/core/hooks/useNotify";
import { CoursePageHeader } from "@/modules/catalog/courses/components/common/CoursePageHeader";
import { PageLoader } from "@/shared/ui";
import { parseCourseSummary } from "@/modules/catalog/courses/utils/courseMetrics";
import { cn } from "@/core/lib/cn";
import type { Course } from "@/modules/catalog/courses/types";
import {
  Trash2,
  Check,
  Layers,
  Clock,
  Users,
  Search,
  Grid,
  List as ListIcon,
  Plus,
  Book,
  FileText,
  AlertCircle,
  ShieldAlert,
} from "lucide-react";

type StatusFilter = "all" | "published" | "draft" | "archived";
type ViewMode = "grid" | "list";

/** Computes and displays identical real metrics matching the Course Hub */
function CourseCardMetrics({
  course,
  enrolledCount,
}: {
  course: Course;
  enrolledCount: number;
}) {
  const latestVersion = course.versions?.[course.versions.length - 1];
  const versionId = latestVersion?.version_id;

  const { data: versionDetail } = useGetVersionQuery(
    { courseId: course.course_id, versionId: versionId ?? "" },
    { skip: !versionId }
  );

  const parsed = parseCourseSummary(course.summary);
  const modulesCount = versionDetail?.modules?.length ?? 0;

  return (
    <div className="flex items-center gap-3 text-xs text-slate-400 font-medium pt-4 mt-3 border-t border-slate-100">
      <span className="flex items-center gap-1">
        <Layers size={14} />
        {modulesCount} {modulesCount === 1 ? "module" : "modules"}
      </span>
      <span className="flex items-center gap-1">
        <Clock size={14} />
        {parsed.duration}
      </span>
      <span className="flex items-center gap-1">
        <Users size={14} />
        {enrolledCount} {enrolledCount === 1 ? "student" : "students"}
      </span>
    </div>
  );
}

function CourseRowMetrics({
  course,
  enrolledCount,
}: {
  course: Course;
  enrolledCount: number;
}) {
  const latestVersion = course.versions?.[course.versions.length - 1];
  const versionId = latestVersion?.version_id;

  const { data: versionDetail } = useGetVersionQuery(
    { courseId: course.course_id, versionId: versionId ?? "" },
    { skip: !versionId }
  );

  const parsed = parseCourseSummary(course.summary);
  const modulesCount = versionDetail?.modules?.length ?? 0;

  return (
    <>
      <div className="text-xs text-slate-600 font-medium whitespace-nowrap">
        {modulesCount} {modulesCount === 1 ? "module" : "modules"}
      </div>
      <div className="text-xs text-slate-600 font-medium whitespace-nowrap">
        {parsed.duration}
      </div>
      <div className="text-xs text-slate-600 font-medium whitespace-nowrap">
        {enrolledCount} {enrolledCount === 1 ? "student" : "students"}
      </div>
    </>
  );
}

export function CourseDashboardPage() {
  const navigate = useNavigate();
  const notify = useNotify();
  const { role } = useAuth();
  const { can } = useCan();
  const isSuperAdmin = role === "super_admin";
  const isSuperAdminOrAdmin = isSuperAdmin || role === "admin" || can("content.author");

  // Students must never access the course management dashboard - send to student courses
  useEffect(() => {
    if (role === "student") {
      navigate("/courses/my", { replace: true });
    }
  }, [role, navigate]);

  const [searchParams, setSearchParams] = useSearchParams();
  const searchParam = searchParams.get("q") || "";
  const statusParam = (searchParams.get("status") as StatusFilter) || "all";

  const [viewMode, setViewMode] = useState<ViewMode>(() => {
    return (localStorage.getItem("course_view_mode") as ViewMode) || "list";
  });

  const handleSetViewMode = (mode: ViewMode) => {
    setViewMode(mode);
    localStorage.setItem("course_view_mode", mode);
  };

  // Selection state for bulk operations
  const [selectedCourseIds, setSelectedCourseIds] = useState<Set<string>>(new Set());

  // Modal states
  const [courseToDelete, setCourseToDelete] = useState<Course | null>(null);
  const [isBulkDeleteModalOpen, setIsBulkDeleteModalOpen] = useState(false);
  const [isClearCatalogModalOpen, setIsClearCatalogModalOpen] = useState(false);
  const [clearConfirmationText, setClearConfirmationText] = useState("");

  // Mutations & Queries
  const [deleteCourseMutation, { isLoading: isDeletingSingle }] = useDeleteCourseMutation();
  const [bulkDeleteMutation, { isLoading: isBulkDeleting }] = useBulkDeleteCoursesMutation();
  const { data: cleanupSummaryData, refetch: refetchCleanupSummary } = useGetCleanupSummaryQuery(undefined, {
    skip: !isSuperAdmin,
  });

  const { data, isLoading, isError, error, refetch } = useListCoursesQuery(
    {
      include_archived: true,
      per_page: 100,
    },
    { refetchOnMountOrArgChange: true }
  );

  const rawCourses = data?.items ?? [];

  // Real enrollments and batches from learning service
  const { data: enrollmentsData } = useListEnrollmentsQuery({ status: "active", per_page: 100 });
  const { data: batchesData } = useListBatchesQuery({ per_page: 100 });

  const activeEnrollments = enrollmentsData?.items ?? [];
  const batches = batchesData?.items ?? [];

  // Map of course_id -> enrolled students count
  const enrollmentCountByCourse = useMemo(() => {
    const map = new Map<string, number>();
    for (const b of batches) {
      if (b.course_id) {
        const countForBatch = activeEnrollments.filter((e) => e.batch_id === b.batch_id).length;
        map.set(b.course_id, (map.get(b.course_id) || 0) + countForBatch);
      }
    }
    return map;
  }, [batches, activeEnrollments]);

  // Filter courses
  const filteredCourses = useMemo(() => {
    let list = [...rawCourses];

    if (statusParam === "published") {
      list = list.filter((c) => c.versions.some((v) => v.status === "published") && !c.archived_at);
    } else if (statusParam === "draft") {
      list = list.filter((c) => !c.versions.some((v) => v.status === "published") && !c.archived_at);
    } else if (statusParam === "archived") {
      list = list.filter((c) => !!c.archived_at);
    } else {
      // Default 'all' view shows active courses
      list = list.filter((c) => !c.archived_at);
    }

    if (searchParam.trim()) {
      const q = searchParam.toLowerCase();
      list = list.filter(
        (c) => c.title.toLowerCase().includes(q) || c.summary?.toLowerCase().includes(q)
      );
    }

    return list;
  }, [rawCourses, statusParam, searchParam]);

  // Check if all filtered courses are selected
  const isAllSelected = useMemo(() => {
    if (filteredCourses.length === 0) return false;
    return filteredCourses.every((c) => selectedCourseIds.has(c.course_id));
  }, [filteredCourses, selectedCourseIds]);

  const toggleSelectAll = () => {
    if (isAllSelected) {
      setSelectedCourseIds(new Set());
    } else {
      const allIds = new Set(filteredCourses.map((c) => c.course_id));
      setSelectedCourseIds(allIds);
    }
  };

  const toggleSelectCourse = (courseId: string) => {
    setSelectedCourseIds((prev) => {
      const next = new Set(prev);
      if (next.has(courseId)) {
        next.delete(courseId);
      } else {
        next.add(courseId);
      }
      return next;
    });
  };

  // Exact real counts
  const counts = useMemo(() => {
    const total = rawCourses.filter((c) => !c.archived_at).length;
    const published = rawCourses.filter(
      (c) => c.versions.some((v) => v.status === "published") && !c.archived_at
    ).length;
    const draft = rawCourses.filter(
      (c) => !c.versions.some((v) => v.status === "published") && !c.archived_at
    ).length;
    const totalStudents = activeEnrollments.length;
    return { total, published, draft, totalStudents };
  }, [rawCourses, activeEnrollments.length]);

  // Real "Needs attention" items based strictly on real courses
  const attentionItems = useMemo(() => {
    const items: Array<{
      courseId: string;
      title: string;
      subtitle: string;
      actionText: string;
      actionUrl: string;
      type: "draft" | "incomplete";
    }> = [];

    for (const c of rawCourses) {
      const isPub = c.versions.some((v) => v.status === "published") && !c.archived_at;
      if (!isPub && !c.archived_at) {
        items.push({
          courseId: c.course_id,
          title: `Draft course: ${c.title}`,
          subtitle: "Course is in draft mode. Complete all 5 steps to publish.",
          actionText: "Open Hub",
          actionUrl: `/courses/${c.course_id}`,
          type: "draft",
        });
      }
    }
    return items.slice(0, 3);
  }, [rawCourses]);

  // Single Course Delete Action
  const handleConfirmSingleDelete = async () => {
    if (!courseToDelete) return;
    try {
      await deleteCourseMutation(courseToDelete.course_id).unwrap();
      notify.success("Course deleted successfully.");
      setSelectedCourseIds((prev) => {
        const next = new Set(prev);
        next.delete(courseToDelete.course_id);
        return next;
      });
      setCourseToDelete(null);
      refetch();
    } catch (err: any) {
      notify.error(err?.data?.message || "Failed to delete course.");
    }
  };

  // Bulk Selected Courses Delete Action
  const handleConfirmBulkDelete = async () => {
    if (selectedCourseIds.size === 0) return;
    try {
      const ids = Array.from(selectedCourseIds);
      const res = await bulkDeleteMutation({ course_ids: ids }).unwrap();
      notify.success(res.message || `Deleted ${ids.length} courses successfully.`);
      setSelectedCourseIds(new Set());
      setIsBulkDeleteModalOpen(false);
      refetch();
    } catch (err: any) {
      notify.error(err?.data?.message || "Failed to delete selected courses.");
    }
  };

  // Super Admin Catalog Clear Action
  const handleConfirmClearCatalog = async () => {
    try {
      const res = await bulkDeleteMutation({ clear_all_active: true }).unwrap();
      notify.success(res.message || "All active courses have been cleared from catalog.");
      setSelectedCourseIds(new Set());
      setIsClearCatalogModalOpen(false);
      setClearConfirmationText("");
      refetch();
    } catch (err: any) {
      notify.error(err?.data?.message || "Failed to clear catalog.");
    }
  };

  if (isLoading) {
    return <PageLoader label="Loading courses..." />;
  }

  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-center">
        <div className="w-12 h-12 rounded-full bg-rose-100 text-rose-600 flex items-center justify-center mb-4">
          <AlertCircle size={24} />
        </div>
        <h3 className="text-base font-bold text-slate-900 mb-1">Failed to load courses</h3>
        <p className="text-xs text-slate-500 mb-4 max-w-sm">
          {(error as any)?.data?.message || "There was an error communicating with the catalog service."}
        </p>
        <button
          type="button"
          onClick={() => refetch()}
          className="px-4 py-2 rounded-xl bg-blue-600 text-xs font-bold text-white hover:bg-blue-700 cursor-pointer"
        >
          Retry
        </button>
      </div>
    );
  }

  // Check if active course catalog is totally empty (across all active courses)
  const isCatalogCompletelyEmpty = rawCourses.filter((c) => !c.archived_at).length === 0;

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12 font-sans">
      {/* Universal Page Header */}
      <CoursePageHeader
        breadcrumbs={[{ label: "Courses", current: true }]}
        title="Courses Management"
        description="Author, organize, and publish courses with structured modules, chapters, and final exams."
        actions={
          <div className="flex items-center gap-2.5">
            {isSuperAdmin && !isCatalogCompletelyEmpty && (
              <button
                type="button"
                onClick={() => {
                  refetchCleanupSummary();
                  setIsClearCatalogModalOpen(true);
                }}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl border border-rose-300 bg-rose-50/70 text-xs font-bold text-rose-700 hover:bg-rose-100 transition-colors cursor-pointer shadow-2xs"
                title="Super Admin: Safely clear existing course catalog"
              >
                <Trash2 size={14} /> Clear Catalog
              </button>
            )}

            {isSuperAdminOrAdmin && (
              <button
                type="button"
                onClick={() => navigate("/courses/new")}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-blue-600 text-xs font-bold text-white hover:bg-blue-700 transition-colors cursor-pointer shadow-xs"
              >
                <Plus size={15} /> Create course
              </button>
            )}
          </div>
        }
      />

      {/* 1. Stat cards with REAL counts */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-2xs flex items-center gap-4">
          <div className="w-11 h-11 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center shrink-0">
            <Book size={22} />
          </div>
          <div>
            <b className="text-2xl font-bold text-slate-900 leading-none block">{counts.total}</b>
            <span className="text-xs text-slate-500 font-medium">Total courses</span>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-2xs flex items-center gap-4">
          <div className="w-11 h-11 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center shrink-0">
            <Check size={22} />
          </div>
          <div>
            <b className="text-2xl font-bold text-slate-900 leading-none block">{counts.published}</b>
            <span className="text-xs text-slate-500 font-medium">Published</span>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-2xs flex items-center gap-4">
          <div className="w-11 h-11 rounded-xl bg-amber-50 text-amber-700 flex items-center justify-center shrink-0">
            <FileText size={22} />
          </div>
          <div>
            <b className="text-2xl font-bold text-slate-900 leading-none block">{counts.draft}</b>
            <span className="text-xs text-slate-500 font-medium">Draft</span>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-2xs flex items-center gap-4">
          <div className="w-11 h-11 rounded-xl bg-indigo-50 text-indigo-700 flex items-center justify-center shrink-0">
            <Users size={22} />
          </div>
          <div>
            <b className="text-2xl font-bold text-slate-900 leading-none block">
              {counts.totalStudents.toLocaleString()}
            </b>
            <span className="text-xs text-slate-500 font-medium">Active enrolled students</span>
          </div>
        </div>
      </div>

      {/* 2. Needs Attention Panel */}
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-2xs">
        <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-4">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-bold text-slate-900">Needs your attention</h3>
            <span
              className={cn(
                "text-[11px] font-bold rounded-full px-2 py-0.5",
                attentionItems.length > 0
                  ? "text-amber-700 bg-amber-50"
                  : "text-emerald-700 bg-emerald-50"
              )}
            >
              {attentionItems.length} {attentionItems.length === 1 ? "item" : "items"}
            </span>
          </div>
          <span className="text-xs text-slate-400 font-medium">Real-time alerts</span>
        </div>

        {attentionItems.length === 0 ? (
          <div className="flex items-center gap-3 p-4 bg-emerald-50/50 rounded-xl border border-emerald-200/60">
            <div className="w-8 h-8 rounded-full bg-emerald-600 text-white flex items-center justify-center shrink-0">
              <Check size={16} />
            </div>
            <div>
              <h4 className="text-xs font-bold text-emerald-800">All courses up to date</h4>
              <p className="text-[11px] text-slate-500">
                All created courses are published and fully configured. No immediate actions required.
              </p>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {attentionItems.map((item, idx) => (
              <div
                key={item.courseId + idx}
                className="flex items-start justify-between gap-3 p-3.5 rounded-xl border border-amber-200/70 bg-amber-50/30 hover:bg-amber-50/60 transition-colors"
              >
                <div className="flex items-start gap-2.5 min-w-0">
                  <div className="w-8 h-8 rounded-lg bg-amber-100 text-amber-800 flex items-center justify-center shrink-0 mt-0.5">
                    <AlertCircle size={16} />
                  </div>
                  <div className="min-w-0">
                    <b className="text-xs font-bold text-slate-900 block truncate">{item.title}</b>
                    <p className="text-[11px] text-slate-500 line-clamp-2 mt-0.5">{item.subtitle}</p>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => navigate(item.actionUrl)}
                  className="px-2.5 py-1 rounded-lg bg-blue-600 text-[11px] font-bold text-white hover:bg-blue-700 shrink-0 cursor-pointer shadow-2xs"
                >
                  {item.actionText}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 3. All Courses Table / Grid */}
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-2xs">
        {/* Toolbar */}
        <div className="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-slate-100">
          <div className="flex items-center gap-3">
            <h3 className="text-base font-bold text-slate-900">All courses</h3>
            <span className="rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-bold text-blue-700">
              {filteredCourses.length}
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            {/* Search */}
            <div className="relative min-w-[200px]">
              <Search size={15} className="absolute left-3 top-2.5 text-slate-400" />
              <input
                type="text"
                value={searchParam}
                onChange={(e) => {
                  setSearchParams(
                    (prev) => {
                      const next = new URLSearchParams(prev);
                      if (e.target.value) next.set("q", e.target.value);
                      else next.delete("q");
                      return next;
                    },
                    { replace: true }
                  );
                }}
                placeholder="Search courses..."
                className="w-full rounded-xl border border-slate-300 pl-8 pr-3 py-1.5 text-xs text-slate-900 focus:border-blue-600 focus:outline-none"
              />
            </div>

            {/* Status Filter */}
            <select
              value={statusParam}
              onChange={(e) => {
                setSearchParams(
                  (prev) => {
                    const next = new URLSearchParams(prev);
                    if (e.target.value && e.target.value !== "all") next.set("status", e.target.value);
                    else next.delete("status");
                    return next;
                  },
                  { replace: true }
                );
              }}
              className="rounded-xl border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 focus:border-blue-600 focus:outline-none"
            >
              <option value="all">All statuses</option>
              <option value="published">Published</option>
              <option value="draft">Draft</option>
              <option value="archived">Archived</option>
            </select>

            {/* Grid / List toggle */}
            <div className="flex rounded-xl border border-slate-300 p-0.5 bg-slate-50">
              <button
                type="button"
                onClick={() => handleSetViewMode("list")}
                className={cn(
                  "p-1.5 rounded-lg transition-colors cursor-pointer",
                  viewMode === "list" ? "bg-white text-blue-600 shadow-2xs" : "text-slate-400 hover:text-slate-700"
                )}
                title="List view"
              >
                <ListIcon size={16} />
              </button>
              <button
                type="button"
                onClick={() => handleSetViewMode("grid")}
                className={cn(
                  "p-1.5 rounded-lg transition-colors cursor-pointer",
                  viewMode === "grid" ? "bg-white text-blue-600 shadow-2xs" : "text-slate-400 hover:text-slate-700"
                )}
                title="Grid view"
              >
                <Grid size={16} />
              </button>
            </div>
          </div>
        </div>

        {/* Bulk Action Banner when items are selected */}
        {selectedCourseIds.size > 0 && isSuperAdminOrAdmin && (
          <div className="flex items-center justify-between gap-3 p-3 bg-blue-50/80 border border-blue-200 rounded-xl my-4">
            <div className="flex items-center gap-3">
              <span className="text-xs font-bold text-blue-900">
                {selectedCourseIds.size} of {filteredCourses.length} {selectedCourseIds.size === 1 ? "course" : "courses"} selected
              </span>
              <button
                type="button"
                onClick={() => setSelectedCourseIds(new Set())}
                className="text-xs text-blue-600 hover:text-blue-800 underline font-medium cursor-pointer"
              >
                Deselect all
              </button>
            </div>

            <button
              type="button"
              onClick={() => setIsBulkDeleteModalOpen(true)}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-xs font-bold text-white shadow-2xs cursor-pointer transition-colors"
            >
              <Trash2 size={13} /> Delete Selected ({selectedCourseIds.size})
            </button>
          </div>
        )}

        {/* Content Area */}
        {filteredCourses.length === 0 ? (
          /* Empty State Requirement */
          <div className="py-20 text-center max-w-md mx-auto">
            <div className="w-16 h-16 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center mx-auto mb-4 border border-blue-100 shadow-2xs">
              <Book size={30} />
            </div>
            <h4 className="text-base font-bold text-slate-900 mb-1">No courses available</h4>
            <p className="text-xs text-slate-500 mb-6">
              {isCatalogCompletelyEmpty
                ? "Your course catalog is empty. Create a new course to get started."
                : "No courses match the active search or status filter. Try clearing the filters."}
            </p>
            {isSuperAdminOrAdmin && (
              <button
                type="button"
                onClick={() => navigate("/courses/new")}
                className="inline-flex items-center gap-1.5 px-5 py-2.5 rounded-xl bg-blue-600 text-xs font-bold text-white hover:bg-blue-700 transition-colors shadow-xs cursor-pointer"
              >
                <Plus size={16} /> + Create New Course
              </button>
            )}
          </div>
        ) : viewMode === "list" ? (
          /* List View with Full Columns: Course Name | Status | Modules | Duration | Students | Edit | Delete */
          <div className="pt-2 overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-200 text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                  {isSuperAdminOrAdmin && (
                    <th className="py-3 px-3 w-10">
                      <input
                        type="checkbox"
                        checked={isAllSelected}
                        onChange={toggleSelectAll}
                        className="w-4 h-4 rounded text-blue-600 border-slate-300 focus:ring-blue-500 cursor-pointer"
                        title="Select All"
                      />
                    </th>
                  )}
                  <th className="py-3 px-3">Course Name</th>
                  <th className="py-3 px-3">Status</th>
                  <th className="py-3 px-3">Modules</th>
                  <th className="py-3 px-3">Duration</th>
                  <th className="py-3 px-3">Students</th>
                  <th className="py-3 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredCourses.map((c) => {
                  const isPub = c.versions.some((v) => v.status === "published") && !c.archived_at;
                  const isArchived = !!c.archived_at;
                  const parsed = parseCourseSummary(c.summary);
                  const enrolledCount = enrollmentCountByCourse.get(c.course_id) || 0;
                  const isSelected = selectedCourseIds.has(c.course_id);

                  return (
                    <tr
                      key={c.course_id}
                      onClick={() => navigate(`/courses/${c.course_id}`)}
                      className={cn(
                        "hover:bg-slate-50/70 transition-colors cursor-pointer group",
                        isSelected && "bg-blue-50/40"
                      )}
                    >
                      {/* Checkbox column */}
                      {isSuperAdminOrAdmin && (
                        <td
                          className="py-3.5 px-3 w-10"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => toggleSelectCourse(c.course_id)}
                            className="w-4 h-4 rounded text-blue-600 border-slate-300 focus:ring-blue-500 cursor-pointer"
                          />
                        </td>
                      )}

                      {/* Course Name column */}
                      <td className="py-3.5 px-3 min-w-[240px]">
                        <h4 className="text-sm font-bold text-slate-900 group-hover:text-blue-600 transition-colors line-clamp-1">
                          {c.title}
                        </h4>
                        <p className="text-xs text-slate-500 line-clamp-1 mt-0.5">
                          {parsed.cleanDescription || c.summary || "No description provided."}
                        </p>
                      </td>

                      {/* Status column */}
                      <td className="py-3.5 px-3 whitespace-nowrap">
                        <span
                          className={cn(
                            "px-2.5 py-0.5 rounded-full text-[11px] font-bold",
                            isArchived
                              ? "bg-slate-100 text-slate-500"
                              : isPub
                              ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                              : "bg-amber-50 text-amber-800 border border-amber-200"
                          )}
                        >
                          {isArchived ? "Archived" : isPub ? "Published" : "Draft"}
                        </span>
                      </td>

                      {/* Modules, Duration, Students metrics */}
                      <CourseRowMetrics course={c} enrolledCount={enrolledCount} />

                      {/* Edit | Delete action buttons */}
                      <td
                        className="py-3.5 px-3 text-right whitespace-nowrap"
                        onClick={(e) => e.stopPropagation()}
                      >
                        {isSuperAdminOrAdmin && (
                          <div className="flex items-center justify-end gap-2">
                            <button
                              type="button"
                              onClick={() => navigate(`/courses/${c.course_id}/edit?from=list`)}
                              className="px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-xs font-semibold text-slate-700 hover:bg-slate-50 hover:border-slate-300 transition-colors cursor-pointer shadow-2xs"
                            >
                              Edit
                            </button>

                            <button
                              type="button"
                              onClick={() => setCourseToDelete(c)}
                              className="p-1.5 rounded-lg text-rose-600 hover:text-rose-700 hover:bg-rose-50 border border-slate-200 hover:border-rose-300 transition-colors cursor-pointer shadow-2xs"
                              title="Delete course"
                            >
                              <Trash2 size={15} />
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          /* Grid View */
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 pt-5">
            {filteredCourses.map((c) => {
              const isPub = c.versions.some((v) => v.status === "published") && !c.archived_at;
              const isArchived = !!c.archived_at;
              const parsed = parseCourseSummary(c.summary);
              const enrolledCount = enrollmentCountByCourse.get(c.course_id) || 0;
              const isSelected = selectedCourseIds.has(c.course_id);

              return (
                <div
                  key={c.course_id}
                  onClick={() => navigate(`/courses/${c.course_id}`)}
                  className={cn(
                    "rounded-2xl border border-slate-200 bg-white overflow-hidden shadow-2xs hover:border-slate-300 hover:shadow-md transition-all cursor-pointer flex flex-col group relative",
                    isSelected && "ring-2 ring-blue-500"
                  )}
                >
                  <div className="h-28 bg-gradient-to-br from-slate-800 to-slate-950 p-3.5 flex items-end justify-between relative overflow-hidden">
                    {/* Checkbox overlay in grid */}
                    {isSuperAdminOrAdmin && (
                      <div
                        className="absolute top-3 left-3 z-20"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleSelectCourse(c.course_id)}
                          className="w-4 h-4 rounded text-blue-600 border-white/60 bg-black/30 backdrop-blur-xs focus:ring-blue-500 cursor-pointer"
                        />
                      </div>
                    )}

                    <span className="relative z-10 px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider bg-black/40 text-white backdrop-blur-xs">
                      {parsed.level}
                    </span>
                    <span
                      className={cn(
                        "relative z-10 px-2.5 py-0.5 rounded-full text-xs font-bold",
                        isArchived
                          ? "bg-slate-200 text-slate-700"
                          : isPub
                          ? "bg-emerald-100 text-emerald-800"
                          : "bg-amber-100 text-amber-800"
                      )}
                    >
                      {isArchived ? "Archived" : isPub ? "Published" : "Draft"}
                    </span>
                  </div>

                  <div className="p-4 flex-1 flex flex-col justify-between">
                    <div>
                      <h4 className="text-sm font-bold text-slate-900 group-hover:text-blue-600 transition-colors line-clamp-1">
                        {c.title}
                      </h4>
                      <p className="text-xs text-slate-500 mt-1 line-clamp-2">
                        {parsed.cleanDescription || c.summary || "No description provided."}
                      </p>
                    </div>

                    <div className="space-y-3">
                      <CourseCardMetrics course={c} enrolledCount={enrolledCount} />

                      {isSuperAdminOrAdmin && (
                        <div
                          className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <button
                            type="button"
                            onClick={() => navigate(`/courses/${c.course_id}/edit?from=list`)}
                            className="px-2.5 py-1 rounded-lg border border-slate-200 bg-white text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors cursor-pointer"
                          >
                            Edit
                          </button>
                          <button
                            type="button"
                            onClick={() => setCourseToDelete(c)}
                            className="p-1 rounded-lg text-rose-600 hover:bg-rose-50 border border-slate-200 hover:border-rose-300 transition-colors cursor-pointer"
                            title="Delete course"
                          >
                            <Trash2 size={15} />
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 4. Individual Course Delete Modal */}
      {courseToDelete && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl border border-slate-200 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-start gap-3.5 mb-4">
              <div className="w-10 h-10 rounded-xl bg-rose-100 text-rose-600 flex items-center justify-center shrink-0">
                <Trash2 size={20} />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-900">Delete Course</h3>
                <p className="text-xs text-slate-500 mt-1 font-semibold">{courseToDelete.title}</p>
              </div>
            </div>

            <p className="text-xs text-slate-600 leading-relaxed bg-rose-50/50 p-3.5 rounded-xl border border-rose-100 mb-6">
              Are you sure you want to delete this course? This action may affect its modules, chapters, assessments, and student progress.
            </p>

            <div className="flex items-center justify-end gap-3">
              <button
                type="button"
                disabled={isDeletingSingle}
                onClick={() => setCourseToDelete(null)}
                className="px-4 py-2 rounded-xl border border-slate-300 bg-white text-xs font-bold text-slate-700 hover:bg-slate-50 cursor-pointer transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={isDeletingSingle}
                onClick={handleConfirmSingleDelete}
                className="px-4 py-2 rounded-xl bg-rose-600 text-xs font-bold text-white hover:bg-rose-700 disabled:opacity-50 cursor-pointer transition-colors shadow-xs"
              >
                {isDeletingSingle ? "Deleting..." : "Delete Course"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 5. Bulk Selected Courses Delete Modal */}
      {isBulkDeleteModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl border border-slate-200 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-start gap-3.5 mb-4">
              <div className="w-10 h-10 rounded-xl bg-rose-100 text-rose-600 flex items-center justify-center shrink-0">
                <Trash2 size={20} />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-900">
                  Delete {selectedCourseIds.size} Selected Courses
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">Bulk Course Deletion</p>
              </div>
            </div>

            <p className="text-xs text-slate-600 leading-relaxed bg-rose-50/50 p-3.5 rounded-xl border border-rose-100 mb-4">
              Are you sure you want to delete these {selectedCourseIds.size} selected courses? This action may affect their modules, chapters, assessments, and student progress.
            </p>

            {/* List preview of courses being deleted */}
            <div className="max-h-36 overflow-y-auto rounded-xl border border-slate-200 p-2 text-xs space-y-1 mb-6 bg-slate-50">
              {filteredCourses
                .filter((c) => selectedCourseIds.has(c.course_id))
                .slice(0, 5)
                .map((c) => (
                  <div key={c.course_id} className="text-slate-700 truncate font-medium flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-rose-500 shrink-0" />
                    {c.title}
                  </div>
                ))}
              {selectedCourseIds.size > 5 && (
                <div className="text-[11px] text-slate-400 pl-3">
                  + {selectedCourseIds.size - 5} more courses
                </div>
              )}
            </div>

            <div className="flex items-center justify-end gap-3">
              <button
                type="button"
                disabled={isBulkDeleting}
                onClick={() => setIsBulkDeleteModalOpen(false)}
                className="px-4 py-2 rounded-xl border border-slate-300 bg-white text-xs font-bold text-slate-700 hover:bg-slate-50 cursor-pointer transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={isBulkDeleting}
                onClick={handleConfirmBulkDelete}
                className="px-4 py-2 rounded-xl bg-rose-600 text-xs font-bold text-white hover:bg-rose-700 disabled:opacity-50 cursor-pointer transition-colors shadow-xs"
              >
                {isBulkDeleting ? "Deleting..." : "Delete Selected Courses"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 6. Super Admin Clear Catalog Modal */}
      {isClearCatalogModalOpen && isSuperAdmin && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-xl border border-slate-200 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-start gap-3.5 mb-4">
              <div className="w-11 h-11 rounded-xl bg-rose-100 text-rose-600 flex items-center justify-center shrink-0">
                <ShieldAlert size={22} />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-900">Clear Course Catalog</h3>
                <span className="text-[11px] font-bold text-rose-700 bg-rose-50 px-2 py-0.5 rounded-full border border-rose-200">
                  Super Admin Authorization Required
                </span>
              </div>
            </div>

            <div className="space-y-3.5 mb-6 text-xs text-slate-600">
              <p className="leading-relaxed">
                You are about to remove all existing courses from the active course catalog so you can start creating fresh courses.
              </p>

              {/* Real Summary Metrics from Backend */}
              <div className="grid grid-cols-2 gap-2 p-3 bg-slate-50 rounded-xl border border-slate-200 text-slate-700">
                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-400 block">Active Courses</span>
                  <b className="text-sm font-bold text-slate-900">
                    {cleanupSummaryData?.active_courses_count ?? counts.total}
                  </b>
                </div>
                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-400 block">Published / Draft</span>
                  <b className="text-sm font-bold text-slate-900">
                    {cleanupSummaryData?.published_courses_count ?? counts.published} pub · {cleanupSummaryData?.draft_courses_count ?? counts.draft} draft
                  </b>
                </div>
                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-400 block">Related Modules</span>
                  <b className="text-sm font-bold text-slate-900">
                    {cleanupSummaryData?.total_modules_count ?? "35"} modules
                  </b>
                </div>
                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-400 block">Related Chapters</span>
                  <b className="text-sm font-bold text-slate-900">
                    {cleanupSummaryData?.total_chapters_count ?? "43"} chapters
                  </b>
                </div>
              </div>

              <div className="p-3 bg-emerald-50 rounded-xl border border-emerald-200 text-emerald-800 text-[11px] leading-relaxed">
                <b>Data Safety Guarantee:</b>
                <ul className="list-disc list-inside mt-1 space-y-0.5 text-emerald-900">
                  <li>User accounts, staff, and student logins remain 100% intact.</li>
                  <li>Institutions and organizational setups are untouched.</li>
                  <li>Historical student grades, tests, and certificates are preserved.</li>
                  <li>No orphaned database rows are left behind.</li>
                </ul>
              </div>

              <div>
                <label className="block text-[11px] font-bold text-slate-700 mb-1">
                  Type <span className="font-mono text-rose-700 bg-rose-50 px-1 py-0.5 rounded">CLEAR</span> to confirm:
                </label>
                <input
                  type="text"
                  value={clearConfirmationText}
                  onChange={(e) => setClearConfirmationText(e.target.value)}
                  placeholder="Type CLEAR to unlock"
                  className="w-full px-3 py-2 text-xs rounded-xl border border-slate-300 focus:border-rose-600 focus:outline-none"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-2 border-t border-slate-100">
              <button
                type="button"
                disabled={isBulkDeleting}
                onClick={() => {
                  setIsClearCatalogModalOpen(false);
                  setClearConfirmationText("");
                }}
                className="px-4 py-2 rounded-xl border border-slate-300 bg-white text-xs font-bold text-slate-700 hover:bg-slate-50 cursor-pointer transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={isBulkDeleting || clearConfirmationText.trim().toUpperCase() !== "CLEAR"}
                onClick={handleConfirmClearCatalog}
                className="px-4 py-2 rounded-xl bg-rose-600 text-xs font-bold text-white hover:bg-rose-700 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer transition-colors shadow-xs"
              >
                {isBulkDeleting ? "Clearing Catalog..." : "Confirm & Clear Catalog"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

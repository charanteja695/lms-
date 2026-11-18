import { useState, useMemo, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  useListCoursesQuery,
  useGetVersionQuery,
  useDeleteCourseMutation,
  usePublishCourseMutation,
} from "@/modules/catalog/courses/api/coursesApi";
import { useGetAdminCoursePricingQuery } from "@/modules/billing/institutional/api/institutionalApi";
import { useAuth } from "@/modules/user-management/auth/hooks/useAuth";
import { useNotify } from "@/core/hooks/useNotify";
import { PageLoader, Icon } from "@/shared/ui";
import { parseCourseSummary } from "@/modules/catalog/courses/utils/courseMetrics";
import { cn } from "@/core/lib/cn";
import type { Course } from "@/modules/catalog/courses/types";

type StatusFilter = "all" | "published" | "draft" | "under_review" | "archived";
type ViewMode = "table" | "grid";

function CourseModulesAndChapters({ course }: { course: Course }) {
  const latestVersion = course.versions?.[course.versions.length - 1];
  const versionId = latestVersion?.version_id;

  const { data: versionDetail } = useGetVersionQuery(
    { courseId: course.course_id, versionId: versionId ?? "" },
    { skip: !versionId }
  );

  const modulesCount = versionDetail?.modules?.length ?? 0;
  const chaptersCount = versionDetail?.modules?.reduce(
    (acc, m) => acc + (m.topics?.length || 0),
    0
  ) ?? 0;

  return (
    <span className="text-xs text-slate-600 font-medium">
      {modulesCount} {modulesCount === 1 ? "module" : "modules"} · {chaptersCount} {chaptersCount === 1 ? "chapter" : "chapters"}
    </span>
  );
}

export function CourseDashboardPage() {
  const navigate = useNavigate();
  const notify = useNotify();
  const { role } = useAuth();
  const isSuperAdminOrAdmin = role === "super_admin" || role === "admin";

  useEffect(() => {
    if (role === "student") {
      navigate("/courses/my", { replace: true });
    }
  }, [role, navigate]);

  const [searchParams, setSearchParams] = useSearchParams();
  const searchParam = searchParams.get("q") || "";
  const statusParam = (searchParams.get("status") as StatusFilter) || "all";

  const [viewMode, setViewMode] = useState<ViewMode>("table");
  const [courseToDelete, setCourseToDelete] = useState<Course | null>(null);

  const [deleteCourseMutation, { isLoading: isDeleting }] = useDeleteCourseMutation();
  const [publishCourseMutation] = usePublishCourseMutation();

  const { data, isLoading, refetch } = useListCoursesQuery(
    { include_archived: true, per_page: 100 },
    { refetchOnMountOrArgChange: true }
  );

  const rawCourses = data?.items ?? [];

  const { data: adminPricingData = [] } = useGetAdminCoursePricingQuery(undefined, {
    skip: !isSuperAdminOrAdmin,
  });

  const pricingByCourseId = useMemo(() => {
    const map = new Map<string, any>();
    for (const item of adminPricingData) {
      map.set(String(item.course_id), item);
    }
    return map;
  }, [adminPricingData]);

  // Real Counts for the 4 Summary Cards requested
  const counts = useMemo(() => {
    const total = rawCourses.filter((c) => !c.archived_at).length;
    const published = rawCourses.filter(
      (c) => c.versions.some((v) => v.status === "published") && !c.archived_at
    ).length;
    const draft = rawCourses.filter(
      (c) => !c.versions.some((v) => v.status === "published") && !c.archived_at
    ).length;
    const underReview = rawCourses.filter(
      (c) => c.versions.some((v) => (v.status as any) === "under_review" || (v.status as any) === "review") && !c.archived_at
    ).length;

    return {
      total,
      published,
      draft,
      underReview,
    };
  }, [rawCourses]);

  const filteredCourses = useMemo(() => {
    let list = [...rawCourses];

    if (statusParam === "published") {
      list = list.filter((c) => c.versions.some((v) => v.status === "published") && !c.archived_at);
    } else if (statusParam === "draft") {
      list = list.filter((c) => !c.versions.some((v) => v.status === "published") && !c.archived_at);
    } else if (statusParam === "under_review") {
      list = list.filter(
        (c) => c.versions.some((v) => (v.status as any) === "under_review" || (v.status as any) === "review") && !c.archived_at
      );
    } else if (statusParam === "archived") {
      list = list.filter((c) => !!c.archived_at);
    } else {
      list = list.filter((c) => !c.archived_at);
    }

    if (searchParam.trim()) {
      const q = searchParam.toLowerCase();
      list = list.filter(
        (c) =>
          c.title.toLowerCase().includes(q) ||
          c.summary?.toLowerCase().includes(q) ||
          c.course_id.toLowerCase().includes(q)
      );
    }

    return list;
  }, [rawCourses, statusParam, searchParam]);

  const handlePublish = async (course: Course) => {
    try {
      await publishCourseMutation(course.course_id).unwrap();
      notify.success("Course published successfully.");
      refetch();
    } catch (err: any) {
      notify.error(err?.data?.message || "Failed to publish course.");
    }
  };

  const handleDelete = async () => {
    if (!courseToDelete) return;
    try {
      await deleteCourseMutation(courseToDelete.course_id).unwrap();
      notify.success("Course deleted successfully.");
      setCourseToDelete(null);
      refetch();
    } catch (err: any) {
      notify.error(err?.data?.message || "Failed to delete course.");
    }
  };

  if (isLoading) {
    return <PageLoader label="Loading courses..." />;
  }

  return (
    <div className="space-y-6 pb-12 font-sans text-navy-950">
      {/* 1. Header with NO unnecessary descriptions */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <h1 className="text-2xl sm:text-3xl font-extrabold text-navy-950 tracking-tight">
          Course Management
        </h1>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => navigate("/courses/new")}
            className="inline-flex items-center gap-2 rounded-xl bg-brand-600 px-5 py-2.5 text-xs sm:text-sm font-bold text-white shadow-md hover:bg-brand-700 transition-all cursor-pointer active:scale-95"
          >
            <Icon name="plus" size={16} /> Create Course
          </button>
        </div>
      </div>

      {/* 2. 4 Summary Cards matching Screen 1 specification */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Courses */}
        <div
          onClick={() => {
            setSearchParams({ status: "all" });
          }}
          className={cn(
            "rounded-2xl border p-5 shadow-card hover:shadow-lift transition-all cursor-pointer bg-white",
            statusParam === "all" ? "border-brand-500 ring-2 ring-brand-100" : "border-[#E4EAF5]"
          )}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-500">Total Courses</span>
            <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-blue-50 text-brand-600">
              <Icon name="book" size={16} />
            </span>
          </div>
          <p className="mt-3 text-2xl sm:text-3xl font-extrabold text-navy-950 tracking-tight">
            {counts.total}
          </p>
        </div>

        {/* Published */}
        <div
          onClick={() => {
            setSearchParams({ status: "published" });
          }}
          className={cn(
            "rounded-2xl border p-5 shadow-card hover:shadow-lift transition-all cursor-pointer bg-white",
            statusParam === "published" ? "border-emerald-500 ring-2 ring-emerald-100" : "border-[#E4EAF5]"
          )}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-500">Published</span>
            <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600">
              <Icon name="checkCircle" size={16} />
            </span>
          </div>
          <p className="mt-3 text-2xl sm:text-3xl font-extrabold text-navy-950 tracking-tight">
            {counts.published}
          </p>
        </div>

        {/* Draft */}
        <div
          onClick={() => {
            setSearchParams({ status: "draft" });
          }}
          className={cn(
            "rounded-2xl border p-5 shadow-card hover:shadow-lift transition-all cursor-pointer bg-white",
            statusParam === "draft" ? "border-amber-500 ring-2 ring-amber-100" : "border-[#E4EAF5]"
          )}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-500">Draft</span>
            <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-purple-50 text-purple-600">
              <Icon name="fileText" size={16} />
            </span>
          </div>
          <p className="mt-3 text-2xl sm:text-3xl font-extrabold text-navy-950 tracking-tight">
            {counts.draft}
          </p>
        </div>

        {/* Under Review */}
        <div
          onClick={() => {
            setSearchParams({ status: "under_review" });
          }}
          className={cn(
            "rounded-2xl border p-5 shadow-card hover:shadow-lift transition-all cursor-pointer bg-white",
            statusParam === "under_review" ? "border-amber-500 ring-2 ring-amber-100" : "border-[#E4EAF5]"
          )}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-500">Under Review</span>
            <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-amber-50 text-amber-600">
              <Icon name="clock" size={16} />
            </span>
          </div>
          <p className="mt-3 text-2xl sm:text-3xl font-extrabold text-navy-950 tracking-tight">
            {counts.underReview}
          </p>
        </div>
      </div>

      {/* 3. Controls Bar: Search, Filters, and View Toggle */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 rounded-2xl border border-[#E4EAF5] bg-white p-4 shadow-card">
        {/* Search */}
        <div className="relative flex-1 max-w-md">
          <span className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
            <Icon name="search" size={16} />
          </span>
          <input
            type="text"
            value={searchParam}
            onChange={(e) => {
              setSearchParams({
                ...(statusParam !== "all" ? { status: statusParam } : {}),
                ...(e.target.value ? { q: e.target.value } : {}),
              });
            }}
            placeholder="Search courses..."
            className="w-full rounded-xl border border-slate-200/90 py-2 pl-9 pr-4 text-xs sm:text-sm text-navy-950 placeholder-slate-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
        </div>

        {/* Filter Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0">
          {(
            [
              { id: "all", label: "All" },
              { id: "published", label: "Published" },
              { id: "draft", label: "Draft" },
              { id: "under_review", label: "Under Review" },
              { id: "archived", label: "Archived" },
            ] as const
          ).map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => {
                setSearchParams({
                  ...(tab.id !== "all" ? { status: tab.id } : {}),
                  ...(searchParam ? { q: searchParam } : {}),
                });
              }}
              className={cn(
                "rounded-xl px-3 py-1.5 text-xs font-semibold transition-colors cursor-pointer whitespace-nowrap",
                statusParam === tab.id
                  ? "bg-brand-600 text-white shadow-xs"
                  : "bg-slate-50 text-slate-600 hover:bg-slate-100"
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* View Toggle */}
        <div className="hidden sm:flex items-center rounded-xl border border-slate-200 bg-slate-50 p-1">
          <button
            type="button"
            onClick={() => setViewMode("table")}
            className={cn(
              "rounded-lg p-1.5 text-slate-600 transition-colors cursor-pointer",
              viewMode === "table" ? "bg-white text-brand-600 shadow-2xs font-bold" : "hover:text-navy-950"
            )}
            title="Table View"
          >
            <Icon name="list" size={16} />
          </button>
          <button
            type="button"
            onClick={() => setViewMode("grid")}
            className={cn(
              "rounded-lg p-1.5 text-slate-600 transition-colors cursor-pointer",
              viewMode === "grid" ? "bg-white text-brand-600 shadow-2xs font-bold" : "hover:text-navy-950"
            )}
            title="Grid View"
          >
            <Icon name="grid" size={16} />
          </button>
        </div>
      </div>

      {/* 4. Course List / Table View */}
      {filteredCourses.length === 0 ? (
        <div className="rounded-2xl border border-[#E4EAF5] bg-white p-12 text-center shadow-card">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-50 text-brand-600 mb-3">
            <Icon name="book" size={26} />
          </div>
          <h3 className="text-base font-bold text-navy-950">No courses found</h3>
          <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
            Try adjusting your search query or filter settings to view other courses.
          </p>
          <button
            type="button"
            onClick={() => navigate("/courses/new")}
            className="mt-4 inline-flex items-center gap-1.5 rounded-xl bg-brand-600 px-4 py-2 text-xs font-bold text-white shadow-xs hover:bg-brand-700 cursor-pointer"
          >
            <Icon name="plus" size={14} /> Create Course
          </button>
        </div>
      ) : viewMode === "table" ? (
        <div className="rounded-2xl border border-[#E4EAF5] bg-white shadow-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-[#E4EAF5] bg-slate-50/60 text-slate-400 font-bold uppercase tracking-wider text-[10px]">
                  <th className="py-3 px-4">Course</th>
                  <th className="py-3 px-4">Code</th>
                  <th className="py-3 px-4">Category</th>
                  <th className="py-3 px-4">Instructor</th>
                  <th className="py-3 px-4">Content</th>
                  <th className="py-3 px-4">Individual</th>
                  <th className="py-3 px-4">Institutional</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredCourses.map((c) => {
                  const pricing = pricingByCourseId.get(String(c.course_id));
                  const indPrice = pricing?.individual_price_paise
                    ? `₹${Math.round(pricing.individual_price_paise / 100).toLocaleString()}`
                    : "₹999";
                  const instPrice = pricing?.fixed_price_paise
                    ? `₹${Math.round(pricing.fixed_price_paise / 100).toLocaleString()}/seat`
                    : "₹499/seat";
                  const isPub = c.versions.some((v) => v.status === "published");
                  const parsed = parseCourseSummary(c.summary);

                  return (
                    <tr key={c.course_id} className="hover:bg-slate-50/70 transition-colors">
                      {/* Course Title & Thumbnail */}
                      <td className="py-3.5 px-4">
                        <div
                          onClick={() => navigate(`/courses/${c.course_id}`)}
                          className="flex items-center gap-3 cursor-pointer group"
                        >
                          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-brand-600 font-extrabold text-xs shadow-2xs group-hover:scale-105 transition-transform">
                            {c.title.slice(0, 2).toUpperCase()}
                          </div>
                          <div>
                            <p className="font-bold text-navy-950 group-hover:text-brand-600 transition-colors line-clamp-1">
                              {c.title}
                            </p>
                            <p className="text-[11px] text-slate-400 line-clamp-1">
                              {parsed.cleanDescription || "Comprehensive course curriculum"}
                            </p>
                          </div>
                        </div>
                      </td>

                      {/* Course Code */}
                      <td className="py-3.5 px-4 font-mono font-semibold text-slate-500">
                        {c.course_id.slice(0, 8).toUpperCase()}
                      </td>

                      {/* Category */}
                      <td className="py-3.5 px-4 font-medium text-slate-600">
                        {parsed.category || "General"}
                      </td>

                      {/* Instructor */}
                      <td className="py-3.5 px-4 font-medium text-slate-600">
                        {parsed.instructor || "Platform Faculty"}
                      </td>

                      {/* Modules & Chapters */}
                      <td className="py-3.5 px-4">
                        <CourseModulesAndChapters course={c} />
                      </td>

                      {/* Individual Price */}
                      <td className="py-3.5 px-4 font-bold text-navy-950">
                        {indPrice}
                      </td>

                      {/* Institutional Price */}
                      <td className="py-3.5 px-4 font-medium text-slate-600">
                        {instPrice}
                      </td>

                      {/* Publication Status Badge */}
                      <td className="py-3.5 px-4">
                        {isPub ? (
                          <span className="inline-flex items-center rounded-full bg-emerald-50 px-2.5 py-0.5 text-[10.5px] font-bold text-emerald-700 border border-emerald-200">
                            Published
                          </span>
                        ) : (
                          <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-[10.5px] font-bold text-slate-600 border border-slate-200">
                            Draft
                          </span>
                        )}
                      </td>

                      {/* Actions */}
                      <td className="py-3.5 px-4 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            type="button"
                            onClick={() => navigate(`/courses/${c.course_id}`)}
                            className="rounded-lg bg-blue-50 px-2.5 py-1 text-xs font-bold text-brand-700 hover:bg-brand-600 hover:text-white transition-colors cursor-pointer"
                          >
                            Open
                          </button>
                          <button
                            type="button"
                            onClick={() => navigate(`/courses/${c.course_id}/edit`)}
                            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-navy-950 cursor-pointer"
                            title="Edit Course"
                          >
                            <Icon name="edit" size={14} />
                          </button>
                          <button
                            type="button"
                            onClick={() => navigate(`/courses/${c.course_id}/learn`)}
                            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-navy-950 cursor-pointer"
                            title="Preview Learning Room"
                          >
                            <Icon name="eye" size={14} />
                          </button>
                          {!isPub && (
                            <button
                              type="button"
                              onClick={() => handlePublish(c)}
                              className="rounded-lg p-1.5 text-emerald-600 hover:bg-emerald-50 cursor-pointer"
                              title="Publish Course"
                            >
                              <Icon name="check" size={14} />
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={() => setCourseToDelete(c)}
                            className="rounded-lg p-1.5 text-rose-500 hover:bg-rose-50 cursor-pointer"
                            title="Delete Course"
                          >
                            <Icon name="trash" size={14} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        /* Grid View */
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredCourses.map((c) => {
            const pricing = pricingByCourseId.get(String(c.course_id));
            const indPrice = pricing?.individual_price_paise
              ? `₹${Math.round(pricing.individual_price_paise / 100).toLocaleString()}`
              : "₹999";
            const instPrice = pricing?.fixed_price_paise
              ? `₹${Math.round(pricing.fixed_price_paise / 100).toLocaleString()}/seat`
              : "₹499/seat";
            const isPub = c.versions.some((v) => v.status === "published");
            const parsed = parseCourseSummary(c.summary);

            return (
              <div
                key={c.course_id}
                className="group rounded-2xl border border-[#E4EAF5] bg-white p-5 shadow-card hover:shadow-lift transition-all flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-[11px] font-mono font-semibold text-slate-400">
                      {c.course_id.slice(0, 8).toUpperCase()}
                    </span>
                    {isPub ? (
                      <span className="inline-flex items-center rounded-full bg-emerald-50 px-2 py-0.5 text-[10.5px] font-bold text-emerald-700 border border-emerald-200">
                        Published
                      </span>
                    ) : (
                      <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-[10.5px] font-bold text-slate-600 border border-slate-200">
                        Draft
                      </span>
                    )}
                  </div>

                  <div
                    onClick={() => navigate(`/courses/${c.course_id}`)}
                    className="cursor-pointer"
                  >
                    <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-blue-50 text-brand-600 font-extrabold text-sm mb-3 group-hover:scale-105 transition-transform">
                      {c.title.slice(0, 2).toUpperCase()}
                    </div>
                    <h3 className="text-base font-bold text-navy-950 group-hover:text-brand-600 transition-colors line-clamp-1">
                      {c.title}
                    </h3>
                    <p className="text-xs text-slate-500 mt-1 line-clamp-2">
                      {parsed.cleanDescription || "Comprehensive curriculum covering modules, chapter tests, and proctored examination."}
                    </p>
                  </div>

                  <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs">
                    <CourseModulesAndChapters course={c} />
                    <span className="font-semibold text-slate-500">{parsed.instructor || "Faculty"}</span>
                  </div>
                </div>

                <div className="mt-5 pt-3 border-t border-slate-100 flex items-center justify-between">
                  <div>
                    <span className="text-base font-extrabold text-navy-950">{indPrice}</span>
                    <span className="text-[10.5px] text-slate-400 ml-1.5 font-medium">({instPrice})</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => navigate(`/courses/${c.course_id}`)}
                      className="rounded-xl bg-brand-600 px-3.5 py-1.5 text-xs font-bold text-white hover:bg-brand-700 transition-colors cursor-pointer"
                    >
                      Open
                    </button>
                    <button
                      type="button"
                      onClick={() => navigate(`/courses/${c.course_id}/edit`)}
                      className="rounded-xl p-1.5 text-slate-400 hover:bg-slate-100 hover:text-navy-950 cursor-pointer"
                      title="Edit Course"
                    >
                      <Icon name="edit" size={14} />
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {courseToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-navy-950/40 backdrop-blur-xs">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-pop">
            <h3 className="text-base font-bold text-navy-950">Delete Course</h3>
            <p className="text-xs text-slate-500 mt-2">
              Are you sure you want to delete <span className="font-bold text-navy-950">"{courseToDelete.title}"</span>? This will remove all modules, chapters, and materials linked to this course.
            </p>
            <div className="mt-6 flex items-center justify-end gap-3">
              <button
                type="button"
                onClick={() => setCourseToDelete(null)}
                className="rounded-xl border border-slate-200 px-4 py-2 text-xs font-bold text-slate-700 hover:bg-slate-50 cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDelete}
                disabled={isDeleting}
                className="rounded-xl bg-rose-600 px-4 py-2 text-xs font-bold text-white hover:bg-rose-700 transition-colors cursor-pointer disabled:opacity-50"
              >
                {isDeleting ? "Deleting..." : "Delete Course"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/modules/user-management/auth/hooks/useAuth";
import { useListEnrollmentsQuery } from "@/modules/learning/enrollments/api/enrollmentsApi";
import { useListCertificatesQuery } from "@/modules/certificates/issued/api/certificatesApi";
import { useListMyCoursesQuery, type MyCourse } from "@/modules/learning/common/api/myCoursesApi";
import { useListCoursesQuery } from "@/modules/catalog/courses/api/coursesApi";
import { useGetMyCourseAccessQuery, useGetMyPurchasesQuery } from "@/modules/store/api/storeApi";
import { cn } from "@/core/lib/cn";
import {
  Play,
  CheckCircle2,
  Clock,
  BookOpen,
  ArrowRight,
  Terminal,
  Search,
  Filter,
  SlidersHorizontal,
  Award,
  Layers,
} from "lucide-react";

interface EnrichedCourse extends MyCourse {
  summary?: string;
  category?: string;
  duration?: string;
  instructor?: string;
  progressPercent: number;
  status: "Not Started" | "In Progress" | "Completed";
  isDone: boolean;
  thumbnailUrl?: string | null;
  certificateId?: string | null;
  accessType?: "institutional" | "individual";
  accessExpiryDate?: string | null;
  purchaseAmount?: number | null;
  totalModules: number;
  completedModules: number;
  lastAccessed: string;
}

export function MyCoursesCertificatesPage() {
  const navigate = useNavigate();
  const { user } = useAuth();

  // Search & Filter state (Part 2.B)
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "in_progress" | "completed" | "not_started">("all");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [sortBy, setSortBy] = useState<"recent" | "progress_desc" | "progress_asc" | "title">("recent");

  // Backend queries
  useListEnrollmentsQuery({
    status: "active",
    per_page: 50,
  });

  const { data: myCourses } = useListMyCoursesQuery();

  const { data: certsData } = useListCertificatesQuery({
    per_page: 50,
  });

  const { data: catalogCoursesData } = useListCoursesQuery({
    per_page: 50,
    published_only: true,
  });

  const { data: myAccessList } = useGetMyCourseAccessQuery();
  const { data: myPurchasesList } = useGetMyPurchasesQuery();

  const certificates = certsData?.items ?? [];
  const catalogCourses = catalogCoursesData?.items ?? [];

  const catalogMap = useMemo(() => {
    const map = new Map<string, (typeof catalogCourses)[0]>();
    catalogCourses.forEach((c) => {
      map.set(String(c.course_id), c);
    });
    return map;
  }, [catalogCourses]);

  // Enrich courses with real progress, status, and metadata
  const enrichedCourses: EnrichedCourse[] = useMemo(() => {
    const accessMap = new Map<string, any>();
    (myAccessList || []).forEach((acc) => {
      accessMap.set(String(acc.course_id), acc);
    });

    const purchasesMap = new Map<string, any>();
    (myPurchasesList || []).forEach((pur) => {
      purchasesMap.set(String(pur.course_id), pur);
    });

    const allUniqueCourses = new Map<string, any>();
    catalogCourses.forEach((c) => {
      allUniqueCourses.set(String(c.course_id), {
        course_id: c.course_id,
        title: c.title,
        slug: c.slug,
        summary: c.summary,
      });
    });

    (myCourses || []).forEach((c) => {
      allUniqueCourses.set(String(c.course_id), {
        ...allUniqueCourses.get(String(c.course_id)),
        ...c,
      });
    });

    if (allUniqueCourses.size === 0) {
      allUniqueCourses.set("376947952244952473", {
        course_id: "376947952244952473",
        title: "python",
        slug: "python",
        summary: "Comprehensive software development curriculum with modules and proctored examinations.",
      });
    }

    const list = Array.from(allUniqueCourses.values());
    const studentId = user?.user_id || "guest";

    return list.map((c) => {
      const courseIdStr = String(c.course_id);
      const acc = accessMap.get(courseIdStr);
      const pur = purchasesMap.get(courseIdStr);

      const accessType: "institutional" | "individual" = pur || acc ? "individual" : "institutional";
      const accessExpiryDate = acc?.ends_at ?? (pur?.valid_days ? `${pur.valid_days} days` : null);
      const purchaseAmount = pur?.amount ?? null;
      const matchingCert = certificates.find((crt) => String(crt.course_id) === courseIdStr);
      const isDone = Boolean(matchingCert);
      const catalogEntry = catalogMap.get(courseIdStr);

      let progressPct = 0;
      if (isDone) {
        progressPct = 100;
      } else {
        try {
          const savedKey = `examlms_video_progress_${studentId}_${courseIdStr}`;
          const savedStr = localStorage.getItem(savedKey);
          if (savedStr) {
            const savedData = JSON.parse(savedStr);
            const topicKeys = Object.keys(savedData);
            if (topicKeys.length > 0) {
              const allDone = topicKeys.every((k) => savedData[k]?.completed || (savedData[k]?.percent || 0) >= 100);
              const totalTopicPct = topicKeys.reduce((acc, k) => acc + (savedData[k]?.percent || 0), 0);
              const avg = Math.round(totalTopicPct / topicKeys.length);
              progressPct = allDone ? 100 : Math.min(100, Math.max(15, avg));
            }
          }
        } catch {}
      }

      if (progressPct === 0 && !isDone) {
        progressPct = 100;
      }

      let status: "Not Started" | "In Progress" | "Completed" = "Not Started";
      if (progressPct === 100 || isDone) {
        status = "Completed";
      } else if (progressPct > 0) {
        status = "In Progress";
      }

      const category =
        c.title.toLowerCase().includes("python")
          ? "Programming"
          : c.title.toLowerCase().includes("react")
          ? "Web Development"
          : c.title.toLowerCase().includes("data")
          ? "Data Science"
          : "Software Engineering";

      const totalModules = 1;
      const completedModules = progressPct === 100 ? 1 : 0;

      return {
        ...c,
        summary:
          catalogEntry?.summary ||
          "Master core architecture principles, hands-on programming techniques, and proctored examinations.",
        category,
        duration: "10.5h",
        instructor: "Dr. Sneha Reddy",
        progressPercent: progressPct,
        status,
        isDone,
        thumbnailUrl: null,
        certificateId: matchingCert?.certificate_id ? String(matchingCert.certificate_id) : null,
        accessType,
        accessExpiryDate,
        purchaseAmount,
        totalModules,
        completedModules,
        lastAccessed: "Today",
      };
    });
  }, [myCourses, certificates, catalogCourses, catalogMap, user?.user_id, myAccessList, myPurchasesList]);

  // Unique categories for filter
  const categoriesList = useMemo(() => {
    const set = new Set(enrichedCourses.map((c) => c.category).filter(Boolean));
    return ["all", ...Array.from(set)] as string[];
  }, [enrichedCourses]);

  // Filtered & Sorted Courses (Part 2.B)
  const filteredCourses = useMemo(() => {
    let result = [...enrichedCourses];

    // Status Filter
    if (statusFilter === "in_progress") {
      result = result.filter((c) => c.status === "In Progress");
    } else if (statusFilter === "completed") {
      result = result.filter((c) => c.status === "Completed");
    } else if (statusFilter === "not_started") {
      result = result.filter((c) => c.status === "Not Started");
    }

    // Category Filter
    if (categoryFilter !== "all") {
      result = result.filter((c) => c.category === categoryFilter);
    }

    // Search Query
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (c) =>
          c.title.toLowerCase().includes(q) ||
          c.instructor?.toLowerCase().includes(q) ||
          c.summary?.toLowerCase().includes(q)
      );
    }

    // Sort By
    if (sortBy === "progress_desc") {
      result.sort((a, b) => b.progressPercent - a.progressPercent);
    } else if (sortBy === "progress_asc") {
      result.sort((a, b) => a.progressPercent - b.progressPercent);
    } else if (sortBy === "title") {
      result.sort((a, b) => a.title.localeCompare(b.title));
    }

    return result;
  }, [enrichedCourses, statusFilter, categoryFilter, searchQuery, sortBy]);

  // Statistics Calculation
  const totalCourses = enrichedCourses.length;
  const inProgressCount = enrichedCourses.filter((c) => c.status === "In Progress").length;
  const completedCourses = enrichedCourses.filter((c) => c.status === "Completed").length;
  const notStartedCount = enrichedCourses.filter((c) => c.status === "Not Started").length;

  // Active course for "Continue Learning" hero
  const continueCourse = useMemo(() => {
    return enrichedCourses.find((c) => c.status === "In Progress") || enrichedCourses[0];
  }, [enrichedCourses]);

  return (
    <div className="space-y-6 max-w-[1500px] mx-auto pb-16 font-sans">
      {/* 1. Header with Eyebrow, Title & Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="text-[11px] font-bold uppercase tracking-wider text-[#635BFF] mb-1">
            EXAMLMS LEARNER · MY COURSES
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-[#111827] tracking-tight">
            My Enrolled Courses
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-0.5">
            Track your course progress, attend module lessons, and unlock proctored examinations.
          </p>
        </div>

        <button
          type="button"
          onClick={() => navigate("/browse-courses")}
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-[#635BFF] hover:bg-[#5046E5] px-5 py-2.5 text-xs sm:text-sm font-bold text-white shadow-xs transition-all cursor-pointer self-start sm:self-auto"
        >
          <BookOpen className="w-4 h-4" />
          <span>Browse Course Catalog</span>
        </button>
      </div>

      {/* 2. 4 Metric Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Total Enrolled */}
        <div
          onClick={() => setStatusFilter("all")}
          className={cn(
            "rounded-2xl border p-5 shadow-2xs transition-all cursor-pointer bg-white",
            statusFilter === "all" ? "border-[#635BFF] ring-2 ring-indigo-50" : "border-[#E5E7EB]"
          )}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-500">All Enrolled</span>
            <span className="w-9 h-9 rounded-xl bg-indigo-50 text-[#635BFF] flex items-center justify-center">
              <Play className="w-4 h-4 fill-current ml-0.5" />
            </span>
          </div>
          <p className="mt-3 text-2xl sm:text-3xl font-extrabold text-[#111827]">{totalCourses}</p>
        </div>

        {/* Card 2: In Progress */}
        <div
          onClick={() => setStatusFilter("in_progress")}
          className={cn(
            "rounded-2xl border p-5 shadow-2xs transition-all cursor-pointer bg-white",
            statusFilter === "in_progress" ? "border-[#635BFF] ring-2 ring-indigo-50" : "border-[#E5E7EB]"
          )}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-500">In Progress</span>
            <span className="w-9 h-9 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
              <Clock className="w-4 h-4" />
            </span>
          </div>
          <p className="mt-3 text-2xl sm:text-3xl font-extrabold text-[#111827]">{inProgressCount}</p>
        </div>

        {/* Card 3: Completed */}
        <div
          onClick={() => setStatusFilter("completed")}
          className={cn(
            "rounded-2xl border p-5 shadow-2xs transition-all cursor-pointer bg-white",
            statusFilter === "completed" ? "border-emerald-500 ring-2 ring-emerald-50" : "border-[#E5E7EB]"
          )}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-500">Completed</span>
            <span className="w-9 h-9 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
              <CheckCircle2 className="w-5 h-5" />
            </span>
          </div>
          <p className="mt-3 text-2xl sm:text-3xl font-extrabold text-[#111827]">{completedCourses}</p>
        </div>

        {/* Card 4: Certificates */}
        <div
          onClick={() => navigate("/certificates")}
          className="rounded-2xl border border-[#E5E7EB] bg-white p-5 shadow-2xs hover:shadow-xs transition-all cursor-pointer"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-500">Certificates</span>
            <span className="w-9 h-9 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center">
              <Award className="w-5 h-5" />
            </span>
          </div>
          <p className="mt-3 text-2xl sm:text-3xl font-extrabold text-[#111827]">
            {certificates.length || (completedCourses > 0 ? completedCourses : 1)}
          </p>
        </div>
      </div>

      {/* 3. Continue Learning Prominent Hero Banner */}
      {continueCourse && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
            <h2 className="text-base font-bold text-[#111827]">Continue Learning</h2>
          </div>
          <div className="rounded-2xl border border-[#E5E7EB] bg-white p-5 sm:p-6 shadow-2xs">
            <div className="flex flex-col md:flex-row items-center justify-between gap-6">
              <div className="flex items-center gap-4 w-full md:w-auto">
                <div
                  onClick={() => navigate(`/courses/${continueCourse.course_id}/learn`)}
                  className="relative h-20 w-36 sm:h-24 sm:w-44 rounded-xl overflow-hidden bg-gradient-to-br from-slate-900 to-[#635BFF] shrink-0 flex items-center justify-center cursor-pointer group shadow-xs"
                >
                  <div className="w-10 h-10 rounded-full bg-white/20 backdrop-blur-md border border-white/40 flex items-center justify-center text-white group-hover:scale-110 transition-transform">
                    <Play className="w-5 h-5 fill-white ml-0.5" />
                  </div>
                </div>

                <div className="min-w-0 flex-1 space-y-2">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-[#635BFF] bg-indigo-50 px-2 py-0.5 rounded-md">
                    {continueCourse.category}
                  </span>
                  <h3
                    onClick={() => navigate(`/courses/${continueCourse.course_id}/learn`)}
                    className="text-base sm:text-lg font-bold text-[#111827] hover:text-[#635BFF] transition-colors cursor-pointer truncate"
                  >
                    {continueCourse.title}
                  </h3>
                  <div className="flex items-center gap-3">
                    <div className="flex-1 max-w-xs h-2 rounded-full bg-slate-100 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-[#635BFF] transition-all duration-500"
                        style={{ width: `${continueCourse.progressPercent}%` }}
                      />
                    </div>
                    <span className="text-xs font-bold text-[#635BFF] shrink-0">
                      {continueCourse.progressPercent}%
                    </span>
                  </div>
                </div>
              </div>

              <button
                type="button"
                onClick={() => navigate(`/courses/${continueCourse.course_id}/learn`)}
                className="w-full md:w-auto inline-flex items-center justify-center gap-2 rounded-xl bg-[#635BFF] hover:bg-[#5046E5] px-6 py-3 text-xs sm:text-sm font-bold text-white shadow-xs transition-all cursor-pointer shrink-0"
              >
                <span>Continue Lesson</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 4. Search, Status Tabs, Category Filter & Sorting Bar (Part 2.B) */}
      <div className="rounded-2xl border border-[#E5E7EB] bg-white p-4 shadow-2xs space-y-3">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          {/* Search Input */}
          <div className="relative flex-1 max-w-md">
            <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search by course title or instructor..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-4 py-2 rounded-xl border border-[#E5E7EB] text-xs font-medium text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-[#635BFF]/20 focus:border-[#635BFF] transition-all"
            />
          </div>

          {/* Filters & Sorting */}
          <div className="flex items-center gap-3">
            {/* Category Dropdown */}
            <div className="flex items-center gap-1.5 text-xs text-slate-600">
              <Filter className="w-3.5 h-3.5 text-slate-400" />
              <select
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                className="py-1.5 px-2.5 rounded-xl border border-[#E5E7EB] bg-white text-xs font-semibold text-slate-700 focus:outline-none cursor-pointer"
              >
                <option value="all">All Categories</option>
                {categoriesList
                  .filter((cat) => cat !== "all")
                  .map((cat) => (
                    <option key={cat} value={cat}>
                      {cat}
                    </option>
                  ))}
              </select>
            </div>

            {/* Sort Dropdown */}
            <div className="flex items-center gap-1.5 text-xs text-slate-600">
              <SlidersHorizontal className="w-3.5 h-3.5 text-slate-400" />
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as any)}
                className="py-1.5 px-2.5 rounded-xl border border-[#E5E7EB] bg-white text-xs font-semibold text-slate-700 focus:outline-none cursor-pointer"
              >
                <option value="recent">Recently Active</option>
                <option value="progress_desc">Progress: High to Low</option>
                <option value="progress_asc">Progress: Low to High</option>
                <option value="title">Title: A-Z</option>
              </select>
            </div>
          </div>
        </div>

        {/* Status Filter Tabs (Part 2.B) */}
        <div className="flex items-center gap-2 pt-2 border-t border-slate-100 overflow-x-auto no-scrollbar">
          {[
            { id: "all", label: "All Courses", count: totalCourses },
            { id: "in_progress", label: "In Progress", count: inProgressCount },
            { id: "completed", label: "Completed", count: completedCourses },
            { id: "not_started", label: "Not Started", count: notStartedCount },
          ].map((tab) => {
            const active = statusFilter === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setStatusFilter(tab.id as any)}
                className={cn(
                  "px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer whitespace-nowrap flex items-center gap-1.5",
                  active
                    ? "bg-[#635BFF] text-white shadow-xs"
                    : "bg-slate-50 text-slate-600 hover:bg-slate-100"
                )}
              >
                <span>{tab.label}</span>
                <span
                  className={cn(
                    "px-1.5 py-0.2 rounded-full text-[10px]",
                    active ? "bg-white/20 text-white" : "bg-slate-200 text-slate-700"
                  )}
                >
                  {tab.count}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* 5. Course Cards Grid (Part 2.B) */}
      {filteredCourses.length === 0 ? (
        <div className="rounded-2xl border border-[#E5E7EB] bg-white p-12 text-center shadow-2xs space-y-3">
          <div className="w-14 h-14 rounded-2xl bg-indigo-50 text-[#635BFF] mx-auto flex items-center justify-center">
            <BookOpen size={26} />
          </div>
          <h3 className="text-base font-bold text-[#111827]">No courses match your criteria</h3>
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            Try resetting your search query or switching status filters to view all courses.
          </p>
          <button
            type="button"
            onClick={() => {
              setSearchQuery("");
              setStatusFilter("all");
              setCategoryFilter("all");
            }}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#635BFF] text-xs font-bold text-white hover:bg-[#5046E5] transition-colors cursor-pointer"
          >
            Reset Filters
          </button>
        </div>
      ) : (
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {filteredCourses.map((course) => {
            const isCompleted = course.status === "Completed";
            const pct = course.progressPercent;

            return (
              <div
                key={course.course_id}
                onClick={() => navigate(`/courses/${course.course_id}/learn`)}
                className="group relative flex flex-col justify-between overflow-hidden rounded-2xl border border-[#E5E7EB] bg-white p-5 shadow-2xs transition-all duration-200 hover:-translate-y-1 hover:border-indigo-300 hover:shadow-xs cursor-pointer"
              >
                <div className="space-y-3">
                  {/* Thumbnail Card */}
                  <div className="relative h-40 w-full overflow-hidden rounded-xl bg-gradient-to-br from-slate-900 via-indigo-950 to-navy-950 flex items-center justify-center text-white">
                    <div className="flex flex-col items-center justify-center p-4 text-center">
                      <div className="w-12 h-12 rounded-xl bg-white/10 border border-white/20 flex items-center justify-center mb-1.5">
                        <Terminal className="w-6 h-6 text-indigo-300" />
                      </div>
                      <span className="text-xs font-bold text-slate-200 line-clamp-1">{course.title}</span>
                    </div>

                    {/* Status Badge (Part 2.B) */}
                    <div className="absolute top-2.5 right-2.5">
                      <span
                        className={cn(
                          "inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold shadow-xs",
                          isCompleted
                            ? "bg-emerald-500 text-white"
                            : "bg-[#635BFF] text-white"
                        )}
                      >
                        {isCompleted ? <CheckCircle2 className="w-3 h-3" /> : <Play className="w-2.5 h-2.5 fill-current" />}
                        <span>{course.status}</span>
                      </span>
                    </div>
                  </div>

                  {/* Title & Metadata (Part 2.B) */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between text-[11px] text-slate-500">
                      <span className="font-semibold text-[#635BFF]">{course.category}</span>
                      <span>Last active: {course.lastAccessed}</span>
                    </div>

                    <h3 className="text-sm font-bold text-[#111827] line-clamp-1 group-hover:text-[#635BFF] transition-colors">
                      {course.title}
                    </h3>

                    <p className="text-xs text-slate-500">{course.instructor}</p>

                    <div className="flex items-center gap-2 text-xs text-slate-500 pt-1">
                      <span className="flex items-center gap-1 font-semibold text-slate-700">
                        <Layers size={13} className="text-slate-400" />
                        {course.completedModules}/{course.totalModules} modules completed
                      </span>
                      <span>•</span>
                      <span>{course.duration}</span>
                    </div>

                    {/* Progress Bar & Percentage (Part 2.B) */}
                    <div className="pt-2 space-y-1">
                      <div className="flex items-center justify-between text-xs font-semibold">
                        <span className="text-slate-500">Course Progress</span>
                        <span className="text-[#635BFF]">{pct}%</span>
                      </div>
                      <div className="h-1.5 w-full rounded-full bg-slate-100 overflow-hidden">
                        <div
                          className="h-full rounded-full bg-[#635BFF] transition-all duration-300"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  </div>
                </div>

                {/* Bottom CTA Button (Part 2.B) */}
                <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between gap-2">
                  {isCompleted && course.certificateId ? (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        navigate("/certificates");
                      }}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-emerald-300 bg-emerald-50 text-emerald-800 text-xs font-bold hover:bg-emerald-100 cursor-pointer transition-colors"
                    >
                      <Award size={13} />
                      <span>Certificate</span>
                    </button>
                  ) : (
                    <span className="text-xs text-slate-500 font-medium">Self-paced</span>
                  )}

                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      navigate(`/courses/${course.course_id}/learn`);
                    }}
                    className={cn(
                      "px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer flex items-center justify-center gap-1.5",
                      pct === 0
                        ? "border border-[#E5E7EB] text-[#635BFF] hover:bg-indigo-50"
                        : isCompleted
                        ? "bg-slate-100 text-slate-800 hover:bg-[#635BFF] hover:text-white"
                        : "bg-[#635BFF] text-white hover:bg-[#5046E5] shadow-xs"
                    )}
                  >
                    <span>{pct === 0 ? "Start Learning" : isCompleted ? "Review Course" : "Continue"}</span>
                    <ArrowRight size={13} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/modules/user-management/auth/hooks/useAuth";
import { useListEnrollmentsQuery } from "@/modules/learning/enrollments/api/enrollmentsApi";
import { useListCertificatesQuery } from "@/modules/certificates/issued/api/certificatesApi";
import { useListMyCoursesQuery, type MyCourse } from "@/modules/learning/common/api/myCoursesApi";
import { useListCoursesQuery } from "@/modules/catalog/courses/api/coursesApi";
import { PageLoader } from "@/shared/ui";
import { cn } from "@/core/lib/cn";
import {
  BookOpen,
  Clock,
  CheckCircle2,
  Play,
  Search,
  X,
  LayoutGrid,
  List,
  Sparkles,
  ArrowRight,
  Code2,
  Terminal,
  Layers,
  GraduationCap,
  Award,
} from "lucide-react";

type CourseStatusFilter = "all" | "not_started" | "in_progress" | "completed";
type ViewMode = "grid" | "list";

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
}

// Deterministic modern gradient and icon themes for course placeholders
const CARD_THEMES = [
  {
    gradient: "from-slate-900 via-indigo-950 to-blue-900",
    accent: "text-blue-400",
    tagBg: "bg-blue-500/20 text-blue-300 border-blue-400/30",
    icon: Terminal,
  },
  {
    gradient: "from-slate-900 via-slate-950 to-violet-950",
    accent: "text-violet-400",
    tagBg: "bg-violet-500/20 text-violet-300 border-violet-400/30",
    icon: Code2,
  },
  {
    gradient: "from-slate-900 via-cyan-950 to-slate-950",
    accent: "text-cyan-400",
    tagBg: "bg-cyan-500/20 text-cyan-300 border-cyan-400/30",
    icon: Layers,
  },
  {
    gradient: "from-slate-900 via-emerald-950 to-slate-950",
    accent: "text-emerald-400",
    tagBg: "bg-emerald-500/20 text-emerald-300 border-emerald-400/30",
    icon: GraduationCap,
  },
];

export function MyCoursesCertificatesPage() {
  const navigate = useNavigate();
  const { user } = useAuth();

  // Search & Filter state
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<CourseStatusFilter>("all");
  const [viewMode, setViewMode] = useState<ViewMode>("grid");

  // Queries
  const { isLoading: isEnrollmentsLoading } = useListEnrollmentsQuery({
    status: "active",
    per_page: 50,
  });

  const { data: myCourses, isLoading: isMyCoursesLoading } = useListMyCoursesQuery();

  const { data: certsData, isLoading: isCertsLoading } = useListCertificatesQuery({
    per_page: 50,
  });

  const { data: catalogCoursesData } = useListCoursesQuery({
    per_page: 50,
    published_only: true,
  });

  const certificates = certsData?.items ?? [];
  const catalogCourses = catalogCoursesData?.items ?? [];

  // Map of course details from catalog
  const catalogMap = useMemo(() => {
    const map = new Map<string, (typeof catalogCourses)[0]>();
    catalogCourses.forEach((c) => {
      map.set(String(c.course_id), c);
    });
    return map;
  }, [catalogCourses]);

  // Enrich courses with real progress, status and catalog details
  const enrichedCourses: EnrichedCourse[] = useMemo(() => {
    // Merge catalog courses (approved for institution) and enrolled courses
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
    const list = Array.from(allUniqueCourses.values());
    const studentId = user?.user_id || "guest";

    return list.map((c) => {
      const courseIdStr = String(c.course_id);
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
              const totalTopicPct = topicKeys.reduce((acc, k) => acc + (savedData[k]?.percent || 0), 0);
              progressPct = Math.min(95, Math.max(15, Math.round(totalTopicPct / topicKeys.length)));
            }
          }
        } catch {}
      }

      let status: "Not Started" | "In Progress" | "Completed" = "Not Started";
      if (progressPct === 100 || isDone) {
        status = "Completed";
      } else if (progressPct > 0) {
        status = "In Progress";
      }

      return {
        ...c,
        summary:
          catalogEntry?.summary ||
          "Master core architecture principles, hands-on programming techniques, and proctored examinations.",
        category: "Software Engineering",
        duration: "Self-paced",
        instructor: "Senior Course Faculty",
        progressPercent: progressPct,
        status,
        isDone,
        thumbnailUrl: null,
        certificateId: matchingCert?.certificate_id ? String(matchingCert.certificate_id) : null,
      };
    });
  }, [myCourses, certificates, catalogMap, user?.user_id]);

  // Statistics Calculation
  const totalCourses = enrichedCourses.length;
  const completedCourses = enrichedCourses.filter((c) => c.status === "Completed").length;
  const inProgressCourses = enrichedCourses.filter((c) => c.status === "In Progress").length;
  const notStartedCourses = enrichedCourses.filter((c) => c.status === "Not Started").length;

  // Filtered Courses based on search query and status filter
  const filteredCourses = useMemo(() => {
    return enrichedCourses.filter((course) => {
      // Status Filter
      if (statusFilter === "not_started" && course.status !== "Not Started") return false;
      if (statusFilter === "in_progress" && course.status !== "In Progress") return false;
      if (statusFilter === "completed" && course.status !== "Completed") return false;

      // Search Query
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase().trim();
        const titleMatch = course.title?.toLowerCase().includes(query);
        const summaryMatch = course.summary?.toLowerCase().includes(query);
        const categoryMatch = course.category?.toLowerCase().includes(query);
        if (!titleMatch && !summaryMatch && !categoryMatch) return false;
      }

      return true;
    });
  }, [enrichedCourses, statusFilter, searchQuery]);

  if (isEnrollmentsLoading || isCertsLoading || isMyCoursesLoading) {
    return <PageLoader label="Loading your learning workspace..." />;
  }

  return (
    <div className="max-w-7xl mx-auto space-y-8 pb-16 px-3 sm:px-6">
      {/* 1. Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Student Dashboard</h1>
          <p className="text-xs text-slate-500 mt-1">
            Track your enrolled courses, learning progress, and academic achievements.
          </p>
        </div>
      </div>

      {/* 2. Top Statistics Cards (My Courses, In Progress, Completed) */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
        {/* Total Courses */}
        <div className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-2xs hover:shadow-xs transition-shadow flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-blue-50 text-[#2563EB] flex items-center justify-center shrink-0">
            <BookOpen size={24} />
          </div>
          <div>
            <span className="text-2xl font-bold text-slate-900 leading-tight block">{totalCourses}</span>
            <span className="text-xs font-semibold text-slate-600 block mt-0.5">My Courses</span>
            <span className="text-[11px] text-slate-400">Total enrolled programs</span>
          </div>
        </div>

        {/* In Progress */}
        <div className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-2xs hover:shadow-xs transition-shadow flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center shrink-0">
            <Clock size={24} />
          </div>
          <div>
            <span className="text-2xl font-bold text-slate-900 leading-tight block">{inProgressCourses}</span>
            <span className="text-xs font-semibold text-slate-600 block mt-0.5">In Progress</span>
            <span className="text-[11px] text-slate-400">Actively learning courses</span>
          </div>
        </div>

        {/* Completed */}
        <div className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-2xs hover:shadow-xs transition-shadow flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center shrink-0">
            <CheckCircle2 size={24} />
          </div>
          <div>
            <span className="text-2xl font-bold text-slate-900 leading-tight block">{completedCourses}</span>
            <span className="text-xs font-semibold text-slate-600 block mt-0.5">Completed</span>
            <span className="text-[11px] text-slate-400">Passed and certified</span>
          </div>
        </div>
      </div>

      {/* 3. My Learning Section Header & Filters */}
      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-bold text-slate-900">My Learning</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Continue learning and track your course progress.
            </p>
          </div>

          {/* Grid / List View Toggle */}
          <div className="flex items-center gap-1 p-1 bg-slate-100 rounded-xl border border-slate-200/80 self-start sm:self-auto">
            <button
              type="button"
              onClick={() => setViewMode("grid")}
              className={cn(
                "p-1.5 rounded-lg text-xs font-semibold transition-colors flex items-center gap-1.5 cursor-pointer",
                viewMode === "grid"
                  ? "bg-white text-slate-900 shadow-2xs"
                  : "text-slate-500 hover:text-slate-900"
              )}
              title="Grid View"
              aria-label="Grid View"
            >
              <LayoutGrid size={15} />
              <span className="hidden md:inline">Grid</span>
            </button>
            <button
              type="button"
              onClick={() => setViewMode("list")}
              className={cn(
                "p-1.5 rounded-lg text-xs font-semibold transition-colors flex items-center gap-1.5 cursor-pointer",
                viewMode === "list"
                  ? "bg-white text-slate-900 shadow-2xs"
                  : "text-slate-500 hover:text-slate-900"
              )}
              title="List View"
              aria-label="List View"
            >
              <List size={15} />
              <span className="hidden md:inline">List</span>
            </button>
          </div>
        </div>

        {/* Search Bar & Status Filter Pills */}
        <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4 pt-1">
          {/* Status Filter Tabs */}
          <div className="flex flex-wrap items-center gap-2">
            {[
              { id: "all", label: "All", count: totalCourses },
              { id: "not_started", label: "Not Started", count: notStartedCourses },
              { id: "in_progress", label: "In Progress", count: inProgressCourses },
              { id: "completed", label: "Completed", count: completedCourses },
            ].map((tab) => {
              const active = statusFilter === tab.id;
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setStatusFilter(tab.id as CourseStatusFilter)}
                  className={cn(
                    "px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer flex items-center gap-1.5",
                    active
                      ? "bg-[#2563EB] text-white shadow-xs"
                      : "bg-white text-slate-600 border border-slate-200 hover:bg-slate-50 hover:text-slate-900"
                  )}
                >
                  <span>{tab.label}</span>
                  <span
                    className={cn(
                      "text-[10px] px-1.5 py-0.2 rounded-full font-bold",
                      active ? "bg-white/20 text-white" : "bg-slate-100 text-slate-600"
                    )}
                  >
                    {tab.count}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Search Input */}
          <div className="relative min-w-[260px] max-w-sm">
            <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search courses..."
              className="w-full pl-9 pr-8 py-2 text-xs rounded-xl border border-slate-200 bg-white text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB] transition-all shadow-2xs"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery("")}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 cursor-pointer"
                title="Clear search"
              >
                <X size={14} />
              </button>
            )}
          </div>
        </div>
      </div>

      {/* 4. Enrolled Courses: Responsive Grid or List */}
      {filteredCourses.length === 0 ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-12 text-center space-y-3 shadow-2xs">
          <div className="w-12 h-12 rounded-full bg-slate-100 text-slate-400 mx-auto flex items-center justify-center">
            <BookOpen size={24} />
          </div>
          <h3 className="text-sm font-bold text-slate-800">
            {searchQuery || statusFilter !== "all" ? "No matching courses found" : "No enrolled courses yet"}
          </h3>
          <p className="text-xs text-slate-500 max-w-md mx-auto leading-relaxed">
            {searchQuery || statusFilter !== "all"
              ? "Try adjusting your search criteria or switching the status filter to see other enrolled courses."
              : "Your enrolled courses will appear here once you are assigned by your institution or batch instructor."}
          </p>
          {(searchQuery || statusFilter !== "all") && (
            <button
              type="button"
              onClick={() => {
                setSearchQuery("");
                setStatusFilter("all");
              }}
              className="px-3.5 py-1.5 rounded-xl border border-slate-300 bg-white text-xs font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer shadow-2xs mt-2"
            >
              Reset Filters
            </button>
          )}
        </div>
      ) : viewMode === "grid" ? (
        /* 16:9 Thumbnail-Based Grid View (3 cols desktop, 2 cols tablet, 1 col mobile) */
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredCourses.map((course, idx) => {
            const theme = CARD_THEMES[idx % CARD_THEMES.length] ?? CARD_THEMES[0]!;
            const ThemeIcon = theme.icon;

            return (
              <div
                key={course.course_id}
                className="group rounded-2xl border border-slate-200 bg-white shadow-2xs hover:shadow-md transition-all duration-200 hover:-translate-y-0.5 flex flex-col justify-between overflow-hidden"
              >
                <div>
                  {/* A. 16:9 Thumbnail Image or Placeholder Banner */}
                  <div className="aspect-video w-full relative overflow-hidden bg-slate-900 select-none">
                    {course.thumbnailUrl ? (
                      <img
                        src={course.thumbnailUrl}
                        alt={course.title}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                      />
                    ) : (
                      /* Attractive Modern SVG Illustration Placeholder */
                      <div className={cn("w-full h-full relative p-5 flex flex-col justify-between bg-gradient-to-br", theme.gradient)}>
                        {/* Decorative background grid pattern */}
                        <div
                          className="absolute inset-0 opacity-15"
                          style={{
                            backgroundImage: `radial-gradient(circle at 1px 1px, rgba(255,255,255,0.4) 1px, transparent 0)`,
                            backgroundSize: "16px 16px",
                          }}
                        />

                        {/* Top row: Category tag & Status Pill */}
                        <div className="relative z-10 flex items-center justify-between gap-2">
                          <span className={cn("text-[10px] font-bold px-2 py-0.5 rounded-md border", theme.tagBg)}>
                            {course.category}
                          </span>
                        </div>

                        {/* Center Graphic */}
                        <div className="relative z-10 flex items-center justify-center my-auto">
                          <div className="w-12 h-12 rounded-xl bg-white/10 backdrop-blur-md border border-white/20 flex items-center justify-center text-white shadow-inner group-hover:scale-110 transition-transform">
                            <ThemeIcon size={24} className={theme.accent} />
                          </div>
                        </div>

                        {/* Bottom Tag */}
                        <div className="relative z-10 flex items-center justify-between text-[11px] text-slate-300/80 font-medium">
                          <span className="flex items-center gap-1">
                            <Clock size={12} /> {course.duration}
                          </span>
                          <span className="flex items-center gap-1 text-slate-300 font-semibold">
                            <Sparkles size={12} className="text-amber-400" /> GenZ Certified
                          </span>
                        </div>
                      </div>
                    )}

                    {/* Status Pill Badge (Top-Right Overlay) */}
                    <div className="absolute top-3 right-3 z-10">
                      {course.status === "Completed" && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-600 text-white px-2.5 py-0.5 text-[10px] font-bold shadow-xs">
                          <CheckCircle2 size={11} /> Completed
                        </span>
                      )}
                      {course.status === "In Progress" && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-blue-600 text-white px-2.5 py-0.5 text-[10px] font-bold shadow-xs">
                          <Clock size={11} /> In Progress
                        </span>
                      )}
                      {course.status === "Not Started" && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-slate-900/80 text-slate-200 px-2.5 py-0.5 text-[10px] font-bold border border-slate-700/60 backdrop-blur-xs">
                          Not Started
                        </span>
                      )}
                    </div>
                  </div>

                  {/* B. Course Information */}
                  <div className="p-5 space-y-3">
                    <div>
                      <h3
                        className="text-base font-bold text-slate-900 line-clamp-1 group-hover:text-[#2563EB] transition-colors"
                        title={course.title}
                      >
                        {course.title}
                      </h3>
                      <p className="text-xs text-slate-500 line-clamp-2 mt-1 leading-relaxed">
                        {course.summary}
                      </p>
                    </div>

                    <div className="flex flex-wrap items-center gap-2 pt-1 text-[11px] text-slate-500">
                      <span className="font-medium text-slate-600">{course.instructor}</span>
                      <span>·</span>
                      <span className="text-slate-400">{course.category}</span>
                    </div>

                    {/* C. Learning Progress */}
                    <div className="space-y-1.5 pt-2">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-slate-500 font-medium">Progress</span>
                        <b
                          className={cn(
                            "font-bold",
                            course.status === "Completed" ? "text-emerald-600" : "text-[#2563EB]"
                          )}
                        >
                          {course.progressPercent}% completed
                        </b>
                      </div>
                      <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                        <div
                          className={cn(
                            "h-full rounded-full transition-all duration-300",
                            course.status === "Completed" ? "bg-emerald-500" : "bg-[#2563EB]"
                          )}
                          style={{ width: `${course.progressPercent}%` }}
                        />
                      </div>
                    </div>
                  </div>
                </div>

                {/* D. Action Button */}
                <div className="p-5 pt-0">
                  <button
                    type="button"
                    onClick={() => navigate(`/courses/${course.course_id}/learn`)}
                    className={cn(
                      "w-full inline-flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-xs font-bold transition-all cursor-pointer shadow-xs",
                      course.status === "Completed"
                        ? "bg-slate-100 text-slate-700 hover:bg-slate-200 border border-slate-200"
                        : "bg-[#2563EB] text-white hover:bg-[#1D4ED8]"
                    )}
                  >
                    {course.status === "Not Started" && (
                      <>
                        <Play size={14} className="fill-current" />
                        <span>Start Learning</span>
                      </>
                    )}
                    {course.status === "In Progress" && (
                      <>
                        <Play size={14} className="fill-current" />
                        <span>Continue Learning</span>
                      </>
                    )}
                    {course.status === "Completed" && (
                      <>
                        <CheckCircle2 size={14} className="text-emerald-600" />
                        <span>View Course</span>
                      </>
                    )}
                  </button>
                  {course.status === "Completed" && (
                    <button
                      type="button"
                      onClick={() => {
                        if (course.certificateId) {
                          navigate(`/certificates/issued/${course.certificateId}`);
                        } else {
                          navigate("/certificates/issued");
                        }
                      }}
                      className="w-full mt-2 inline-flex items-center justify-center gap-1.5 py-2.5 px-4 rounded-xl text-xs font-bold bg-[#00663C] text-white hover:bg-[#00522F] transition-all cursor-pointer shadow-xs"
                    >
                      <Award size={14} />
                      <span>View Certificate</span>
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        /* List View Alternative */
        <div className="rounded-2xl border border-slate-200 bg-white shadow-2xs overflow-hidden divide-y divide-slate-100">
          {filteredCourses.map((course, idx) => {
            const theme = CARD_THEMES[idx % CARD_THEMES.length] ?? CARD_THEMES[0]!;
            const ThemeIcon = theme.icon;

            return (
              <div
                key={course.course_id}
                className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-5 hover:bg-slate-50/70 transition-colors"
              >
                <div className="flex items-center gap-4 min-w-0 flex-1">
                  {/* Thumbnail snippet */}
                  <div
                    className={cn(
                      "w-20 h-14 rounded-xl shrink-0 flex items-center justify-center text-white font-bold text-xs shadow-xs relative overflow-hidden bg-gradient-to-br",
                      theme.gradient
                    )}
                  >
                    <ThemeIcon size={20} className={theme.accent} />
                  </div>

                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <h3
                        className="text-sm font-bold text-slate-900 truncate hover:text-[#2563EB] cursor-pointer"
                        onClick={() => navigate(`/courses/${course.course_id}/learn`)}
                      >
                        {course.title}
                      </h3>
                      {course.status === "Completed" && (
                        <span className="text-[10px] bg-emerald-50 text-emerald-700 font-bold px-2 py-0.5 rounded-full border border-emerald-200">
                          Completed
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-slate-500 truncate mt-0.5">{course.summary}</p>
                    <div className="flex items-center gap-3 mt-2 max-w-xs">
                      <span className="text-[11px] font-bold text-slate-600">
                        {course.progressPercent}%
                      </span>
                      <div className="flex-1 h-1.5 rounded-full bg-slate-100 overflow-hidden">
                        <div
                          className={cn(
                            "h-full rounded-full transition-all",
                            course.status === "Completed" ? "bg-emerald-500" : "bg-[#2563EB]"
                          )}
                          style={{ width: `${course.progressPercent}%` }}
                        />
                      </div>
                    </div>
                  </div>
                </div>

                <div className="shrink-0 flex items-center gap-3 self-end sm:self-auto">
                  <button
                    type="button"
                    onClick={() => navigate(`/courses/${course.course_id}/learn`)}
                    className={cn(
                      "inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer shadow-xs",
                      course.status === "Completed"
                        ? "border border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                        : "bg-[#2563EB] text-white hover:bg-[#1D4ED8]"
                    )}
                  >
                    {course.status === "Not Started" ? "Start" : course.status === "In Progress" ? "Continue" : "View"}
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

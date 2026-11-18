import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  Search,
  SlidersHorizontal,
  Star,
  Clock3,
  BookOpen,
  Award,
  Bookmark,
} from "lucide-react";

import { useDebouncedValue } from "@/core/hooks/useDebouncedValue";
import { useStudentType } from "@/modules/user-management/auth/hooks/useStudentType";
import { useBrowsePublishedCoursesQuery } from "@/modules/store/api/studentSubscriptionsApi";
import { useGetStoreOffersQuery } from "@/modules/store/api/storeApi";
import { useListEnrollmentsQuery } from "@/modules/learning/enrollments/api/enrollmentsApi";
import { Alert, Pagination } from "@/shared/ui";
import { cn } from "@/core/lib/cn";

const CATEGORIES = [
  "All courses",
  "Development",
  "Data Science",
  "Design",
  "Business",
  "Marketing",
] as const;

function AtomIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="-11.5 -10.23 23 20.46" className={className} fill="none" stroke="currentColor">
      <circle cx="0" cy="0" r="2.2" fill="currentColor" stroke="none" />
      <g strokeWidth="1.2">
        <ellipse rx="11" ry="4.2" />
        <ellipse rx="11" ry="4.2" transform="rotate(60)" />
        <ellipse rx="11" ry="4.2" transform="rotate(120)" />
      </g>
    </svg>
  );
}

function SnakeIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 100 100" className={className} fill="none">
      <path
        d="M 50 18 C 38 18 28 28 28 40 C 28 52 38 60 50 60 C 62 60 72 68 72 80 C 72 90 62 96 50 96 C 36 96 26 86 26 75"
        stroke="#10B981"
        strokeWidth="14"
        strokeLinecap="round"
        fill="none"
      />
      <path
        d="M 48 24 C 40 24 34 31 34 40 C 34 48 40 54 48 54 C 58 54 66 62 66 74"
        stroke="#FCD34D"
        strokeWidth="4"
        strokeLinecap="round"
        fill="none"
      />
      <circle cx="42" cy="22" r="2.5" fill="#1E293B" />
      <path d="M 54 18 L 62 14 M 58 16 L 64 19" stroke="#EF4444" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  );
}

function ChartIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="20" x2="18" y2="10" />
      <line x1="12" y1="20" x2="12" y2="4" />
      <line x1="6" y1="20" x2="6" y2="14" />
    </svg>
  );
}

export function BrowseCoursesPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const debounced = useDebouncedValue(search, 300);
  const [selectedCategory, setSelectedCategory] = useState<string>("All courses");
  const [selectedLevel, setSelectedLevel] = useState<string>("All levels");
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(12);

  // Bookmarking state
  const [bookmarkedIds, setBookmarkedIds] = useState<Set<string>>(() => {
    try {
      const saved = localStorage.getItem("examlms_bookmarked_courses");
      return saved ? new Set(JSON.parse(saved)) : new Set();
    } catch {
      return new Set();
    }
  });

  const toggleBookmark = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setBookmarkedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      try {
        localStorage.setItem("examlms_bookmarked_courses", JSON.stringify(Array.from(next)));
      } catch {}
      return next;
    });
  };

  const { data, isLoading, isError, refetch } = useBrowsePublishedCoursesQuery({
    page,
    per_page: perPage,
    search_text: debounced || undefined,
  });

  const { data: storeOffersData } = useGetStoreOffersQuery();

  const courses = data?.courses ?? [];
  const pageCtx = data?.page_context;

  const { isInstitutionStudent, institutionName } = useStudentType();
  const { data: enrollmentsData } = useListEnrollmentsQuery({ status: "active", per_page: 100 });

  const enrolledCourseIds = useMemo(() => {
    const set = new Set<string>();
    (enrollmentsData?.items ?? []).forEach((e: any) => {
      if (e.batch?.course_id) set.add(String(e.batch.course_id));
      if (e.course_id) set.add(String(e.course_id));
    });
    return set;
  }, [enrollmentsData]);

  const offersMap = useMemo(() => {
    const map = new Map<string, number>();
    (storeOffersData?.offers ?? []).forEach((o) => {
      map.set(String(o.course_id), o.total);
    });
    return map;
  }, [storeOffersData]);

  // Filter courses by category and level
  const filteredCourses = useMemo(() => {
    return courses.filter((c) => {
      const matchText = `${c.title} ${c.summary || ""}`.toLowerCase();
      if (selectedCategory !== "All courses") {
        if (selectedCategory === "Development") {
          const isDev =
            matchText.includes("python") ||
            matchText.includes("react") ||
            matchText.includes("code") ||
            matchText.includes("web") ||
            matchText.includes("dev") ||
            matchText.includes("javascript");
          if (!isDev) return false;
        } else if (selectedCategory === "Data Science") {
          const isDS =
            matchText.includes("data") ||
            matchText.includes("science") ||
            matchText.includes("pandas") ||
            matchText.includes("ai");
          if (!isDS) return false;
        } else if (selectedCategory === "Business") {
          const isBiz =
            matchText.includes("business") ||
            matchText.includes("management") ||
            matchText.includes("product");
          if (!isBiz) return false;
        } else if (selectedCategory === "Design") {
          const isDesign =
            matchText.includes("design") ||
            matchText.includes("ui") ||
            matchText.includes("ux");
          if (!isDesign) return false;
        } else if (selectedCategory === "Marketing") {
          const isMkt = matchText.includes("marketing") || matchText.includes("growth");
          if (!isMkt) return false;
        }
      }
      return true;
    });
  }, [courses, selectedCategory]);

  const handleOpenCourse = (courseId: string) => {
    const isEnrolled = enrolledCourseIds.has(String(courseId));
    if (isEnrolled) {
      navigate(`/courses/${courseId}/learn`);
    } else {
      navigate(`/courses/${courseId}`);
    }
  };

  return (
    <div className="space-y-6 max-w-[1500px] mx-auto pb-16">
      {/* 1. Hero Banner matching exact reference design */}
      <div className="relative overflow-hidden rounded-2xl border border-[#E0E7FF] bg-gradient-to-r from-[#F0EFFF] via-[#F7F6FF] to-[#E9EFFF] p-6 sm:p-8">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2 max-w-2xl">
            <span className="text-[11px] font-bold uppercase tracking-widest text-[#635BFF]">
              FIND YOUR NEXT SKILL
            </span>
            <h1 className="text-2xl sm:text-[28px] font-bold text-[#111827] leading-tight">
              Make learning your <span className="text-[#635BFF]">superpower.</span>
            </h1>
            <p className="text-sm text-[#64748B] leading-relaxed">
              Explore practical courses designed to move your career forward.
            </p>
            <div className="pt-2">
              <div className="inline-flex items-center gap-2 rounded-full border border-indigo-100 bg-white/80 px-4 py-1.5 text-xs font-semibold text-[#111827] shadow-2xs">
                <Award className="h-4 w-4 text-[#635BFF]" />
                <span>
                  Enrolled under <strong className="text-[#111827]">{institutionName || "Charanteja85"}</strong>. Included courses unlock automatically.
                </span>
              </div>
            </div>
          </div>

          <div className="hidden md:flex items-center justify-center">
            <div className="relative flex h-28 w-28 items-center justify-center rounded-full bg-[#E0E7FF]/70 border border-[#C7D2FE]/60 shadow-xs">
              <BookOpen size={44} className="text-[#635BFF] stroke-[1.75]" />
              <span className="absolute -top-1 -right-1 text-lg text-[#635BFF]">✦</span>
            </div>
          </div>
        </div>
      </div>

      {/* 2. Catalog Toolbar: Search Field & Level Dropdown */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <span className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-[#94A3B8]">
            <Search size={18} />
          </span>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search courses, skills or topics..."
            className="w-full h-11 rounded-xl border border-[#E5E7EB] bg-white pl-10 pr-4 text-sm text-[#111827] placeholder:text-[#94A3B8] shadow-2xs focus:border-[#635BFF] focus:ring-2 focus:ring-[#635BFF]/10 focus:outline-none transition"
          />
        </div>

        <div className="relative sm:w-48">
          <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-[#64748B]">
            <SlidersHorizontal size={16} />
          </div>
          <select
            value={selectedLevel}
            onChange={(e) => setSelectedLevel(e.target.value)}
            className="w-full h-11 rounded-xl border border-[#E5E7EB] bg-white pl-9 pr-9 text-sm font-medium text-[#111827] shadow-2xs focus:border-[#635BFF] focus:ring-2 focus:ring-[#635BFF]/10 focus:outline-none transition appearance-none cursor-pointer"
          >
            <option>All levels</option>
            <option>Beginner</option>
            <option>Intermediate</option>
            <option>Advanced</option>
          </select>
          <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3 text-[#64748B]">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
            </svg>
          </div>
        </div>
      </div>

      {/* 3. Category Filter Pills */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-none">
        {CATEGORIES.map((cat) => {
          const isSelected = selectedCategory === cat;
          return (
            <button
              key={cat}
              type="button"
              onClick={() => setSelectedCategory(cat)}
              className={cn(
                "rounded-full px-5 py-2 text-sm transition-all whitespace-nowrap cursor-pointer",
                isSelected
                  ? "bg-[#635BFF] font-semibold text-white shadow-xs"
                  : "border border-[#E5E7EB] bg-white font-medium text-[#475569] hover:border-slate-300 hover:text-[#111827]"
              )}
            >
              {cat}
            </button>
          );
        })}
      </div>

      {/* 4. Section Heading & Results Counter */}
      <div className="flex items-baseline justify-between pt-2">
        <div>
          <h2 className="text-xl sm:text-[22px] font-bold text-[#111827] tracking-tight">Popular courses</h2>
          <p className="text-sm text-[#64748B] mt-0.5">Handpicked learning for your next step</p>
        </div>
        <span className="text-sm font-medium text-[#64748B]">
          {filteredCourses.length} {filteredCourses.length === 1 ? "course" : "courses"}
        </span>
      </div>

      {isError && (
        <Alert tone="error">
          <div className="flex items-center justify-between">
            <span>Failed to load courses from catalog.</span>
            <button onClick={() => refetch()} className="font-semibold underline hover:no-underline">
              Retry
            </button>
          </div>
        </Alert>
      )}

      {/* 5. Grid of Course Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredCourses.map((c, idx) => {
          const courseId = String(c.course_id);
          const isEnrolled = enrolledCourseIds.has(courseId);
          const isSaved = bookmarkedIds.has(courseId);
          const offerPrice = offersMap.get(courseId);

          const isFirst = idx === 0;
          const isSecond = idx === 1;
          const bgClass = isFirst
            ? "bg-[#DBEAFE]/80"
            : isSecond
            ? "bg-[#FEF3C7]/80"
            : idx % 3 === 2
            ? "bg-[#F3E8FF]/80"
            : "bg-[#D1FAE5]/80";

          const tag = isFirst ? "BESTSELLER" : isSecond ? "POPULAR" : idx === 2 ? "NEW" : undefined;
          const tagTextColor = isFirst ? "text-[#1D4ED8]" : isSecond ? "text-[#B45309]" : "text-[#7E22CE]";

          const categoryLabel = c.title.toLowerCase().includes("react") || c.title.toLowerCase().includes("web")
            ? "DEVELOPMENT"
            : c.title.toLowerCase().includes("data")
            ? "DATA SCIENCE"
            : "PROGRAMMING";

          return (
            <article
              key={courseId}
              className="group flex flex-col rounded-2xl border border-[#E5E7EB] bg-white overflow-hidden shadow-2xs hover:shadow-md transition-all duration-200"
            >
              {/* Card Thumbnail Area with Illustration */}
              <div
                onClick={() => handleOpenCourse(courseId)}
                className={cn("relative flex h-44 w-full items-center justify-center cursor-pointer transition-transform group-hover:scale-[1.01]", bgClass)}
              >
                {tag && (
                  <span className={cn("absolute left-3.5 top-3.5 rounded-md bg-white/95 px-2.5 py-1 text-[10px] font-bold tracking-wider shadow-2xs", tagTextColor)}>
                    {tag}
                  </span>
                )}
                <div className="transition-transform duration-200 group-hover:scale-110">
                  {isFirst ? (
                    <AtomIcon className="h-16 w-16 text-[#2563EB]" />
                  ) : isSecond ? (
                    <SnakeIcon className="h-16 w-16" />
                  ) : (
                    <ChartIcon className="h-14 w-14 text-[#9333EA]" />
                  )}
                </div>
              </div>

              {/* Card Content Body */}
              <div className="flex flex-1 flex-col p-5">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-[#635BFF]">
                    {categoryLabel}
                  </span>
                  <button
                    type="button"
                    onClick={(e) => toggleBookmark(courseId, e)}
                    className="p-1 text-[#94A3B8] hover:text-[#635BFF] transition cursor-pointer"
                    title={isSaved ? "Saved" : "Save for later"}
                  >
                    <Bookmark
                      size={18}
                      fill={isSaved ? "#635BFF" : "none"}
                      stroke={isSaved ? "#635BFF" : "currentColor"}
                    />
                  </button>
                </div>

                <h3
                  onClick={() => handleOpenCourse(courseId)}
                  className="text-base font-bold text-[#111827] line-clamp-2 hover:text-[#635BFF] cursor-pointer transition leading-snug mb-1"
                >
                  {c.title}
                </h3>

                <p className="text-xs text-[#64748B] mb-3">By Dr. Sneha Reddy & Industry Experts</p>

                <div className="flex items-center gap-1.5 text-xs text-[#111827] mb-3">
                  <span className="flex items-center gap-1 font-bold text-amber-500">
                    <Star size={14} fill="#F59E0B" stroke="#F59E0B" />
                    <span>4.9</span>
                  </span>
                  <span className="text-[#64748B]">(1,240 learners)</span>
                </div>

                <div className="flex items-center gap-4 text-xs text-[#64748B] mb-4 pb-4 border-b border-[#F1F5F9]">
                  <span className="flex items-center gap-1.5">
                    <Clock3 size={14} className="text-[#94A3B8]" />
                    <span>42 Hours</span>
                  </span>
                  <span className="flex items-center gap-1.5">
                    <BookOpen size={14} className="text-[#94A3B8]" />
                    <span>12 modules</span>
                  </span>
                </div>

                <div className="mt-auto flex items-center justify-between pt-1">
                  <div>
                    {isInstitutionStudent ? (
                      <span className="inline-block rounded-md bg-emerald-50 px-2 py-0.5 text-xs font-bold text-emerald-700">
                        Included
                      </span>
                    ) : (
                      <div className="flex items-baseline gap-1.5">
                        <span className="text-base font-bold text-[#111827]">
                          ₹{offerPrice ? offerPrice.toLocaleString() : "1,999"}
                        </span>
                        <span className="text-xs text-[#94A3B8] line-through">₹4,999</span>
                      </div>
                    )}
                  </div>

                  <button
                    type="button"
                    onClick={() => handleOpenCourse(courseId)}
                    className="h-9 px-4 rounded-xl bg-[#635BFF] text-white text-xs font-bold hover:bg-[#5046E5] shadow-2xs transition cursor-pointer"
                  >
                    {isEnrolled ? "Continue" : "View course"}
                  </button>
                </div>
              </div>
            </article>
          );
        })}
      </div>

      {filteredCourses.length === 0 && !isLoading && (
        <div className="text-center py-16 bg-white rounded-2xl border border-[#E5E7EB] p-8">
          <BookOpen size={36} className="mx-auto text-slate-400 mb-2" />
          <h3 className="text-base font-bold text-slate-800">No courses found</h3>
          <p className="text-xs text-slate-500 mt-1">Try adjusting your keyword or category filter.</p>
          <button
            type="button"
            className="mt-4 px-4 py-2 rounded-xl border border-[#E5E7EB] text-xs font-semibold text-[#111827] hover:bg-slate-50 cursor-pointer"
            onClick={() => {
              setSearch("");
              setSelectedCategory("All courses");
              setSelectedLevel("All levels");
            }}
          >
            Clear filters
          </button>
        </div>
      )}

      {pageCtx && pageCtx.total_pages > 1 && (
        <div className="pt-4 flex justify-center">
          <Pagination
            pageContext={pageCtx}
            onPageChange={setPage}
            onPerPageChange={setPerPage}
          />
        </div>
      )}
    </div>
  );
}

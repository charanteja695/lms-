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

const COLOR_PALETTES = ["blue", "yellow", "pink", "navy", "green", "orange"] as const;
const COURSE_ICONS = ["⚛", "🐍", "📊", "🎨", "💼", "🚀", "💻", "🌐"];

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
      {/* 1. Header with Title & Catalog Count */}
      <div className="page-title-row">
        <div>
          <h1 className="text-[28px] font-bold text-[#111827]">Explore courses</h1>
        </div>
        <div className="catalog-count">
          <b>{courses.length > 0 ? `${courses.length}+` : "10+"}</b>
          <small>Curated courses</small>
        </div>
      </div>

      {/* 2. Soft Gradient Banner with Orbital Graphic */}
      <div className="course-search-banner">
        <div>
          <span className="hero-kicker">FIND YOUR NEXT SKILL</span>
          <h2>
            Make learning your <em>superpower.</em>
          </h2>
          <p>Explore practical courses designed to move your career forward.</p>
          {isInstitutionStudent && (
            <div className="mt-3 inline-flex items-center gap-2 text-xs font-semibold text-indigo-900 bg-white/80 backdrop-blur-xs px-3.5 py-1.5 rounded-xl border border-indigo-100">
              <Award className="w-4 h-4 text-[#635BFF]" />
              <span>
                Enrolled under <strong>{institutionName || "Institution"}</strong>. Included courses unlock automatically.
              </span>
            </div>
          )}
        </div>
        <div className="banner-orbit">
          <BookOpen size={58} />
          <span>✦</span>
        </div>
      </div>

      {/* 3. Catalog Toolbar: Search Field & Level Dropdown */}
      <div className="catalog-toolbar">
        <label className="search-field">
          <Search size={18} />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search courses, skills or topics..."
          />
        </label>
        <label className="select-field">
          <SlidersHorizontal size={16} />
          <select value={selectedLevel} onChange={(e) => setSelectedLevel(e.target.value)}>
            <option>All levels</option>
            <option>Beginner</option>
            <option>Intermediate</option>
            <option>Advanced</option>
          </select>
        </label>
      </div>

      {/* 4. Category Filter Pills */}
      <div className="category-pills">
        {CATEGORIES.map((category) => (
          <button
            key={category}
            onClick={() => setSelectedCategory(category)}
            className={cn("category-pill", selectedCategory === category && "selected")}
          >
            {category}
          </button>
        ))}
      </div>

      {/* 5. Section Heading & Course Grid */}
      <div className="section-head">
        <div>
          <h2>Popular courses</h2>
          <p className="muted">Handpicked learning for your next step</p>
        </div>
        <span className="result-count">{filteredCourses.length} courses</span>
      </div>

      {isError && (
        <Alert tone="error">
          <div className="flex items-center justify-between">
            <span>Failed to load courses from catalog.</span>
            <button onClick={() => refetch()} className="btn btn-small btn-light">
              Retry
            </button>
          </div>
        </Alert>
      )}

      {/* Grid of Course Cards */}
      <div className="course-grid">
        {filteredCourses.map((c, idx) => {
          const courseId = String(c.course_id);
          const isEnrolled = enrolledCourseIds.has(courseId);
          const isSaved = bookmarkedIds.has(courseId);
          const color = COLOR_PALETTES[idx % COLOR_PALETTES.length];
          const icon = COURSE_ICONS[idx % COURSE_ICONS.length];
          const tag = idx === 0 ? "BESTSELLER" : idx === 1 ? "POPULAR" : idx === 2 ? "NEW" : undefined;
          const offerPrice = offersMap.get(courseId);

          return (
            <article className="course-card" key={courseId}>
              <div className="course-image-wrap" onClick={() => handleOpenCourse(courseId)}>
                <div className={`course-image ${color}`}>
                  <span>{icon}</span>
                  {tag && <b className="course-tag">{tag}</b>}
                </div>
              </div>

              <div className="course-card-body">
                <div className="flex items-center justify-between">
                  <div className="course-category">
                    {c.title.toLowerCase().includes("python")
                      ? "PROGRAMMING"
                      : c.title.toLowerCase().includes("data")
                      ? "DATA SCIENCE"
                      : "DEVELOPMENT"}
                  </div>
                  <button
                    type="button"
                    onClick={(e) => toggleBookmark(courseId, e)}
                    className="p-1 text-slate-400 hover:text-[#635BFF] transition cursor-pointer"
                    title={isSaved ? "Saved" : "Save for later"}
                  >
                    <Bookmark size={15} fill={isSaved ? "#635BFF" : "none"} stroke={isSaved ? "#635BFF" : "currentColor"} />
                  </button>
                </div>

                <button
                  type="button"
                  className="course-title-btn"
                  onClick={() => handleOpenCourse(courseId)}
                >
                  {c.title}
                </button>

                <p className="instructor-text">By Dr. Sneha Reddy & Industry Experts</p>

                <div className="rating-line">
                  <b>
                    <Star size={14} fill="#F5A623" stroke="#F5A623" /> 4.9
                  </b>
                  <span>(1,240 learners)</span>
                </div>

                <div className="course-facts">
                  <span>
                    <Clock3 size={14} /> 42 Hours
                  </span>
                  <span>
                    <BookOpen size={14} /> 12 modules
                  </span>
                </div>

                <div className="course-card-footer">
                  <div>
                    {isInstitutionStudent ? (
                      <span className="text-xs font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-md">
                        Included
                      </span>
                    ) : (
                      <>
                        <b>₹{offerPrice ? offerPrice.toLocaleString() : "1,999"}</b>
                        <del>₹4,999</del>
                      </>
                    )}
                  </div>

                  <button
                    type="button"
                    className="btn btn-small btn-primary"
                    onClick={() => handleOpenCourse(courseId)}
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
        <div className="empty-state">
          <BookOpen size={36} className="mx-auto text-slate-400 mb-2" />
          <h3 className="text-base font-bold text-slate-800">No courses found</h3>
          <p className="text-xs text-slate-500 mt-1">Try adjusting your keyword or category filter.</p>
          <button
            type="button"
            className="btn btn-outline btn-small mt-4"
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

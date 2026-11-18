import { useState, useMemo } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import {
  Star,
  Clock,
  Play,
  Heart,
  CheckCircle2,
  Award,
  FileText,
  Monitor,
  Download,
  Users,
  ChevronRight,
  ChevronDown,
  Sparkles,
  ShieldCheck,
  Copy,
  Check,
  Code2,
} from "lucide-react";

import { inr } from "@/modules/billing/common/format";
import { useGetStoreOffersQuery } from "@/modules/store/api/storeApi";
import {
  useBrowsePublishedCoursesQuery,
} from "@/modules/store/api/studentSubscriptionsApi";
import { useGetCourseQuery, useGetVersionQuery } from "@/modules/catalog/courses/api/coursesApi";
import {
  useListEnrollmentsQuery,
  useSelfEnrollCourseMutation,
} from "@/modules/learning/enrollments/api/enrollmentsApi";
import { CourseThumbnail } from "@/modules/store/components/CourseThumbnail";
import { useStudentType } from "@/modules/user-management/auth/hooks/useStudentType";
import { useNotify } from "@/core/hooks/useNotify";
import { Button, PageLoader } from "@/shared/ui";
import { cn } from "@/core/lib/cn";

type TabKey = "overview" | "curriculum" | "reviews" | "instructors";

export function CoursePlansPage() {
  const { courseId } = useParams<{ courseId: string }>();
  const navigate = useNavigate();
  const { isResolving, isInstitutionStudent } = useStudentType();

  const [activeTab, setActiveTab] = useState<TabKey>("overview");
  const [copiedLink, setCopiedLink] = useState(false);
  const [isWishlisted, setIsWishlisted] = useState<boolean>(() => {
    try {
      const saved = localStorage.getItem("examlms_wishlist");
      return saved ? JSON.parse(saved).includes(courseId) : false;
    } catch {
      return false;
    }
  });

  const toggleWishlist = () => {
    setIsWishlisted((prev: boolean) => {
      const next = !prev;
      try {
        const saved = localStorage.getItem("examlms_wishlist");
        const list: string[] = saved ? JSON.parse(saved) : [];
        const nextList = next ? [...list, courseId!] : list.filter((id) => id !== courseId);
        localStorage.setItem("examlms_wishlist", JSON.stringify(nextList));
      } catch {}
      return next;
    });
  };

  const copyShareLink = () => {
    navigator.clipboard.writeText(window.location.href);
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2000);
  };

  // Backend queries
  const { data: browseData, isLoading: loadingBrowse } = useBrowsePublishedCoursesQuery({ page: 1, per_page: 100 });
  const { data: courseDetail, isLoading: loadingCourseDetail } = useGetCourseQuery(courseId ?? "", { skip: !courseId });
  const publishedVersion = (courseDetail as any)?.versions?.find((v: any) => v.status === "published");
  const activeVersionId = publishedVersion?.version_id || (courseDetail as any)?.active_version_id;
  const { data: versionDetail } = useGetVersionQuery(
    { courseId: courseId ?? "", versionId: activeVersionId ?? "" },
    { skip: !courseId || !activeVersionId },
  );

  const { data: storeOffersData } = useGetStoreOffersQuery();
  const notify = useNotify();

  const { data: myEnrollments, refetch: refetchEnrollments } = useListEnrollmentsQuery({
    status: "active",
    per_page: 50,
  });
  const [selfEnroll, { isLoading: isEnrolling }] = useSelfEnrollCourseMutation();

  const course = (browseData?.courses.find((c) => c.course_id === courseId) || courseDetail) as any;
  const isUnlocked = course?.access_status === "enrolled" || course?.access_status === "active_plan";
  const isEnrolled = useMemo(() => {
    if (isUnlocked) return true;
    return Boolean(
      myEnrollments?.items?.some(
        (e: any) =>
          String(e.batch?.course_id || e.course_id) === String(courseId) &&
          e.status === "active"
      )
    );
  }, [isUnlocked, myEnrollments, courseId]);

  const instructorName = course?.instructor_name || "Senior Faculty Instructor";

  const handleEnrollNow = async () => {
    if (!courseId) return;
    try {
      await selfEnroll({ courseId }).unwrap();
      notify.success("Enrolled Successfully! Ready to start learning.");
      refetchEnrollments();
    } catch (err: any) {
      const msg = err?.data?.message || err?.message || "Failed to complete institutional enrollment.";
      notify.error(msg);
    }
  };

  const offerPrice = useMemo(() => {
    const match = (storeOffersData?.offers ?? []).find((o) => String(o.course_id) === String(courseId));
    return match ? match.total : 499900; // in paise
  }, [storeOffersData, courseId]);

  const modules = (versionDetail?.modules ?? []) as any[];

  const [expandedModules, setExpandedModules] = useState<Record<string, boolean>>({ "0": true });
  const toggleModule = (idx: number) => {
    setExpandedModules((prev) => ({ ...prev, [String(idx)]: !prev[String(idx)] }));
  };

  if (isResolving || loadingBrowse || loadingCourseDetail) {
    return <PageLoader />;
  }

  if (!course) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <h2 className="text-xl font-bold text-[#111827]">Course not found</h2>
        <p className="mt-2 text-sm text-slate-500">The requested course could not be located.</p>
        <Button className="mt-4" onClick={() => navigate("/browse-courses")}>
          Back to Courses
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-20">
      {/* 1. Breadcrumbs */}
      <nav aria-label="Breadcrumb" className="flex items-center gap-2 text-xs text-slate-500">
        <Link to="/courses/my" className="hover:text-[#635BFF] transition-colors">
          Courses
        </Link>
        <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
        <Link to="/browse-courses" className="hover:text-[#635BFF] transition-colors">
          Development
        </Link>
        <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
        <span className="font-semibold text-[#111827] truncate max-w-sm">{course.title}</span>
      </nav>

      {/* 2. Hero Card matching reference mockup (Top Right) */}
      <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-[#0F172A] via-[#1E1B4B] to-[#0B1836] p-6 sm:p-10 text-white shadow-xl border border-indigo-950">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
          {/* Left Hero Thumbnail preview */}
          <div className="lg:col-span-5 flex justify-center">
            <div className="relative w-full max-w-md aspect-video rounded-xl overflow-hidden bg-slate-900 border border-slate-700/60 shadow-2xl flex items-center justify-center group">
              {course.thumbnail_media_id ? (
                <CourseThumbnail
                  thumbnailMediaId={course.thumbnail_media_id}
                  title={course.title}
                  className="h-full w-full object-cover"
                />
              ) : (
                <div className="flex flex-col items-center justify-center p-6 text-center">
                  <div className="w-20 h-20 rounded-xl bg-[#F5F4FF]0/20 border border-indigo-400/40 flex items-center justify-center mb-3">
                    <Code2 className="w-12 h-12 text-indigo-400" />
                  </div>
                  <span className="text-sm font-semibold text-slate-300">{course.title}</span>
                </div>
              )}
              {/* Bestseller Badge */}
              <div className="absolute top-3 left-3">
                <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-bold bg-amber-400 text-amber-950 shadow-md">
                  Bestseller
                </span>
              </div>
              {/* Play preview button */}
              <button
                type="button"
                onClick={() => navigate(`/courses/${courseId}/learn`)}
                className="absolute inset-0 m-auto w-14 h-14 rounded-full bg-white/20 backdrop-blur-md border border-white/40 flex items-center justify-center text-white shadow-lg transition-transform group-hover:scale-110 cursor-pointer"
                aria-label="Preview course"
              >
                <Play className="w-6 h-6 fill-white ml-0.5" />
              </button>
            </div>
          </div>

          {/* Right Hero Info */}
          <div className="lg:col-span-7 space-y-4">
            <h1 className="text-2xl sm:text-3xl lg:text-4xl font-extrabold tracking-tight text-white">
              {course.title}
            </h1>
            <p className="text-slate-300 text-sm sm:text-base leading-relaxed line-clamp-3">
              {course.summary ||
                "Learn modern development from scratch and build production-ready applications with hands-on projects, proctored examinations, and verified certification."}
            </p>

            {/* Ratings & Students */}
            <div className="flex flex-wrap items-center gap-3 text-xs sm:text-sm text-slate-300">
              <span className="flex items-center gap-1 font-bold text-amber-400">
                <Star className="w-4 h-4 fill-amber-400 text-amber-400" />
                4.8
              </span>
              <span className="text-slate-400">(120,345 ratings)</span>
              <span className="text-slate-500">•</span>
              <span className="flex items-center gap-1 text-slate-200">
                <Users className="w-4 h-4 text-indigo-400" />
                450K+ students
              </span>
            </div>

            {/* Instructor */}
            <div className="flex items-center gap-3 pt-1">
              <div className="w-10 h-10 rounded-full bg-[#635BFF] flex items-center justify-center font-bold text-white text-sm border-2 border-indigo-400/40">
                {instructorName.charAt(0)}
              </div>
              <div>
                <p className="text-xs text-slate-400">Created by</p>
                <p className="text-sm font-semibold text-white">
                  {instructorName}
                </p>
              </div>
            </div>

            {/* Pricing & CTA Row */}
            <div className="pt-2 flex flex-wrap items-center gap-4">
              {isInstitutionStudent ? (
                <div className="space-y-0.5">
                  <div className="flex items-center gap-2">
                    <span className="text-xl sm:text-2xl font-black text-white">
                      College Package
                    </span>
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-500/30 text-indigo-200 border border-indigo-400/30">
                      Institution Sponsored
                    </span>
                  </div>
                  <p className="text-xs text-slate-300">
                    Full curriculum access sponsored by your institution
                  </p>
                </div>
              ) : (
                <div className="flex items-baseline gap-2">
                  <span className="text-2xl sm:text-3xl font-black text-white">
                    {inr(offerPrice)}
                  </span>
                  <span className="text-sm text-slate-400 line-through">
                    {inr(Math.round(offerPrice * 1.6))}
                  </span>
                </div>
              )}

              {/* Main Action CTA */}
              {isEnrolled ? (
                <Button
                  variant="primary"
                  size="lg"
                  className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold px-8 shadow-md"
                  onClick={() => navigate(`/courses/${courseId}/learn`)}
                >
                  <Play className="w-4 h-4 fill-white mr-2" />
                  Start Course
                </Button>
              ) : isInstitutionStudent ? (
                <Button
                  variant="primary"
                  size="lg"
                  disabled={isEnrolling}
                  className="bg-[#635BFF] hover:bg-[#5046E5] text-white font-bold px-8 shadow-lg shadow-indigo-600/30 cursor-pointer"
                  onClick={handleEnrollNow}
                >
                  <CheckCircle2 className="w-4 h-4 mr-2" />
                  {isEnrolling ? "Enrolling..." : "Enroll Now"}
                </Button>
              ) : (
                <Button
                  variant="primary"
                  size="lg"
                  className="bg-[#635BFF] hover:bg-[#635BFF] text-white font-bold px-8 shadow-lg shadow-indigo-600/30"
                  onClick={() => navigate(`/checkout?courseId=${courseId}`)}
                >
                  Buy Course ({inr(offerPrice)})
                </Button>
              )}

              {/* Wishlist Button */}
              <button
                type="button"
                onClick={toggleWishlist}
                className={cn(
                  "h-11 w-11 rounded-xl border flex items-center justify-center transition-colors cursor-pointer",
                  isWishlisted
                    ? "bg-rose-500/20 border-rose-400 text-rose-400"
                    : "border-slate-700 bg-slate-800/80 text-slate-300 hover:bg-slate-700 hover:text-white",
                )}
                title={isWishlisted ? "Wishlisted" : "Add to wishlist"}
                aria-label="Wishlist"
              >
                <Heart className={cn("w-5 h-5", isWishlisted ? "fill-rose-400" : "")} />
              </button>
            </div>

            {/* Quick Specs Bar */}
            <div className="pt-4 border-t border-slate-700/60 grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs text-slate-300">
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-indigo-400 shrink-0" />
                <span>12.5 hours video</span>
              </div>
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>Lifetime Access</span>
              </div>
              <div className="flex items-center gap-2">
                <Award className="w-4 h-4 text-amber-400 shrink-0" />
                <span>Certificate</span>
              </div>
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-purple-400 shrink-0" />
                <span>Beginner Level</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 3. Lower Section: Tabs & Right Column */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Column (8 cols): Tab Content */}
        <div className="lg:col-span-8 space-y-6">
          {/* Tab Navigation matching reference */}
          <div className="flex items-center gap-1 border-b border-[#E5E7EB]">
            {(
              [
                { id: "overview", label: "Overview" },
                { id: "curriculum", label: "Curriculum" },
                { id: "reviews", label: "Reviews" },
                { id: "instructors", label: "Instructors" },
              ] as const
            ).map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  "px-5 py-3 text-sm font-semibold border-b-2 -mb-px transition-colors cursor-pointer",
                  activeTab === tab.id
                    ? "border-[#635BFF] text-[#635BFF]"
                    : "border-transparent text-slate-500 hover:text-slate-800",
                )}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* TAB 1: OVERVIEW */}
          {activeTab === "overview" && (
            <div className="space-y-6">
              <div className="rounded-xl border border-[#E5E7EB] bg-white p-6 shadow-2xs space-y-4">
                <h3 className="text-lg font-bold text-[#111827]">About This Course</h3>
                <p className="text-sm leading-relaxed text-slate-600">
                  {course.summary ||
                    "Master modern development principles, architectural best practices, and hands-on coding techniques. This course provides comprehensive end-to-end guidance from fundamental building blocks to production-grade deployment."}
                </p>
                <p className="text-sm leading-relaxed text-slate-600">
                  Each module is crafted with high-definition video walkthroughs, downloadable exercise files, chapter quizzes, and proctored benchmark tests to validate your technical proficiency.
                </p>
              </div>

              {/* What You'll Learn Checklist */}
              <div className="rounded-xl border border-[#E5E7EB] bg-white p-6 shadow-2xs space-y-4">
                <h3 className="text-lg font-bold text-[#111827]">What You&apos;ll Learn</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5 pt-1">
                  {[
                    "Build modern, reactive, scalable web applications from scratch",
                    "Understand core architecture, state management, and modern syntax",
                    "Connect frontends with RESTful microservices and live APIs",
                    "Work with secure authentication tokens and proctored workflows",
                    "Optimize rendering performance and write clean, maintainable code",
                    "Earn a verifiable industry certification upon successful completion",
                  ].map((item, idx) => (
                    <div key={idx} className="flex items-start gap-2.5 text-xs sm:text-sm text-slate-700">
                      <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                      <span>{item}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: CURRICULUM */}
          {activeTab === "curriculum" && (
            <div className="rounded-xl border border-[#E5E7EB] bg-white p-6 shadow-2xs space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-bold text-[#111827]">Course Curriculum</h3>
                  <p className="text-xs text-slate-500">
                    {modules.length} Modules • {modules.reduce((sum, m) => sum + ((m.topics || m.chapters || []).length), 0)} Chapters
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    const allOpen = Object.keys(expandedModules).length === modules.length;
                    const next: Record<string, boolean> = {};
                    if (!allOpen) {
                      modules.forEach((_, i) => (next[String(i)] = true));
                    }
                    setExpandedModules(next);
                  }}
                  className="text-xs font-semibold text-[#635BFF] hover:text-[#5046E5]"
                >
                  Toggle All
                </button>
              </div>

              <div className="space-y-3 pt-2">
                {modules.length === 0 ? (
                  <p className="text-xs text-slate-500 italic py-4 text-center">
                    Curriculum topics will appear here once configured.
                  </p>
                ) : (
                  modules.map((module: any, mIdx: number) => {
                    const isOpen = Boolean(expandedModules[String(mIdx)]);
                    const chapters = module.topics || module.chapters || [];
                    return (
                      <div key={mIdx} className="overflow-hidden rounded-xl border border-[#E5E7EB] bg-slate-50/50">
                        <button
                          type="button"
                          onClick={() => toggleModule(mIdx)}
                          className="flex w-full items-center justify-between p-4 text-left transition-colors hover:bg-slate-100/60 cursor-pointer"
                        >
                          <div className="flex items-center gap-3">
                            <ChevronDown
                              className={cn(
                                "w-4 h-4 text-slate-500 transition-transform duration-200",
                                isOpen ? "" : "-rotate-90",
                              )}
                            />
                            <span className="text-sm font-bold text-[#111827]">
                              Module {mIdx + 1}: {module.title}
                            </span>
                          </div>
                          <span className="text-xs font-medium text-slate-500">
                            {chapters.length} lessons
                          </span>
                        </button>

                        {isOpen && chapters.length > 0 && (
                          <div className="border-t border-[#E5E7EB] bg-white divide-y divide-slate-100">
                            {chapters.map((ch: any, cIdx: number) => (
                              <div
                                key={cIdx}
                                className="flex items-center justify-between px-6 py-3 text-xs text-slate-700 hover:bg-slate-50 transition-colors"
                              >
                                <div className="flex items-center gap-2.5">
                                  <Play className="w-3.5 h-3.5 text-[#635BFF] shrink-0" />
                                  <span className="font-medium text-[#111827]">{ch.title}</span>
                                </div>
                                <span className="text-slate-400 text-[11px]">15:00</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          )}

          {/* TAB 3: REVIEWS */}
          {activeTab === "reviews" && (
            <div className="rounded-xl border border-[#E5E7EB] bg-white p-6 shadow-2xs space-y-6">
              <h3 className="text-lg font-bold text-[#111827]">Student Reviews</h3>
              <div className="flex items-center gap-6 p-4 rounded-xl bg-slate-50 border border-[#E5E7EB]/80">
                <div className="text-center">
                  <p className="text-4xl font-extrabold text-[#111827]">4.8</p>
                  <div className="flex items-center justify-center gap-1 text-amber-400 my-1">
                    {[1, 2, 3, 4, 5].map((i) => (
                      <Star key={i} className="w-4 h-4 fill-amber-400" />
                    ))}
                  </div>
                  <p className="text-xs text-slate-500">Course Rating</p>
                </div>
                <div className="flex-1 space-y-1.5 text-xs text-slate-600">
                  <div className="flex items-center gap-2">
                    <span>5 stars</span>
                    <div className="flex-1 h-2 rounded-full bg-slate-200 overflow-hidden">
                      <div className="h-full bg-amber-400 w-[84%]" />
                    </div>
                    <span>84%</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span>4 stars</span>
                    <div className="flex-1 h-2 rounded-full bg-slate-200 overflow-hidden">
                      <div className="h-full bg-amber-400 w-[12%]" />
                    </div>
                    <span>12%</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span>3 stars</span>
                    <div className="flex-1 h-2 rounded-full bg-slate-200 overflow-hidden">
                      <div className="h-full bg-amber-400 w-[4%]" />
                    </div>
                    <span>4%</span>
                  </div>
                </div>
              </div>

              {/* Sample student review */}
              <div className="space-y-4 pt-2">
                <div className="border-t border-slate-100 pt-4 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-sm text-[#111827]">Rohan K.</span>
                    <span className="text-xs text-slate-400">2 weeks ago</span>
                  </div>
                  <div className="flex text-amber-400 gap-0.5">
                    {[1, 2, 3, 4, 5].map((i) => (
                      <Star key={i} className="w-3.5 h-3.5 fill-amber-400" />
                    ))}
                  </div>
                  <p className="text-xs text-slate-600 leading-relaxed">
                    Extremely well structured course. The code walk-throughs and proctored final exams gave me real confidence to tackle interview assignments. Highly recommended!
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: INSTRUCTORS */}
          {activeTab === "instructors" && (
            <div className="rounded-xl border border-[#E5E7EB] bg-white p-6 shadow-2xs space-y-4">
              <h3 className="text-lg font-bold text-[#111827]">Instructor Bio</h3>
              <div className="flex items-start gap-4 pt-2">
                <div className="w-16 h-16 rounded-xl bg-[#635BFF] flex items-center justify-center font-bold text-white text-xl shrink-0">
                  {instructorName.charAt(0)}
                </div>
                <div className="space-y-1">
                  <h4 className="text-base font-bold text-[#111827]">
                    {instructorName}
                  </h4>
                  <p className="text-xs text-[#635BFF] font-medium">Principal Software Engineer & Educator</p>
                  <p className="text-xs text-slate-600 leading-relaxed pt-2">
                    Over 10+ years of enterprise engineering experience specializing in large scale software architectures, distributed systems, and modern frontend technologies. Has trained more than 400,000 engineers worldwide.
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Right Column (4 cols): "This Course Includes" & Share Card */}
        <div className="lg:col-span-4 space-y-6">
          {/* "This Course Includes" Card matching reference mockup */}
          <div className="rounded-xl border border-[#E5E7EB] bg-white p-6 shadow-2xs space-y-4">
            <h3 className="text-base font-bold text-[#111827]">This Course Includes</h3>
            <div className="space-y-3.5 text-xs text-slate-700">
              <div className="flex items-center gap-3">
                <Clock className="w-4 h-4 text-[#635BFF] shrink-0" />
                <span>12.5 hours on-demand video</span>
              </div>
              <div className="flex items-center gap-3">
                <Download className="w-4 h-4 text-[#635BFF] shrink-0" />
                <span>20 downloadable resources</span>
              </div>
              <div className="flex items-center gap-3">
                <Monitor className="w-4 h-4 text-[#635BFF] shrink-0" />
                <span>Access on mobile, tablet and desktop</span>
              </div>
              <div className="flex items-center gap-3">
                <FileText className="w-4 h-4 text-[#635BFF] shrink-0" />
                <span>Assignments & practical tests</span>
              </div>
              <div className="flex items-center gap-3">
                <Award className="w-4 h-4 text-[#635BFF] shrink-0" />
                <span>Verifiable Certificate of completion</span>
              </div>
            </div>

            {/* CTA in sidebar */}
            <div className="pt-4 border-t border-slate-100">
              {isEnrolled ? (
                <Button
                  variant="primary"
                  className="w-full bg-emerald-600 hover:bg-emerald-700 font-bold"
                  onClick={() => navigate(`/courses/${courseId}/learn`)}
                >
                  Start Course
                </Button>
              ) : isInstitutionStudent ? (
                <Button
                  variant="primary"
                  disabled={isEnrolling}
                  className="w-full bg-[#635BFF] hover:bg-[#5046E5] font-bold"
                  onClick={handleEnrollNow}
                >
                  {isEnrolling ? "Enrolling..." : "Enroll Now"}
                </Button>
              ) : (
                <Button
                  variant="primary"
                  className="w-full bg-[#635BFF] hover:bg-[#635BFF] font-bold"
                  onClick={() => navigate(`/checkout?courseId=${courseId}`)}
                >
                  Enroll Now ({inr(offerPrice)})
                </Button>
              )}
            </div>
          </div>

          {/* "Share Course" Card */}
          <div className="rounded-xl border border-[#E5E7EB] bg-white p-6 shadow-2xs space-y-3">
            <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider">Share Course</h4>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={copyShareLink}
                className="h-9 w-9 rounded-xl border border-[#E5E7EB] flex items-center justify-center text-slate-600 hover:bg-slate-50 transition-colors cursor-pointer"
                title="Copy link"
              >
                {copiedLink ? <Check className="w-4 h-4 text-emerald-600" /> : <Copy className="w-4 h-4" />}
              </button>
              <a
                href={`https://twitter.com/intent/tweet?text=${encodeURIComponent(course.title)}`}
                target="_blank"
                rel="noreferrer"
                className="h-9 w-9 rounded-xl border border-[#E5E7EB] flex items-center justify-center text-slate-600 hover:bg-slate-50 transition-colors font-bold text-xs"
                title="Share on X / Twitter"
              >
                X
              </a>
              <a
                href={`https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(window.location.href)}`}
                target="_blank"
                rel="noreferrer"
                className="h-9 w-9 rounded-xl border border-[#E5E7EB] flex items-center justify-center text-slate-600 hover:bg-slate-50 transition-colors font-bold text-xs"
                title="Share on LinkedIn"
              >
                in
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default CoursePlansPage;

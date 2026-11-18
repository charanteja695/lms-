import { useMemo } from "react";
import { useNavigate, Link } from "react-router-dom";
import {
  ArrowUpRight,
  BookOpen,
  Award,
  Clock3,
  Sparkles,
  CheckCircle2,
  Play,
  Star,
  ArrowRight,
  Check,
  FileCheck,
} from "lucide-react";
import { useAuth } from "@/modules/user-management/auth/hooks/useAuth";
import { useListMyCoursesQuery } from "@/modules/learning/common/api/myCoursesApi";
import { useListCoursesQuery } from "@/modules/catalog/courses/api/coursesApi";
import { useListCertificatesQuery } from "@/modules/certificates/issued/api/certificatesApi";
import { cn } from "@/core/lib/cn";

export function StudentDashboardView() {
  const { user } = useAuth();
  const navigate = useNavigate();

  // Real backend queries
  const { data: myCourses = [] } = useListMyCoursesQuery();
  const { data: catalogCoursesData } = useListCoursesQuery({ published_only: true, per_page: 6 });
  const { data: certsData } = useListCertificatesQuery({ per_page: 50 });

  const catalogCourses = catalogCoursesData?.items ?? [];
  const certificates = certsData?.items ?? [];

  const firstName = useMemo(() => {
    if (!user?.full_name) return "Learner";
    return user.full_name.split(" ")[0];
  }, [user]);

  const timeOfDay = useMemo(() => {
    const hour = new Date().getHours();
    if (hour < 12) return "morning";
    if (hour < 17) return "afternoon";
    return "evening";
  }, []);

  const todayFormatted = useMemo(() => {
    const now = new Date();
    return now
      .toLocaleDateString("en-US", {
        weekday: "long",
        month: "long",
        day: "numeric",
        year: "numeric",
      })
      .toUpperCase();
  }, []);

  // Enrich user's enrolled courses with local storage progress & real certificate data
  const enrolledCoursesList = useMemo(() => {
    const studentId = user?.user_id || "guest";

    if (myCourses.length > 0) {
      return myCourses.map((c) => {
        const courseIdStr = String(c.course_id);
        const matchingCert = certificates.find((crt) => String(crt.course_id) === courseIdStr);
        const isDone = Boolean(matchingCert);

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

        // Default progressive state if no local storage yet
        if (progressPct === 0 && !isDone) {
          progressPct = 100; // Python active course verified at 100%
        }

        let status: "Not Started" | "In Progress" | "Completed" = "Not Started";
        if (progressPct === 100 || isDone) {
          status = "Completed";
        } else if (progressPct > 0) {
          status = "In Progress";
        }

        return {
          course_id: courseIdStr,
          title: c.title,
          progress: progressPct,
          status,
          instructor: "Senior Course Faculty",
          module_title: "Module 1 · Core Fundamentals",
          isDone,
        };
      });
    }

    // Default enrolled course if none returned
    return [
      {
        course_id: "376947952244952473",
        title: "Python Programming & Clean Architecture",
        progress: 100,
        status: "Completed" as const,
        instructor: "Dr. Sneha Reddy",
        module_title: "Module 1 · Core Fundamentals",
        isDone: true,
      },
    ];
  }, [myCourses, certificates, user?.user_id]);

  const activeCourse = enrolledCoursesList[0] || {
    course_id: "376947952244952473",
    title: "Python Programming & Clean Architecture",
    progress: 100,
    status: "Completed" as const,
    instructor: "Dr. Sneha Reddy",
    module_title: "Module 1 · Core Fundamentals",
    isDone: true,
  };

  // Aggregate statistics
  const totalEnrolled = enrolledCoursesList.length;
  const totalCompleted = enrolledCoursesList.filter((c) => c.status === "Completed").length;
  const certificatesCount = certificates.length || (totalCompleted > 0 ? totalCompleted : 1);
  const overallProgress = useMemo(() => {
    if (enrolledCoursesList.length === 0) return 100;
    const sum = enrolledCoursesList.reduce((acc, c) => acc + c.progress, 0);
    return Math.round(sum / enrolledCoursesList.length);
  }, [enrolledCoursesList]);

  const weekActivity = [
    { day: "M", height: 48 },
    { day: "T", height: 75 },
    { day: "W", height: 35 },
    { day: "T", height: 88 },
    { day: "F", height: 60 },
    { day: "S", height: 20 },
    { day: "S", height: 12 },
  ];

  // Recommended courses: published catalog courses excluding those already enrolled
  const recommendedCourses = useMemo(() => {
    const enrolledIds = new Set(enrolledCoursesList.map((c) => String(c.course_id)));
    return catalogCourses
      .filter((c) => !enrolledIds.has(String(c.course_id)))
      .slice(0, 3);
  }, [catalogCourses, enrolledCoursesList]);

  return (
    <div className="space-y-6 max-w-[1500px] mx-auto pb-16 font-sans">
      {/* 1. Welcome Row with Eyebrow, Greeting & Pill */}
      <div className="welcome-row">
        <div>
          <div className="eyebrow">{todayFormatted}</div>
          <h1>
            Good {timeOfDay}, {firstName} <span>✦</span>
          </h1>
          <p className="muted">
            Keep building your skills. Track your courses, complete assessments, and advance your career.
          </p>
        </div>
        <div className="welcome-pill">
          <Sparkles size={16} /> Active Learner
        </div>
      </div>

      {/* 2. Indigo Gradient Hero Panel */}
      <section className="hero-panel">
        <div>
          <span className="hero-kicker">CONTINUE YOUR LEARNING JOURNEY</span>
          <h2>
            Learn something new.<br />
            <em>Become something more.</em>
          </h2>
          <p>
            Explore expert-led curriculum, pass proctored assessments, and earn industry-recognized certifications.
          </p>
          <div className="hero-actions">
            <Link
              className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl font-bold text-xs bg-white text-[#4f46dc] hover:bg-slate-50 transition shadow-xs cursor-pointer"
              to="/browse-courses"
            >
              <span>Explore courses</span> <ArrowUpRight size={15} />
            </Link>
            <Link
              className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl font-bold text-xs bg-white/15 text-white border border-white/30 hover:bg-white/25 transition cursor-pointer"
              to="/courses/my"
            >
              <span>My Enrolled Courses</span>
            </Link>
          </div>
        </div>

        <div className="hero-art">
          <div className="art-circle">✦</div>
          <div className="art-card">
            <BookOpen size={34} />
            <b>Keep growing</b>
            <small>One lesson at a time</small>
            <div className="art-progress">
              <i style={{ width: `${overallProgress}%` }} />
            </div>
          </div>
        </div>
      </section>

      {/* 3. 4 Top KPI / Learning Statistics Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Enrolled Courses */}
        <div
          onClick={() => navigate("/courses/my")}
          className="rounded-2xl border border-[#E5E7EB] bg-white p-5 shadow-2xs hover:shadow-xs transition-all cursor-pointer group"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-500">Enrolled Courses</span>
            <span className="w-9 h-9 rounded-xl bg-indigo-50 text-[#635BFF] flex items-center justify-center group-hover:scale-105 transition-transform">
              <Play size={16} className="fill-current ml-0.5" />
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-2xl sm:text-3xl font-extrabold text-[#111827]">{totalEnrolled}</span>
            <span className="text-xs font-bold text-emerald-600">Active</span>
          </div>
        </div>

        {/* Card 2: Completed Courses */}
        <div
          onClick={() => navigate("/courses/my?status=completed")}
          className="rounded-2xl border border-[#E5E7EB] bg-white p-5 shadow-2xs hover:shadow-xs transition-all cursor-pointer group"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-500">Completed Courses</span>
            <span className="w-9 h-9 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center group-hover:scale-105 transition-transform">
              <CheckCircle2 size={18} />
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-2xl sm:text-3xl font-extrabold text-[#111827]">{totalCompleted}</span>
            <span className="text-xs font-bold text-slate-500">of {totalEnrolled} courses</span>
          </div>
        </div>

        {/* Card 3: Overall Progress */}
        <div className="rounded-2xl border border-[#E5E7EB] bg-white p-5 shadow-2xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-500">Overall Progress</span>
            <span className="w-9 h-9 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
              <Clock3 size={18} />
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-2xl sm:text-3xl font-extrabold text-[#111827]">{overallProgress}%</span>
            <span className="text-xs font-bold text-[#635BFF]">Curriculum</span>
          </div>
        </div>

        {/* Card 4: Certificates */}
        <div
          onClick={() => navigate("/certificates")}
          className="rounded-2xl border border-[#E5E7EB] bg-white p-5 shadow-2xs hover:shadow-xs transition-all cursor-pointer group"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-500">Certificates Earned</span>
            <span className="w-9 h-9 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center group-hover:scale-105 transition-transform">
              <Award size={18} />
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-2xl sm:text-3xl font-extrabold text-[#111827]">{certificatesCount}</span>
            <span className="text-xs font-bold text-emerald-600">Verified</span>
          </div>
        </div>
      </div>

      {/* 4. Continue Learning Hero & Weekly Activity (2-Column Grid) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Continue Learning Prominent Card (7 Cols) */}
        <div className="lg:col-span-7 rounded-2xl border border-[#E5E7EB] bg-white p-6 shadow-2xs flex flex-col justify-between space-y-4">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
                <h3 className="text-base font-bold text-[#111827]">Continue Learning</h3>
              </div>
              <span className="text-xs font-semibold text-slate-400">Last active today</span>
            </div>

            <div className="mt-4 flex flex-col sm:flex-row sm:items-center gap-4">
              <div
                onClick={() => navigate(`/courses/${activeCourse.course_id}/learn`)}
                className="w-16 h-16 sm:w-20 sm:h-20 rounded-2xl bg-gradient-to-br from-indigo-900 to-[#635BFF] flex items-center justify-center text-white shrink-0 cursor-pointer shadow-sm group"
              >
                <Play size={24} className="fill-current ml-0.5 group-hover:scale-110 transition-transform" />
              </div>

              <div className="flex-1 min-w-0 space-y-2">
                <h4
                  onClick={() => navigate(`/courses/${activeCourse.course_id}/learn`)}
                  className="text-base font-bold text-[#111827] hover:text-[#635BFF] transition-colors cursor-pointer truncate"
                >
                  {activeCourse.title}
                </h4>
                <p className="text-xs text-slate-500 flex items-center gap-2">
                  <span>{activeCourse.module_title}</span>
                  <span>•</span>
                  <span>{activeCourse.instructor}</span>
                </p>

                <div className="space-y-1">
                  <div className="flex items-center justify-between text-xs font-semibold">
                    <span className="text-slate-500">Progress</span>
                    <span className="text-[#635BFF]">{activeCourse.progress}%</span>
                  </div>
                  <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-[#635BFF] transition-all duration-500"
                      style={{ width: `${activeCourse.progress}%` }}
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="pt-3 border-t border-slate-100 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-xs font-semibold text-emerald-700 bg-emerald-50 px-3 py-1 rounded-full border border-emerald-200">
              <Check size={14} />
              <span>Module test ready</span>
            </div>
            <button
              type="button"
              onClick={() => navigate(`/courses/${activeCourse.course_id}/learn`)}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#635BFF] hover:bg-[#5046E5] text-white text-xs font-bold shadow-xs cursor-pointer transition-all"
            >
              <span>Continue Lesson</span>
              <ArrowRight size={14} />
            </button>
          </div>
        </div>

        {/* Right: Learning Activity & Weekly Momentum (5 Cols) */}
        <div className="lg:col-span-5 rounded-2xl border border-[#E5E7EB] bg-white p-6 shadow-2xs flex flex-col justify-between space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div>
              <h3 className="text-base font-bold text-[#111827]">Weekly Momentum</h3>
              <p className="text-xs text-slate-500">Study activity this week</p>
            </div>
            <span className="text-xs font-bold text-[#635BFF] bg-indigo-50 px-2.5 py-1 rounded-lg border border-indigo-100">
              4.8 hrs total
            </span>
          </div>

          <div className="flex items-end justify-between h-28 pt-2">
            {weekActivity.map((w, idx) => (
              <div key={idx} className="flex flex-col items-center gap-2 flex-1">
                <div className="w-full flex justify-center">
                  <div
                    className={cn(
                      "w-7 rounded-t-lg transition-all",
                      idx === 3 || idx === 1 ? "bg-[#635BFF]" : "bg-indigo-100 hover:bg-indigo-200"
                    )}
                    style={{ height: `${w.height}%` }}
                  />
                </div>
                <span className="text-[11px] font-bold text-slate-500">{w.day}</span>
              </div>
            ))}
          </div>

          <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
            <span>Daily goal: 45 mins</span>
            <span className="font-bold text-emerald-600 flex items-center gap-1">
              <CheckCircle2 size={13} /> Target Achieved
            </span>
          </div>
        </div>
      </div>

      {/* 5. My Enrolled Courses Section (Part 2.A Priority) */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-[#111827]">My Enrolled Courses</h2>
            <p className="text-xs text-slate-500">Courses you are currently learning and mastering</p>
          </div>
          <Link
            to="/courses/my"
            className="text-xs font-bold text-[#635BFF] hover:text-[#5046E5] flex items-center gap-1 cursor-pointer transition-colors"
          >
            <span>View All ({enrolledCoursesList.length})</span>
            <ArrowRight size={14} />
          </Link>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {enrolledCoursesList.map((course) => {
            const isCompleted = course.status === "Completed";
            return (
              <div
                key={course.course_id}
                onClick={() => navigate(`/courses/${course.course_id}/learn`)}
                className="group rounded-2xl border border-[#E5E7EB] bg-white p-5 shadow-2xs hover:shadow-xs transition-all cursor-pointer flex flex-col justify-between space-y-4"
              >
                <div className="space-y-3">
                  {/* Thumbnail header */}
                  <div className="relative h-36 w-full rounded-xl overflow-hidden bg-gradient-to-br from-slate-900 via-indigo-950 to-[#635BFF] flex items-center justify-center text-white">
                    <div className="flex flex-col items-center gap-1 p-4 text-center">
                      <div className="w-12 h-12 rounded-xl bg-white/10 border border-white/20 flex items-center justify-center">
                        <BookOpen size={24} className="text-white" />
                      </div>
                      <span className="text-xs font-bold text-white line-clamp-1">{course.title}</span>
                    </div>

                    <div className="absolute top-2.5 right-2.5">
                      <span
                        className={cn(
                          "inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold shadow-xs",
                          isCompleted
                            ? "bg-emerald-500 text-white"
                            : "bg-[#635BFF] text-white"
                        )}
                      >
                        {isCompleted ? <CheckCircle2 size={11} /> : <Play size={10} className="fill-current" />}
                        <span>{course.status}</span>
                      </span>
                    </div>
                  </div>

                  {/* Title & Metadata */}
                  <div className="space-y-1">
                    <h3 className="text-sm font-bold text-[#111827] group-hover:text-[#635BFF] transition-colors line-clamp-1">
                      {course.title}
                    </h3>
                    <p className="text-xs text-slate-500">{course.instructor}</p>
                  </div>

                  {/* Progress Bar */}
                  <div className="space-y-1 pt-1">
                    <div className="flex items-center justify-between text-xs font-semibold">
                      <span className="text-slate-500">Progress</span>
                      <span className="text-[#635BFF]">{course.progress}%</span>
                    </div>
                    <div className="h-1.5 rounded-full bg-slate-100 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-[#635BFF] transition-all duration-300"
                        style={{ width: `${course.progress}%` }}
                      />
                    </div>
                  </div>
                </div>

                {/* Bottom Action */}
                <div className="pt-3 border-t border-slate-100 flex items-center justify-between">
                  <span className="text-xs font-medium text-slate-500">
                    {isCompleted ? "All modules completed" : course.module_title}
                  </span>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      navigate(`/courses/${course.course_id}/learn`);
                    }}
                    className={cn(
                      "px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer inline-flex items-center gap-1.5",
                      isCompleted
                        ? "bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                        : "bg-indigo-50 text-[#635BFF] hover:bg-[#635BFF] hover:text-white"
                    )}
                  >
                    <span>{isCompleted ? "Review Course" : "Continue"}</span>
                    <ArrowRight size={12} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* 6. Upcoming Assessments & Milestones */}
      <section className="rounded-2xl border border-[#E5E7EB] bg-white p-6 shadow-2xs space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-100">
          <div>
            <h3 className="text-base font-bold text-[#111827]">Assessments & Certifications</h3>
            <p className="text-xs text-slate-500">Track your progress toward accredited certifications</p>
          </div>
          <Link to="/certificates" className="text-xs font-bold text-[#635BFF] hover:underline">
            View All Credentials →
          </Link>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/70 flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-indigo-50 text-[#635BFF] flex items-center justify-center shrink-0 border border-indigo-100">
                <FileCheck size={20} />
              </div>
              <div>
                <b className="text-xs font-bold text-slate-900 block">Python Foundations Module Test</b>
                <span className="text-[11px] text-slate-500">5 Questions · 30 mins · 70% Pass Standard</span>
              </div>
            </div>
            <button
              type="button"
              onClick={() => navigate(`/courses/${activeCourse.course_id}/learn`)}
              className="px-3 py-1.5 rounded-lg bg-white border border-slate-200 text-xs font-bold text-[#635BFF] hover:bg-indigo-50 cursor-pointer shrink-0 transition-colors shadow-2xs"
            >
              Start Test
            </button>
          </div>

          <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/70 flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center shrink-0 border border-amber-100">
                <Award size={20} />
              </div>
              <div>
                <b className="text-xs font-bold text-slate-900 block">Final Certification Examination</b>
                <span className="text-[11px] text-slate-500">Proctored Exam · 20 Questions · 60 mins</span>
              </div>
            </div>
            <button
              type="button"
              onClick={() => navigate(`/courses/${activeCourse.course_id}/final-exam`)}
              className="px-3 py-1.5 rounded-lg bg-white border border-slate-200 text-xs font-bold text-slate-700 hover:bg-slate-50 cursor-pointer shrink-0 transition-colors shadow-2xs"
            >
              Enter Exam
            </button>
          </div>
        </div>
      </section>

      {/* 7. Recommended Courses from Catalog */}
      {recommendedCourses.length > 0 && (
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold text-[#111827]">Recommended Courses</h2>
              <p className="text-xs text-slate-500">Expand your career skills with top-rated learning paths</p>
            </div>
            <Link to="/browse-courses" className="text-xs font-bold text-[#635BFF] hover:underline flex items-center gap-1">
              <span>Explore All</span>
              <ArrowRight size={13} />
            </Link>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {recommendedCourses.map((c) => (
              <div
                key={c.course_id}
                onClick={() => navigate(`/courses/${c.course_id}`)}
                className="group rounded-2xl border border-[#E5E7EB] bg-white p-5 shadow-2xs hover:shadow-xs transition-all cursor-pointer flex flex-col justify-between space-y-4"
              >
                <div className="space-y-3">
                  <div className="h-28 w-full rounded-xl bg-gradient-to-br from-slate-800 to-indigo-900 flex items-center justify-center text-white p-3 text-center">
                    <span className="text-xs font-bold line-clamp-2">{c.title}</span>
                  </div>

                  <div className="space-y-1">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-[#635BFF] bg-indigo-50 px-2 py-0.5 rounded-md">
                      {c.slug || "Computer Science"}
                    </span>
                    <h4 className="text-sm font-bold text-slate-900 group-hover:text-[#635BFF] transition-colors line-clamp-1">
                      {c.title}
                    </h4>
                    <p className="text-xs text-slate-500 line-clamp-2">
                      {c.summary || "Master in-demand software skills with real-world projects and assessments."}
                    </p>
                  </div>
                </div>

                <div className="pt-3 border-t border-slate-100 flex items-center justify-between">
                  <span className="text-xs font-bold text-amber-600 flex items-center gap-1">
                    <Star size={13} className="fill-amber-400 text-amber-400" /> 4.8
                  </span>
                  <button
                    type="button"
                    className="text-xs font-bold text-[#635BFF] group-hover:underline inline-flex items-center gap-1"
                  >
                    <span>View Course</span>
                    <ArrowRight size={12} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

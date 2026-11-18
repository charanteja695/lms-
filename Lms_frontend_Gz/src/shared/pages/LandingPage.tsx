import { useNavigate } from "react-router-dom";
import { Brand } from "@/shared/layout/Brand";
import { Icon } from "@/shared/ui";
import { useListCoursesQuery } from "@/modules/catalog/courses/api/coursesApi";
import { useListInstitutionsQuery } from "@/modules/user-management/institutions/api/institutionsApi";
import { useListUsersQuery } from "@/modules/user-management/users/api/usersApi";

export function LandingPage() {
  const navigate = useNavigate();

  const { data: coursesData } = useListCoursesQuery({ per_page: 4 });
  const { data: instData } = useListInstitutionsQuery({ per_page: 1 });
  const { data: studentsData } = useListUsersQuery({ role: "student", per_page: 1 });

  const totalCourses = coursesData?.pageContext?.total_records ?? 25;
  const totalStudents = studentsData?.pageContext?.total_records ?? 1250;
  const totalInstitutions = instData?.pageContext?.total_records ?? 12;

  const popularCourses = [
    {
      id: "1",
      title: "Python Programming & Data Structures",
      instructor: "DataTech Academy",
      category: "Programming",
      duration: "42 Hours",
      rating: "4.8",
      reviews: "12.5k",
      price: "₹999",
      tag: "Best Seller",
      badgeBg: "bg-blue-600 text-white",
      iconBg: "bg-blue-50 text-brand-600",
    },
    {
      id: "2",
      title: "Full Stack Web Development (React & Node)",
      instructor: "Tech Masters",
      category: "Web Development",
      duration: "58 Hours",
      rating: "4.9",
      reviews: "8.2k",
      price: "₹1,299",
      tag: "Popular",
      badgeBg: "bg-emerald-600 text-white",
      iconBg: "bg-emerald-50 text-emerald-600",
    },
    {
      id: "3",
      title: "Machine Learning & AI Foundations",
      instructor: "Future Labs",
      category: "AI & ML",
      duration: "36 Hours",
      rating: "4.7",
      reviews: "6.7k",
      price: "₹1,499",
      tag: "Trending",
      badgeBg: "bg-purple-600 text-white",
      iconBg: "bg-purple-50 text-purple-600",
    },
    {
      id: "4",
      title: "Cloud Computing & DevOps Masterclass",
      instructor: "CloudTech Systems",
      category: "Cloud",
      duration: "30 Hours",
      rating: "4.8",
      reviews: "4.9k",
      price: "₹1,199",
      tag: "Featured",
      badgeBg: "bg-amber-600 text-white",
      iconBg: "bg-amber-50 text-amber-600",
    },
  ];

  return (
    <div className="min-h-screen bg-[#F3F6FC] flex flex-col font-sans text-navy-950">
      {/* =========================================================================
          A. HEADER
          ========================================================================= */}
      <header className="sticky top-0 z-30 flex h-20 items-center justify-between border-b border-[#E4EAF5] bg-white/95 px-6 backdrop-blur-md lg:px-12">
        <div className="flex items-center gap-10">
          <Brand />
          <nav className="hidden md:flex items-center gap-6 text-sm font-semibold text-slate-600" aria-label="Main Navigation">
            <a href="#" className="text-brand-600 font-bold">Home</a>
            <button onClick={() => navigate("/browse-courses")} className="hover:text-navy-950 transition-colors cursor-pointer">Courses</button>
            <a href="#institutions" className="hover:text-navy-950 transition-colors">For Institutions</a>
            <button onClick={() => navigate("/career")} className="hover:text-navy-950 transition-colors cursor-pointer">Career</button>
            <a href="#about" className="hover:text-navy-950 transition-colors">About Us</a>
            <a href="#contact" className="hover:text-navy-950 transition-colors">Contact</a>
          </nav>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => navigate("/login")}
            className="rounded-xl px-4 py-2 text-sm font-semibold text-slate-700 hover:text-navy-950 transition-colors cursor-pointer"
          >
            Login
          </button>
          <button
            type="button"
            onClick={() => navigate("/register")}
            className="rounded-xl bg-brand-600 px-5 py-2.5 text-sm font-bold text-white shadow-md hover:bg-brand-700 transition-all cursor-pointer active:scale-95"
          >
            Get Started
          </button>
        </div>
      </header>

      {/* =========================================================================
          B. HERO SECTION
          ========================================================================= */}
      <section className="relative px-6 py-14 lg:px-12 lg:py-20 max-w-7xl mx-auto w-full">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
          <div className="lg:col-span-7">
            <div className="inline-flex items-center gap-2 rounded-full bg-blue-50 px-3.5 py-1.5 text-xs font-bold text-brand-700 border border-blue-100 mb-6 shadow-2xs">
              <span className="text-sm">⚡</span> Enterprise Learning Platform
            </div>

            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold text-navy-950 tracking-tight leading-[1.12]">
              Learn Today. <br />
              <span className="bg-gradient-to-r from-brand-600 to-indigo-600 bg-clip-text text-transparent">Lead Tomorrow.</span>
            </h1>

            <p className="mt-5 text-base sm:text-lg text-slate-600 leading-relaxed max-w-xl">
              Build practical skills, master new technologies and accelerate your career with ExamLMS. 
              Comprehensive learning, proctored assessments, and recognized certificates.
            </p>

            <div className="mt-8 flex flex-wrap items-center gap-4">
              <button
                type="button"
                onClick={() => navigate("/browse-courses")}
                className="inline-flex items-center gap-2 rounded-xl bg-brand-600 px-6 py-3.5 text-sm font-bold text-white shadow-md hover:bg-brand-700 transition-all cursor-pointer active:scale-95"
              >
                Explore Courses <Icon name="arrowRight" size={16} />
              </button>
              <button
                type="button"
                onClick={() => navigate("/register")}
                className="inline-flex items-center gap-2 rounded-xl border border-slate-200/90 bg-white px-6 py-3.5 text-sm font-bold text-navy-950 hover:bg-slate-50 transition-all cursor-pointer shadow-xs active:scale-95"
              >
                Get Started Free
              </button>
            </div>

            {/* Social Trust Metrics */}
            <div className="mt-10 flex items-center gap-4">
              <div className="flex -space-x-2">
                {["DS", "RK", "AM", "SR"].map((init, i) => (
                  <div
                    key={i}
                    className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-tr from-brand-700 to-blue-500 border-2 border-white text-xs font-bold text-white shadow-xs"
                  >
                    {init}
                  </div>
                ))}
              </div>
              <div>
                <div className="flex items-center text-amber-500 text-sm font-bold">
                  {"★".repeat(5)} <span className="ml-1.5 text-xs text-navy-950 font-bold">4.9 / 5.0</span>
                </div>
                <p className="text-xs text-slate-500 font-medium">Over 50,000+ satisfied learners</p>
              </div>
            </div>
          </div>

          {/* Educational 3D Hero Graphic Container */}
          <div className="lg:col-span-5 relative">
            <div className="rounded-3xl bg-gradient-to-tr from-[#1D4ED8] via-[#2563EB] to-[#3B82F6] p-8 text-white shadow-lift relative overflow-hidden">
              <div className="pointer-events-none absolute -right-10 -bottom-10 h-48 w-48 rounded-full bg-white/10 blur-2xl" />
              
              <div className="text-center py-6">
                <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-white/20 backdrop-blur-md mb-4 shadow-sm">
                  <Icon name="graduation" size={32} className="text-white" />
                </div>
                <h3 className="text-xl font-bold">Interactive Learning Hub</h3>
                <p className="text-xs text-blue-100 mt-1 max-w-xs mx-auto">
                  High-definition video lectures, interactive modules, instant coding execution and verified proctored examinations.
                </p>
              </div>

              {/* Floating Stat Card 1 */}
              <div className="mt-4 rounded-2xl bg-white/95 backdrop-blur-md p-3.5 text-navy-950 shadow-md flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-50 text-brand-600">
                    <Icon name="book" size={18} />
                  </span>
                  <div>
                    <p className="text-xs font-bold">Industry Curriculum</p>
                    <p className="text-[10px] text-slate-500">Curated by top tech leads</p>
                  </div>
                </div>
                <span className="text-xs font-bold text-emerald-600">Updated</span>
              </div>

              {/* Floating Stat Card 2 */}
              <div className="mt-3 rounded-2xl bg-white/95 backdrop-blur-md p-3.5 text-navy-950 shadow-md flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-purple-50 text-purple-600">
                    <Icon name="award" size={18} />
                  </span>
                  <div>
                    <p className="text-xs font-bold">ISO-Compliant Certificates</p>
                    <p className="text-[10px] text-slate-500">Globally verifiable credentials</p>
                  </div>
                </div>
                <span className="text-xs font-bold text-brand-600">100% Valid</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* =========================================================================
          C. TRUST SECTION (Real Platform Statistics)
          ========================================================================= */}
      <section className="bg-white border-y border-[#E4EAF5] py-12 px-6 lg:px-12">
        <div className="max-w-7xl mx-auto grid grid-cols-2 lg:grid-cols-4 gap-6 text-center">
          <div className="p-4">
            <p className="text-3xl sm:text-4xl font-extrabold text-navy-950 tracking-tight">{totalCourses}+</p>
            <p className="text-xs sm:text-sm font-semibold text-slate-500 mt-1">Active Courses</p>
          </div>
          <div className="p-4">
            <p className="text-3xl sm:text-4xl font-extrabold text-navy-950 tracking-tight">{totalStudents.toLocaleString()}+</p>
            <p className="text-xs sm:text-sm font-semibold text-slate-500 mt-1">Enrolled Students</p>
          </div>
          <div className="p-4">
            <p className="text-3xl sm:text-4xl font-extrabold text-navy-950 tracking-tight">{totalInstitutions}+</p>
            <p className="text-xs sm:text-sm font-semibold text-slate-500 mt-1">Partner Institutions</p>
          </div>
          <div className="p-4">
            <p className="text-3xl sm:text-4xl font-extrabold text-navy-950 tracking-tight">125,000+</p>
            <p className="text-xs sm:text-sm font-semibold text-slate-500 mt-1">Learning Hours Completed</p>
          </div>
        </div>
      </section>

      {/* =========================================================================
          D. POPULAR COURSES
          ========================================================================= */}
      <section className="py-16 px-6 lg:px-12 max-w-7xl mx-auto w-full">
        <div className="flex items-center justify-between mb-8">
          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-brand-600">Top Picks</p>
            <h2 className="text-2xl sm:text-3xl font-extrabold text-navy-950 tracking-tight mt-1">
              Popular Courses
            </h2>
          </div>
          <button
            type="button"
            onClick={() => navigate("/browse-courses")}
            className="text-xs sm:text-sm font-bold text-brand-600 hover:text-brand-700 flex items-center gap-1 cursor-pointer"
          >
            View All Courses <Icon name="arrowRight" size={14} />
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {popularCourses.map((c) => (
            <div
              key={c.id}
              onClick={() => navigate("/browse-courses")}
              className="group cursor-pointer rounded-2xl border border-[#E4EAF5] bg-white p-5 shadow-card transition-all hover:shadow-lift hover:border-brand-200 flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between mb-3">
                  <span className={`rounded-md px-2 py-0.5 text-[10px] font-bold ${c.badgeBg}`}>
                    {c.tag}
                  </span>
                  <span className="text-[11px] font-semibold text-slate-400">{c.category}</span>
                </div>

                <div className={`flex h-12 w-12 items-center justify-center rounded-xl mb-4 ${c.iconBg}`}>
                  <Icon name="book" size={24} />
                </div>

                <h3 className="text-base font-bold text-navy-950 group-hover:text-brand-600 transition-colors line-clamp-2">
                  {c.title}
                </h3>
                <p className="mt-1 text-xs text-slate-500 font-medium">{c.instructor}</p>
                <p className="mt-1 text-xs text-slate-400 font-medium flex items-center gap-1">
                  <Icon name="clock" size={12} /> {c.duration}
                </p>
              </div>

              <div className="mt-5 flex items-center justify-between pt-3 border-t border-slate-100">
                <div className="flex items-center gap-1 text-xs font-bold text-slate-700">
                  <span className="text-amber-500">★</span> {c.rating}
                  <span className="text-[10px] font-normal text-slate-400">({c.reviews})</span>
                </div>
                <span className="text-base font-extrabold text-navy-950">{c.price}</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* =========================================================================
          E. WHY EXAMLMS
          ========================================================================= */}
      <section className="bg-white py-16 px-6 lg:px-12 border-y border-[#E4EAF5]">
        <div className="max-w-7xl mx-auto">
          <div className="text-center max-w-2xl mx-auto mb-12">
            <p className="text-xs font-bold uppercase tracking-wider text-brand-600">The Modern LMS Advantage</p>
            <h2 className="text-2xl sm:text-3xl font-extrabold text-navy-950 tracking-tight mt-1">
              Why Learn with ExamLMS?
            </h2>
            <p className="text-sm text-slate-500 mt-2">
              Engineered for both ambitious individual students and progressive academic institutions.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              { title: "Structured Learning", desc: "Modular curricula with video, PDF resources, chapter quizzes, and comprehensive module tests.", icon: "layers" as const, color: "bg-blue-50 text-brand-600" },
              { title: "Practical Assessments", desc: "Automated grading, proctored AI evaluation, anti-cheat detection, and detailed performance analytics.", icon: "clipboardCheck" as const, color: "bg-emerald-50 text-emerald-600" },
              { title: "Progress Tracking", desc: "Granular streak milestones, completion bars, module checkpoint tracking, and personalized dashboards.", icon: "chart" as const, color: "bg-purple-50 text-purple-600" },
              { title: "Verifiable Certificates", desc: "Automated credential generation with tamper-proof verification IDs and LinkedIn sharing.", icon: "award" as const, color: "bg-amber-50 text-amber-600" },
              { title: "Institutional Learning", desc: "Bulk purchasing, quota allocation, batch management, student performance monitoring and faculty controls.", icon: "building" as const, color: "bg-teal-50 text-teal-600" },
              { title: "Career Development", desc: "Integrated placement boards, employer partnerships, resume building tools and mock AI interviews.", icon: "briefcase" as const, color: "bg-indigo-50 text-indigo-600" },
            ].map((f) => (
              <div key={f.title} className="rounded-2xl border border-slate-100 bg-[#F8FAFC] p-6 shadow-2xs hover:shadow-card transition-all">
                <span className={`flex h-12 w-12 items-center justify-center rounded-xl ${f.color} mb-4 shadow-2xs`}>
                  <Icon name={f.icon} size={22} />
                </span>
                <h3 className="text-base font-bold text-navy-950">{f.title}</h3>
                <p className="mt-2 text-xs sm:text-sm text-slate-500 leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* =========================================================================
          F. INSTITUTION SECTION
          ========================================================================= */}
      <section id="institutions" className="py-16 px-6 lg:px-12 max-w-7xl mx-auto w-full">
        <div className="rounded-3xl bg-gradient-to-r from-[#0B1836] via-[#10234B] to-[#1E3A8A] p-8 sm:p-12 text-white shadow-lift relative overflow-hidden">
          <div className="pointer-events-none absolute right-0 top-0 h-64 w-64 rounded-full bg-blue-500/10 blur-3xl" />

          <div className="max-w-2xl relative z-10">
            <span className="rounded-full bg-blue-500/20 px-3 py-1 text-xs font-bold text-cyan-300 border border-blue-400/30">
              For Colleges & Universities
            </span>
            <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight mt-4 leading-tight">
              Empower Your Institution with ExamLMS
            </h2>
            <p className="mt-3 text-sm sm:text-base text-slate-300 leading-relaxed">
              Equip your faculty and departments with state-of-the-art course management, bulk student enrollments, 
              custom academic batches, and enterprise-grade performance dashboards.
            </p>

            <ul className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs sm:text-sm font-semibold text-slate-200">
              <li className="flex items-center gap-2"><Icon name="checkCircle" size={16} className="text-cyan-400" /> Manage students & staff centrally</li>
              <li className="flex items-center gap-2"><Icon name="checkCircle" size={16} className="text-cyan-400" /> Purchase courses in bulk with quotation workflows</li>
              <li className="flex items-center gap-2"><Icon name="checkCircle" size={16} className="text-cyan-400" /> Track cohort academic performance</li>
              <li className="flex items-center gap-2"><Icon name="checkCircle" size={16} className="text-cyan-400" /> Export institutional audit & grading reports</li>
            </ul>

            <div className="mt-8">
              <button
                type="button"
                onClick={() => navigate("/login")}
                className="rounded-xl bg-brand-600 px-6 py-3 text-sm font-bold text-white shadow-md hover:bg-brand-500 transition-all cursor-pointer active:scale-95"
              >
                Explore Institutional Solutions →
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* =========================================================================
          I. FOOTER
          ========================================================================= */}
      <footer className="mt-auto border-t border-[#E4EAF5] bg-white py-12 px-6 lg:px-12 text-xs text-slate-500">
        <div className="max-w-7xl mx-auto grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-8 mb-10">
          <div className="col-span-2">
            <Brand />
            <p className="mt-3 text-xs text-slate-500 max-w-sm leading-relaxed">
              ExamLMS is the premier unified learning management platform designed for students, educators, and institutions.
            </p>
          </div>

          <div>
            <h4 className="font-bold text-navy-950 uppercase text-[11px] tracking-wider mb-3">Courses</h4>
            <ul className="space-y-2">
              <li><button onClick={() => navigate("/browse-courses")} className="hover:text-navy-950 transition-colors">Programming</button></li>
              <li><button onClick={() => navigate("/browse-courses")} className="hover:text-navy-950 transition-colors">Data Science</button></li>
              <li><button onClick={() => navigate("/browse-courses")} className="hover:text-navy-950 transition-colors">AI & Robotics</button></li>
              <li><button onClick={() => navigate("/browse-courses")} className="hover:text-navy-950 transition-colors">Cloud & DevOps</button></li>
            </ul>
          </div>

          <div>
            <h4 className="font-bold text-navy-950 uppercase text-[11px] tracking-wider mb-3">Institutions</h4>
            <ul className="space-y-2">
              <li><a href="#institutions" className="hover:text-navy-950 transition-colors">Bulk Purchasing</a></li>
              <li><a href="#institutions" className="hover:text-navy-950 transition-colors">Batch Management</a></li>
              <li><a href="#institutions" className="hover:text-navy-950 transition-colors">Quota Calculator</a></li>
              <li><a href="#institutions" className="hover:text-navy-950 transition-colors">Accreditation</a></li>
            </ul>
          </div>

          <div>
            <h4 className="font-bold text-navy-950 uppercase text-[11px] tracking-wider mb-3">Company</h4>
            <ul className="space-y-2">
              <li><a href="#about" className="hover:text-navy-950 transition-colors">About Us</a></li>
              <li><button onClick={() => navigate("/career")} className="hover:text-navy-950 transition-colors">Careers</button></li>
              <li><a href="#contact" className="hover:text-navy-950 transition-colors">Contact</a></li>
              <li><a href="#privacy" className="hover:text-navy-950 transition-colors">Privacy Policy</a></li>
            </ul>
          </div>

          <div>
            <h4 className="font-bold text-navy-950 uppercase text-[11px] tracking-wider mb-3">Connect</h4>
            <ul className="space-y-2">
              <li><a href="#" className="hover:text-navy-950 transition-colors">LinkedIn</a></li>
              <li><a href="#" className="hover:text-navy-950 transition-colors">Twitter / X</a></li>
              <li><a href="#" className="hover:text-navy-950 transition-colors">GitHub</a></li>
              <li><a href="#" className="hover:text-navy-950 transition-colors">YouTube</a></li>
            </ul>
          </div>
        </div>

        <div className="max-w-7xl mx-auto border-t border-slate-100 pt-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <p>© {new Date().getFullYear()} ExamLMS. All rights reserved. GenZ Technologies.</p>
          <div className="flex items-center gap-6">
            <a href="#terms" className="hover:text-navy-950 transition-colors">Terms of Service</a>
            <a href="#privacy" className="hover:text-navy-950 transition-colors">Privacy Policy</a>
            <a href="#security" className="hover:text-navy-950 transition-colors">Security</a>
          </div>
        </div>
      </footer>
    </div>
  );
}

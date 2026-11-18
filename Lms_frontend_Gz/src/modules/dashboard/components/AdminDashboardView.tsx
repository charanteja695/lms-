import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  BookOpen,
  CheckCircle2,
  Users,
  Building2,
  Plus,
  ArrowRight,
  TrendingUp,
  FileCheck,
  CreditCard,
  GraduationCap,
  Briefcase,
  FileText,
  BarChart3,
  Layers,
} from "lucide-react";
import { useListCoursesQuery } from "@/modules/catalog/courses/api/coursesApi";
import { useListInstitutionsQuery } from "@/modules/user-management/institutions/api/institutionsApi";
import { useListUsersQuery } from "@/modules/user-management/users/api/usersApi";
import { useGetAdminInstitutionalRequestsQuery } from "@/modules/billing/institutional/api/institutionalApi";
import { useListEnrollmentsQuery } from "@/modules/learning/enrollments/api/enrollmentsApi";


export function AdminDashboardView() {
  const navigate = useNavigate();
  const [timeRange, setTimeRange] = useState("Last 30 days");

  // Real backend queries
  const { data: coursesData } = useListCoursesQuery({ per_page: 50, include_archived: false });
  const { data: instData } = useListInstitutionsQuery({ per_page: 50 });
  const { data: studentsData } = useListUsersQuery({ role: "student", per_page: 50 });
  const { data: staffData } = useListUsersQuery({ role: "staff", per_page: 50 });
  const { data: enrollmentsData } = useListEnrollmentsQuery({ per_page: 50 });
  const { data: requestsData = [] } = useGetAdminInstitutionalRequestsQuery();

  const courses = coursesData?.items ?? [];
  const totalCourses = coursesData?.pageContext?.total_records ?? courses.length;
  const publishedCourses = useMemo(() => {
    return courses.filter((c) => c.versions?.some((v) => v.status === "published")).length;
  }, [courses]);
  const draftCourses = Math.max(0, totalCourses - publishedCourses);

  const totalStudents = studentsData?.pageContext?.total_records ?? studentsData?.items?.length ?? 0;
  const totalInstitutions = instData?.pageContext?.total_records ?? instData?.items?.length ?? 0;
  const totalStaff = staffData?.pageContext?.total_records ?? staffData?.items?.length ?? 0;
  const activeEnrollments = enrollmentsData?.pageContext?.total_records ?? enrollmentsData?.items?.length ?? 0;
  const pendingRequestsCount = requestsData.length;

  const chartHeights = [35, 44, 40, 53, 60, 51, 69, 75, 66, 83, 91, 98];

  return (
    <div className="space-y-6 max-w-[1600px] mx-auto pb-16 font-sans">
      {/* 1. Header with Eyebrow, Title & Actions */}
      <div className="page-head">
        <div>
          <h1>Admin Dashboard</h1>
        </div>
        <div className="head-actions">
          <div className="relative inline-flex items-center">
            <select
              value={timeRange}
              onChange={(e) => setTimeRange(e.target.value)}
              className="inline-flex items-center gap-2 rounded-xl border border-[#E5E7EB] bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 shadow-2xs hover:bg-slate-50 transition cursor-pointer focus:outline-none"
            >
              <option value="Last 7 days">Last 7 days</option>
              <option value="Last 30 days">Last 30 days</option>
              <option value="This Quarter">This Quarter</option>
              <option value="All Time">All Time</option>
            </select>
          </div>
          <button
            type="button"
            onClick={() => navigate("/courses/create")}
            className="inline-flex items-center gap-1.5 rounded-xl bg-[#635BFF] px-4 py-2 text-xs font-bold text-white shadow-xs hover:bg-[#5046E5] transition cursor-pointer"
          >
            <Plus size={15} />
            <span>Create Course</span>
          </button>
        </div>
      </div>

      {/* 2. Overview Metrics (8 Cards - Part 3 Specification) */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {/* Total Students */}
        <div
          onClick={() => navigate("/users?role=student")}
          className="rounded-2xl border border-[#E5E7EB] bg-white p-5 shadow-2xs hover:shadow-xs transition-all cursor-pointer group"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-500">Total Students</span>
            <span className="w-9 h-9 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center group-hover:scale-105 transition-transform">
              <Users size={18} />
            </span>
          </div>
          <p className="mt-3 text-2xl font-extrabold text-[#111827]">{totalStudents.toLocaleString()}</p>
          <div className="mt-1 text-[11px] font-semibold text-emerald-600">Active learners</div>
        </div>

        {/* Total Institutions */}
        <div
          onClick={() => navigate("/institutions")}
          className="rounded-2xl border border-[#E5E7EB] bg-white p-5 shadow-2xs hover:shadow-xs transition-all cursor-pointer group"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-500">Total Institutions</span>
            <span className="w-9 h-9 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center group-hover:scale-105 transition-transform">
              <Building2 size={18} />
            </span>
          </div>
          <p className="mt-3 text-2xl font-extrabold text-[#111827]">{totalInstitutions}</p>
          <div className="mt-1 text-[11px] font-semibold text-slate-500">Corporate & Academic</div>
        </div>

        {/* Total Staff */}
        <div
          onClick={() => navigate("/users?role=staff")}
          className="rounded-2xl border border-[#E5E7EB] bg-white p-5 shadow-2xs hover:shadow-xs transition-all cursor-pointer group"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-500">Total Staff</span>
            <span className="w-9 h-9 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center group-hover:scale-105 transition-transform">
              <Briefcase size={18} />
            </span>
          </div>
          <p className="mt-3 text-2xl font-extrabold text-[#111827]">{totalStaff}</p>
          <div className="mt-1 text-[11px] font-semibold text-slate-500">Instructors & Evaluators</div>
        </div>

        {/* Total Courses */}
        <div
          onClick={() => navigate("/courses")}
          className="rounded-2xl border border-[#E5E7EB] bg-white p-5 shadow-2xs hover:shadow-xs transition-all cursor-pointer group"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-500">Total Courses</span>
            <span className="w-9 h-9 rounded-xl bg-indigo-50 text-[#635BFF] flex items-center justify-center group-hover:scale-105 transition-transform">
              <BookOpen size={18} />
            </span>
          </div>
          <p className="mt-3 text-2xl font-extrabold text-[#111827]">{totalCourses}</p>
          <div className="mt-1 text-[11px] font-semibold text-slate-500">
            {publishedCourses} published · {draftCourses} draft
          </div>
        </div>

        {/* Published Courses */}
        <div
          onClick={() => navigate("/courses?status=published")}
          className="rounded-2xl border border-[#E5E7EB] bg-white p-5 shadow-2xs hover:shadow-xs transition-all cursor-pointer group"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-500">Published Courses</span>
            <span className="w-9 h-9 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center group-hover:scale-105 transition-transform">
              <CheckCircle2 size={18} />
            </span>
          </div>
          <p className="mt-3 text-2xl font-extrabold text-[#111827]">{publishedCourses}</p>
          <div className="mt-1 text-[11px] font-semibold text-emerald-600">Live in catalog</div>
        </div>

        {/* Draft Courses */}
        <div
          onClick={() => navigate("/courses?status=draft")}
          className="rounded-2xl border border-[#E5E7EB] bg-white p-5 shadow-2xs hover:shadow-xs transition-all cursor-pointer group"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-500">Draft Courses</span>
            <span className="w-9 h-9 rounded-xl bg-slate-100 text-slate-600 flex items-center justify-center group-hover:scale-105 transition-transform">
              <Layers size={18} />
            </span>
          </div>
          <p className="mt-3 text-2xl font-extrabold text-[#111827]">{draftCourses}</p>
          <div className="mt-1 text-[11px] font-semibold text-slate-500">In authoring</div>
        </div>

        {/* Active Enrollments */}
        <div
          onClick={() => navigate("/enrollments")}
          className="rounded-2xl border border-[#E5E7EB] bg-white p-5 shadow-2xs hover:shadow-xs transition-all cursor-pointer group"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-500">Active Enrollments</span>
            <span className="w-9 h-9 rounded-xl bg-cyan-50 text-cyan-600 flex items-center justify-center group-hover:scale-105 transition-transform">
              <GraduationCap size={18} />
            </span>
          </div>
          <p className="mt-3 text-2xl font-extrabold text-[#111827]">{activeEnrollments.toLocaleString()}</p>
          <div className="mt-1 text-[11px] font-semibold text-cyan-600">Enrolled seats</div>
        </div>

        {/* Platform Revenue */}
        <div
          onClick={() => navigate("/billing")}
          className="rounded-2xl border border-[#E5E7EB] bg-white p-5 shadow-2xs hover:shadow-xs transition-all cursor-pointer group"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-500">Total Revenue</span>
            <span className="w-9 h-9 rounded-xl bg-indigo-50 text-[#635BFF] flex items-center justify-center group-hover:scale-105 transition-transform">
              <CreditCard size={18} />
            </span>
          </div>
          <p className="mt-3 text-2xl font-extrabold text-[#111827]">₹41.17L</p>
          <div className="mt-1 text-[11px] font-semibold text-emerald-600">↑ 14% growth</div>
        </div>
      </div>

      {/* 3. 2-Column Section: Enrollment Analytics + Revenue Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Enrollment Trends Chart (7 cols) */}
        <section className="lg:col-span-7 rounded-2xl border border-[#E5E7EB] bg-white p-6 shadow-2xs space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <h3 className="text-base font-bold text-[#111827]">Student Enrollment Trends</h3>
            <span className="text-xs font-bold text-[#635BFF] bg-indigo-50 px-2.5 py-1 rounded-lg border border-indigo-100">
              {timeRange}
            </span>
          </div>

          <div className="flex items-end justify-between h-40 pt-4 gap-2">
            {chartHeights.map((h, i) => (
              <div key={i} className="flex-1 flex flex-col items-center gap-2 h-full justify-end">
                <div
                  className="w-full max-w-[28px] rounded-t-lg bg-[#635BFF] hover:bg-[#5046E5] transition-all cursor-pointer group relative"
                  style={{ height: `${h}%` }}
                >
                  <div className="opacity-0 group-hover:opacity-100 absolute -top-8 left-1/2 -translate-x-1/2 px-2 py-0.5 rounded bg-slate-900 text-white text-[10px] font-bold whitespace-nowrap transition-opacity pointer-events-none">
                    {h * 12} students
                  </div>
                </div>
                <span className="text-[10px] font-semibold text-slate-400">D{i + 1}</span>
              </div>
            ))}
          </div>

          <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
            <span>Average: 540 enrollments/week</span>
            <span className="font-bold text-emerald-600 flex items-center gap-1">
              <TrendingUp size={13} /> +18.4% vs previous period
            </span>
          </div>
        </section>

        {/* Right: Revenue Breakdown Overview (5 cols) */}
        <section className="lg:col-span-5 rounded-2xl border border-[#E5E7EB] bg-white p-6 shadow-2xs flex flex-col justify-between space-y-4">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <h3 className="text-base font-bold text-[#111827]">Revenue Overview</h3>
              <span className="text-xs font-semibold text-slate-400">Current Month</span>
            </div>

            <div className="grid grid-cols-2 gap-4 mt-4">
              <div className="p-4 rounded-xl bg-slate-50 border border-[#E5E7EB] space-y-1">
                <span className="text-[11px] font-semibold text-slate-500">Individual Direct</span>
                <p className="text-xl font-extrabold text-slate-900">₹12,42,000</p>
                <span className="text-[11px] font-bold text-emerald-600">↑ 18%</span>
              </div>
              <div className="p-4 rounded-xl bg-slate-50 border border-[#E5E7EB] space-y-1">
                <span className="text-[11px] font-semibold text-slate-500">Institutional Contracts</span>
                <p className="text-xl font-extrabold text-slate-900">₹28,75,000</p>
                <span className="text-[11px] font-bold text-emerald-600">↑ 12%</span>
              </div>
            </div>

            <div className="mt-4 p-4 rounded-xl bg-[#F5F4FF] border border-[#E5E7EB]">
              <span className="text-xs font-bold text-[#635BFF]">Total Platform Collections</span>
              <h2 className="text-2xl font-extrabold text-[#111827] mt-1 flex items-baseline gap-2">
                ₹41,17,000 <small className="text-xs font-bold text-emerald-600">↑ 14% MoM</small>
              </h2>
            </div>
          </div>

          <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-xs">
            <span className="text-slate-500">Active Billing Contracts: 18</span>
            <button
              type="button"
              onClick={() => navigate("/billing")}
              className="text-xs font-bold text-[#635BFF] hover:underline"
            >
              View Invoices →
            </button>
          </div>
        </section>
      </div>

      {/* 4. 3-Column Section: Pending Approvals + Recent Activity + Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Card 1: Pending Approvals (Part 3) */}
        <section className="rounded-2xl border border-[#E5E7EB] bg-white p-5 shadow-2xs space-y-3">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-[#111827]">Pending Approvals</h3>
              <span className="px-2 py-0.5 rounded-full bg-blue-100 text-blue-800 text-[10px] font-bold">
                {pendingRequestsCount}
              </span>
            </div>
            <button
              type="button"
              onClick={() => navigate("/institutions")}
              className="text-xs font-bold text-[#635BFF] hover:underline cursor-pointer"
            >
              View all →
            </button>
          </div>

          <div className="space-y-3">
            <div className="flex items-start gap-3 p-2.5 rounded-xl hover:bg-slate-50 transition-colors">
              <div className="w-8 h-8 rounded-lg bg-indigo-50 text-[#635BFF] flex items-center justify-center shrink-0 mt-0.5">
                <FileCheck size={16} />
              </div>
              <div className="min-w-0 flex-1">
                <b className="text-xs font-bold text-slate-900 block truncate">Course license request</b>
                <span className="text-[11px] text-slate-500">Python Mastery · Premier Institute · 2h ago</span>
              </div>
            </div>

            <div className="flex items-start gap-3 p-2.5 rounded-xl hover:bg-slate-50 transition-colors">
              <div className="w-8 h-8 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center shrink-0 mt-0.5">
                <Building2 size={16} />
              </div>
              <div className="min-w-0 flex-1">
                <b className="text-xs font-bold text-slate-900 block truncate">New institution onboarding</b>
                <span className="text-[11px] text-slate-500">Apex Global University · 3h ago</span>
              </div>
            </div>

            <div className="flex items-start gap-3 p-2.5 rounded-xl hover:bg-slate-50 transition-colors">
              <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center shrink-0 mt-0.5">
                <CreditCard size={16} />
              </div>
              <div className="min-w-0 flex-1">
                <b className="text-xs font-bold text-slate-900 block truncate">Institutional wire confirmation</b>
                <span className="text-[11px] text-slate-500">TXN-492198 · ₹2,50,000 · 4h ago</span>
              </div>
            </div>
          </div>
        </section>

        {/* Card 2: Recent Activity (Part 3) */}
        <section className="rounded-2xl border border-[#E5E7EB] bg-white p-5 shadow-2xs space-y-3">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <h3 className="text-sm font-bold text-[#111827]">Recent Platform Activity</h3>
            <button
              type="button"
              onClick={() => navigate("/audit-logs")}
              className="text-xs font-bold text-[#635BFF] hover:underline cursor-pointer"
            >
              Audit log →
            </button>
          </div>

          <div className="space-y-3">
            <div className="flex items-start gap-3 p-2.5 rounded-xl hover:bg-slate-50 transition-colors">
              <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center shrink-0 mt-0.5">
                <Users size={16} />
              </div>
              <div className="min-w-0 flex-1">
                <b className="text-xs font-bold text-slate-900 block truncate">New student registration</b>
                <span className="text-[11px] text-slate-500">demo.student1@example.com · Verified</span>
              </div>
            </div>

            <div className="flex items-start gap-3 p-2.5 rounded-xl hover:bg-slate-50 transition-colors">
              <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center shrink-0 mt-0.5">
                <CheckCircle2 size={16} />
              </div>
              <div className="min-w-0 flex-1">
                <b className="text-xs font-bold text-slate-900 block truncate">Course version published</b>
                <span className="text-[11px] text-slate-500">Python Programming · Version live</span>
              </div>
            </div>

            <div className="flex items-start gap-3 p-2.5 rounded-xl hover:bg-slate-50 transition-colors">
              <div className="w-8 h-8 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center shrink-0 mt-0.5">
                <GraduationCap size={16} />
              </div>
              <div className="min-w-0 flex-1">
                <b className="text-xs font-bold text-slate-900 block truncate">Batch assignment generated</b>
                <span className="text-[11px] text-slate-500">Batch 2026-A · 45 learners assigned</span>
              </div>
            </div>
          </div>
        </section>

        {/* Card 3: Quick Actions (Part 3 Specification) */}
        <section className="rounded-2xl border border-[#E5E7EB] bg-white p-5 shadow-2xs space-y-3">
          <div className="pb-3 border-b border-slate-100">
            <h3 className="text-sm font-bold text-[#111827]">Quick Actions</h3>
          </div>

          <div className="space-y-2">
            {/* Action 1: Create Course */}
            <button
              type="button"
              onClick={() => navigate("/courses/create")}
              className="w-full inline-flex items-center justify-center gap-2 rounded-xl bg-[#635BFF] py-2.5 text-xs font-bold text-white shadow-xs hover:bg-[#5046E5] transition cursor-pointer"
            >
              <Plus size={14} />
              <span>Create Course</span>
            </button>

            {/* Action 2: View Courses */}
            <button
              type="button"
              onClick={() => navigate("/courses")}
              className="w-full inline-flex items-center justify-center gap-2 rounded-xl border border-[#E5E7EB] bg-white py-2 text-xs font-bold text-slate-700 hover:bg-slate-50 transition cursor-pointer"
            >
              <BookOpen size={14} className="text-[#635BFF]" />
              <span>View All Courses</span>
            </button>

            {/* Action 3: Manage Users */}
            <button
              type="button"
              onClick={() => navigate("/users")}
              className="w-full inline-flex items-center justify-center gap-2 rounded-xl border border-[#E5E7EB] bg-white py-2 text-xs font-bold text-slate-700 hover:bg-slate-50 transition cursor-pointer"
            >
              <Users size={14} className="text-[#635BFF]" />
              <span>Manage Users</span>
            </button>

            {/* Action 4: Review Course Requests */}
            <button
              type="button"
              onClick={() => navigate("/institutions")}
              className="w-full inline-flex items-center justify-center gap-2 rounded-xl border border-[#E5E7EB] bg-white py-2 text-xs font-bold text-slate-700 hover:bg-slate-50 transition cursor-pointer"
            >
              <FileText size={14} className="text-[#635BFF]" />
              <span>Review Course Requests</span>
            </button>

            {/* Action 5: View Reports */}
            <button
              type="button"
              onClick={() => navigate("/analytics")}
              className="w-full inline-flex items-center justify-center gap-2 rounded-xl border border-[#E5E7EB] bg-white py-2 text-xs font-bold text-slate-700 hover:bg-slate-50 transition cursor-pointer"
            >
              <BarChart3 size={14} className="text-[#635BFF]" />
              <span>View Platform Reports</span>
            </button>
          </div>
        </section>
      </div>

      {/* 5. Popular Courses Overview Table */}
      <section className="rounded-2xl border border-[#E5E7EB] bg-white shadow-2xs overflow-hidden">
        <div className="p-5 border-b border-slate-100 flex items-center justify-between">
          <div>
            <h3 className="text-base font-bold text-[#111827]">Active Course Catalog</h3>
            <p className="text-xs text-slate-500">Live courses, enrollment distribution, and authoring statuses</p>
          </div>
          <button
            type="button"
            onClick={() => navigate("/courses")}
            className="text-xs font-bold text-[#635BFF] hover:underline flex items-center gap-1 cursor-pointer"
          >
            <span>Manage All Courses ({totalCourses})</span>
            <ArrowRight size={13} />
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-[#E5E7EB] bg-slate-50/70 text-slate-500 font-bold uppercase tracking-wider text-[10px]">
                <th className="py-3 px-4">Course</th>
                <th className="py-3 px-4">Instructor</th>
                <th className="py-3 px-4">Modules</th>
                <th className="py-3 px-4">Pricing</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {courses.length > 0 ? (
                courses.slice(0, 6).map((c) => {
                  const isPublished = c.versions?.some((v) => v.status === "published");
                  const initials = c.title
                    .split(" ")
                    .map((w) => w[0])
                    .slice(0, 2)
                    .join("")
                    .toUpperCase();

                  return (
                    <tr key={c.course_id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="py-3.5 px-4">
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-900 to-[#635BFF] text-white flex items-center justify-center font-bold text-xs shrink-0">
                            {initials || "CR"}
                          </div>
                          <div className="min-w-0">
                            <b className="text-xs font-bold text-slate-900 hover:text-[#635BFF] cursor-pointer block truncate" onClick={() => navigate(`/courses/${c.course_id}`)}>
                              {c.title}
                            </b>
                            <span className="text-[11px] text-slate-400">ID: {c.course_id.slice(-8)}</span>
                          </div>
                        </div>
                      </td>
                      <td className="py-3.5 px-4 font-medium text-slate-700">Dr. Sneha Reddy</td>
                      <td className="py-3.5 px-4 text-slate-600 font-semibold">1 Module · Graded Tests</td>
                      <td className="py-3.5 px-4">
                        <div className="text-[11px]">
                          <span className="font-bold text-slate-900">₹1,999</span>
                          <span className="text-slate-400 ml-1">(₹499/seat)</span>
                        </div>
                      </td>
                      <td className="py-3.5 px-4">
                        {isPublished ? (
                          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-0.5 text-[10.5px] font-bold text-emerald-700 border border-emerald-200">
                            <CheckCircle2 size={11} /> Published
                          </span>
                        ) : (
                          <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-[10.5px] font-bold text-slate-600 border border-slate-200">
                            Draft
                          </span>
                        )}
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            type="button"
                            onClick={() => navigate(`/courses/${c.course_id}`)}
                            className="rounded-lg bg-indigo-50 px-2.5 py-1 text-xs font-bold text-[#635BFF] hover:bg-[#635BFF] hover:text-white transition-colors cursor-pointer"
                          >
                            Open
                          </button>
                          <button
                            type="button"
                            onClick={() => navigate(`/courses/${c.course_id}/edit`)}
                            className="rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors cursor-pointer"
                          >
                            Edit
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-xs text-slate-500">
                    No courses available. Click "Create Course" to add your first course.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

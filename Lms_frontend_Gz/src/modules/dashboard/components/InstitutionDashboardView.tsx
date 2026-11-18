import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  BookOpen,
  Users,
  Award,
  Calendar,
  Plus,
  ArrowRight,
  TrendingUp,
  FileCheck,
  CreditCard,
  Building2,
  CheckCircle2,
  ExternalLink,
} from "lucide-react";
import { useAuth } from "@/modules/user-management/auth/hooks/useAuth";
import {
  useGetInstitutionPurchasesQuery,
  useGetInstitutionRequestsQuery,
} from "@/modules/billing/institutional/api/institutionalApi";
import { useListBatchesQuery } from "@/modules/learning/batches/api/batchesApi";

export function InstitutionDashboardView() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [timeRange] = useState("Academic Year 2026-27");

  const { data: packages = [] } = useGetInstitutionPurchasesQuery();
  const { data: requests = [] } = useGetInstitutionRequestsQuery();
  const { data: batchesData } = useListBatchesQuery({});

  const institutionName = user?.institution?.name || "Premier Institute of Technology";

  // Aggregate metrics from real packages
  const metrics = useMemo(() => {
    const totalCourses = packages.reduce((acc, p) => acc + (p.courses?.length || 0), 0);
    const totalSeats = packages.reduce((acc, p) => acc + (p.seats_total || 0), 0);
    const usedSeats = packages.reduce((acc, p) => acc + (p.seats_used || 0), 0);
    const availableSeats = Math.max(0, totalSeats - usedSeats);
    const utilizationRate = totalSeats > 0 ? Math.round((usedSeats / totalSeats) * 100) : 0;

    return {
      totalCourses,
      totalSeats,
      usedSeats,
      availableSeats,
      utilizationRate,
      activePackages: packages.length,
    };
  }, [packages]);

  const batches = batchesData?.items ?? [];
  const totalBatches = batches.length;

  const chartHeights = [40, 52, 48, 65, 72, 60, 85, 90, 78, 92, 96, 100];

  return (
    <div className="space-y-5 max-w-[1600px] mx-auto pb-16 font-sans">
      {/* 1. Workspace Header: 28px/700, 14px/400 subtitle */}
      <div className="page-head">
        <div>
          <div className="eyebrow">INSTITUTION WORKSPACE · {institutionName.toUpperCase()}</div>
          <h1>Institution Dashboard</h1>
          <p>Monitor licensed courses, student allocations, batch performance and quotas.</p>
        </div>
        <div className="head-actions">
          <div className="relative inline-flex items-center">
            <button
              type="button"
              className="inline-flex items-center gap-2 rounded-xl border border-[#E5E7EB] bg-white px-3.5 h-10 text-[13px] font-medium text-[#111827] shadow-2xs hover:bg-slate-50 transition cursor-pointer"
            >
              <Calendar size={14} className="text-[#64748B]" />
              <span>{timeRange}</span>
              <span className="text-[#64748B]">⌄</span>
            </button>
          </div>
          <button
            type="button"
            onClick={() => navigate("/browse-courses")}
            className="inline-flex items-center gap-1.5 rounded-xl bg-[#635BFF] px-4 h-10 text-[14px] font-semibold text-white shadow-xs hover:bg-[#5046E5] transition cursor-pointer"
          >
            <Plus size={16} />
            <span>Request Course Quota</span>
          </button>
        </div>
      </div>

      {/* 2. 4 Modern Stat / KPI Cards: 20px padding, 12px border radius, #FFFFFF, border #E5E7EB */}
      <div className="grid stats">
        <div className="stat">
          <div className="stat-icon">
            <BookOpen size={20} />
          </div>
          <div>
            <label>Licensed Courses</label>
            <strong>{metrics.totalCourses}</strong>
            <div className="delta">Active curriculum</div>
          </div>
        </div>

        <div className="stat">
          <div className="stat-icon green">
            <Users size={20} />
          </div>
          <div>
            <label>Enrolled Learners</label>
            <strong>{metrics.usedSeats.toLocaleString()}</strong>
            <div className="delta">↑ {metrics.utilizationRate}% seat utilization</div>
          </div>
        </div>

        <div className="stat">
          <div className="stat-icon blue">
            <Building2 size={20} />
          </div>
          <div>
            <label>Active Batches</label>
            <strong>{totalBatches}</strong>
            <div className="delta">Across departments</div>
          </div>
        </div>

        <div className="stat">
          <div className="stat-icon orange">
            <Award size={20} />
          </div>
          <div>
            <label>Assessment Pass Rate</label>
            <strong>88.4%</strong>
            <div className="delta">↑ 4.2% this semester</div>
          </div>
        </div>
      </div>

      {/* 3. 2-Column Section: Learning Analytics & Seat Utilization */}
      <div className="grid two-col">
        {/* Left Card: Enrollment & Activity Analytics */}
        <section className="card">
          <div className="card-head">
            <div>
              <h3>Institutional Learning Activity</h3>
              <p className="text-[12px] text-[#64748B] mt-0.5">Weekly module completion rates across enrolled departments</p>
            </div>
            <span className="pill blue">Real-time</span>
          </div>

          <div className="chart">
            {chartHeights.map((h, i) => (
              <div
                key={i}
                className="bar"
                style={{ height: `${h}%` }}
                title={`Week ${i + 1}: ${h}% completion`}
              />
            ))}
          </div>

          <div className="chart-labels">
            <span>Oct 1</span>
            <span>Oct 8</span>
            <span>Oct 15</span>
            <span>Oct 22</span>
            <span>Oct 30</span>
          </div>
        </section>

        {/* Right Card: Seat Quota & License Overview */}
        <section className="card flex flex-col justify-between">
          <div className="card-head">
            <div>
              <h3>Seat Quota & Licenses</h3>
              <p className="text-[12px] text-[#64748B] mt-0.5">Current institutional subscription breakdown</p>
            </div>
            <button
              type="button"
              onClick={() => navigate("/store/invoices")}
              className="text-[12px] font-semibold text-[#635BFF] hover:underline cursor-pointer"
            >
              Invoices →
            </button>
          </div>

          <div className="card-body">
            <div className="revenue-box">
              <div>
                <label>TOTAL SEATS PURCHASED</label>
                <strong>{metrics.totalSeats}</strong>
                <span className="text-[11px] text-[#64748B]">Approved quota</span>
              </div>
              <div>
                <label>AVAILABLE SEATS</label>
                <strong className="text-[#16A37B]">{metrics.availableSeats}</strong>
                <span className="text-[11px] text-[#16A37B]">Ready to allocate</span>
              </div>
            </div>

            <div className="mt-5 space-y-2">
              <div className="flex justify-between text-[13px]">
                <span className="font-medium text-[#111827]">Allocation Capacity</span>
                <span className="font-semibold text-[#635BFF]">{metrics.utilizationRate}% used</span>
              </div>
              <div className="w-full bg-slate-100 h-2.5 rounded-full overflow-hidden">
                <div
                  className="bg-[#635BFF] h-full rounded-full transition-all duration-500"
                  style={{ width: `${metrics.utilizationRate}%` }}
                />
              </div>
              <div className="flex justify-between text-[11px] text-[#64748B] pt-1">
                <span>{metrics.usedSeats} assigned</span>
                <span>{metrics.availableSeats} remaining</span>
              </div>
            </div>

            <div className="mt-5 pt-4 border-t border-[#E5E7EB] flex items-center justify-between">
              <div>
                <p className="text-[13px] font-semibold text-[#111827]">Need additional seats?</p>
                <p className="text-[11px] text-[#64748B]">Request bulk additions with institutional discounts.</p>
              </div>
              <button
                type="button"
                onClick={() => navigate("/browse-courses")}
                className="h-9 px-3.5 rounded-xl bg-[#F5F4FF] text-[#635BFF] text-[13px] font-semibold hover:bg-[#EDE8FF] transition cursor-pointer"
              >
                Expand Quota
              </button>
            </div>
          </div>
        </section>
      </div>

      {/* 4. 3-Column Section: Pending Quotas + Department Activity + Quick Actions */}
      <div className="grid three-col">
        {/* Card 1: Course Requests & Quotes */}
        <section className="card">
          <div className="card-head">
            <div className="flex items-center gap-2">
              <h3>Quota Requests</h3>
              <span className="pill blue">{requests.length || 2}</span>
            </div>
            <button
              type="button"
              onClick={() => navigate("/institution-requests")}
              className="text-[12px] font-semibold text-[#635BFF] hover:underline cursor-pointer"
            >
              View all →
            </button>
          </div>
          <div className="card-body py-1">
            <div className="activity">
              <div className="activity-dot">
                <FileCheck size={16} />
              </div>
              <div>
                <b>Python for Machine Learning</b>
                <small>50 seats requested · In Review</small>
              </div>
            </div>

            <div className="activity">
              <div className="activity-dot">
                <CreditCard size={16} />
              </div>
              <div>
                <b>Full Stack Web Development</b>
                <small>Quotation approved · Ready for payment</small>
              </div>
            </div>

            <div className="activity">
              <div className="activity-dot">
                <CheckCircle2 size={16} />
              </div>
              <div>
                <b>Data Structures & Algorithms</b>
                <small>100 seats active · Enrolled</small>
              </div>
            </div>
          </div>
        </section>

        {/* Card 2: Recent Department Activity */}
        <section className="card">
          <div className="card-head">
            <h3>Department Activity</h3>
            <span className="text-[11px] text-[#64748B]">Recent updates</span>
          </div>
          <div className="card-body py-1">
            <div className="activity">
              <div className="activity-dot">
                <Users size={16} />
              </div>
              <div>
                <b>Batch CSE-2026 Assigned</b>
                <small>45 students enrolled · 2h ago</small>
              </div>
            </div>

            <div className="activity">
              <div className="activity-dot">
                <CheckCircle2 size={16} />
              </div>
              <div>
                <b>Final Exam Passed (82%)</b>
                <small>Batch ECE-A · Yesterday</small>
              </div>
            </div>

            <div className="activity">
              <div className="activity-dot">
                <TrendingUp size={16} />
              </div>
              <div>
                <b>New Milestone Reached</b>
                <small>500th course certificate issued</small>
              </div>
            </div>
          </div>
        </section>

        {/* Card 3: Quick Institutional Actions */}
        <section className="card flex flex-col justify-between">
          <div className="card-head">
            <h3>Quick Actions</h3>
            <span className="pill">Shortcuts</span>
          </div>
          <div className="card-body space-y-2">
            <button
              type="button"
              onClick={() => navigate("/batches")}
              className="w-full flex items-center justify-between p-3 rounded-xl border border-[#E5E7EB] bg-slate-50/50 hover:bg-slate-100 transition text-[13px] font-medium text-[#111827] cursor-pointer"
            >
              <span className="flex items-center gap-2.5">
                <Building2 size={16} className="text-[#635BFF]" />
                Manage Batches & Classes
              </span>
              <ArrowRight size={14} className="text-[#64748B]" />
            </button>

            <button
              type="button"
              onClick={() => navigate("/browse-courses")}
              className="w-full flex items-center justify-between p-3 rounded-xl border border-[#E5E7EB] bg-slate-50/50 hover:bg-slate-100 transition text-[13px] font-medium text-[#111827] cursor-pointer"
            >
              <span className="flex items-center gap-2.5">
                <BookOpen size={16} className="text-[#635BFF]" />
                Browse Course Catalog
              </span>
              <ArrowRight size={14} className="text-[#64748B]" />
            </button>

            <button
              type="button"
              onClick={() => navigate("/people")}
              className="w-full flex items-center justify-between p-3 rounded-xl border border-[#E5E7EB] bg-slate-50/50 hover:bg-slate-100 transition text-[13px] font-medium text-[#111827] cursor-pointer"
            >
              <span className="flex items-center gap-2.5">
                <Users size={16} className="text-[#635BFF]" />
                Student Directory
              </span>
              <ArrowRight size={14} className="text-[#64748B]" />
            </button>

            <button
              type="button"
              onClick={() => navigate("/certificates")}
              className="w-full flex items-center justify-between p-3 rounded-xl border border-[#E5E7EB] bg-slate-50/50 hover:bg-slate-100 transition text-[13px] font-medium text-[#111827] cursor-pointer"
            >
              <span className="flex items-center gap-2.5">
                <Award size={16} className="text-[#635BFF]" />
                Issued Certificates
              </span>
              <ArrowRight size={14} className="text-[#64748B]" />
            </button>
          </div>
        </section>
      </div>

      {/* 5. Institutional Courses & Allocation Table */}
      <section className="card">
        <div className="card-head">
          <div>
            <h3>Active Institutional Courses & Allocation</h3>
            <p className="text-[12px] text-[#64748B] mt-0.5">Courses currently provisioned for this academic institution</p>
          </div>
          <button
            type="button"
            onClick={() => navigate("/browse-courses")}
            className="text-[12px] font-semibold text-[#635BFF] hover:underline cursor-pointer"
          >
            View all courses →
          </button>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>COURSE</th>
                <th>ALLOCATED SEATS</th>
                <th>ENROLLED STUDENTS</th>
                <th>PASS RATE</th>
                <th>STATUS</th>
                <th>ACTION</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>
                  <div className="course-cell">
                    <div className="course-thumb-box">PY</div>
                    <div>
                      <b>Python for Data Science & AI</b>
                      <span className="block text-[11px] text-[#64748B]">CS-401 · Computer Science</span>
                    </div>
                  </div>
                </td>
                <td>100 seats</td>
                <td>
                  <b>88 learners</b> (88%)
                </td>
                <td>
                  <span className="font-semibold text-[#16A37B]">91.2%</span>
                </td>
                <td>
                  <span className="pill">Active</span>
                </td>
                <td>
                  <button
                    type="button"
                    onClick={() => navigate("/batches")}
                    className="inline-flex items-center gap-1 text-[12px] font-semibold text-[#635BFF] hover:underline cursor-pointer"
                  >
                    <span>Manage</span>
                    <ExternalLink size={12} />
                  </button>
                </td>
              </tr>

              <tr>
                <td>
                  <div className="course-cell">
                    <div className="course-thumb-box">FS</div>
                    <div>
                      <b>Full Stack Web Development with React</b>
                      <span className="block text-[11px] text-[#64748B]">WEB-201 · Information Tech</span>
                    </div>
                  </div>
                </td>
                <td>150 seats</td>
                <td>
                  <b>125 learners</b> (83%)
                </td>
                <td>
                  <span className="font-semibold text-[#16A37B]">87.5%</span>
                </td>
                <td>
                  <span className="pill">Active</span>
                </td>
                <td>
                  <button
                    type="button"
                    onClick={() => navigate("/batches")}
                    className="inline-flex items-center gap-1 text-[12px] font-semibold text-[#635BFF] hover:underline cursor-pointer"
                  >
                    <span>Manage</span>
                    <ExternalLink size={12} />
                  </button>
                </td>
              </tr>

              <tr>
                <td>
                  <div className="course-cell">
                    <div className="course-thumb-box">ML</div>
                    <div>
                      <b>Machine Learning & Neural Networks</b>
                      <span className="block text-[11px] text-[#64748B]">AI-301 · Artificial Intelligence</span>
                    </div>
                  </div>
                </td>
                <td>80 seats</td>
                <td>
                  <b>62 learners</b> (77%)
                </td>
                <td>
                  <span className="font-semibold text-[#16A37B]">84.0%</span>
                </td>
                <td>
                  <span className="pill">Active</span>
                </td>
                <td>
                  <button
                    type="button"
                    onClick={() => navigate("/batches")}
                    className="inline-flex items-center gap-1 text-[12px] font-semibold text-[#635BFF] hover:underline cursor-pointer"
                  >
                    <span>Manage</span>
                    <ExternalLink size={12} />
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

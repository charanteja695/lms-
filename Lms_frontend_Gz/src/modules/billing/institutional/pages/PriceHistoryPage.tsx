import { useState, useMemo } from "react";
import { Link } from "react-router-dom";
import {
  useGetCoursePricingHistoryQuery,
  useGetAdminCoursePricingQuery,
} from "@/modules/billing/institutional/api/institutionalApi";
import type { CoursePricingAuditItem } from "@/modules/billing/institutional/types";

const THUMBNAIL_STYLES: Record<string, { bg: string; color: string; cls: string }> = {
  DS: { bg: "#E0F2FE", color: "#075985", cls: "t2" },
  JP: { bg: "#FCE7F3", color: "#9D174D", cls: "t6" },
  UP: { bg: "#EDE9FE", color: "#5B21B6", cls: "t5" },
  SR: { bg: "#FEF3C7", color: "#92400E", cls: "t4" },
  QA: { bg: "#DBEAFE", color: "#1E40AF", cls: "t1" },
  EN: { bg: "#E0F2FE", color: "#075985", cls: "t2" },
  BA: { bg: "#DBEAFE", color: "#1E40AF", cls: "t1" },
};

function getCourseBadge(code?: string, id?: number | string) {
  const c = String(code || "CR").toUpperCase();
  if (THUMBNAIL_STYLES[c]) {
    return { code: c, ...THUMBNAIL_STYLES[c] };
  }
  const colorList = ["t1", "t2", "t3", "t4", "t5", "t6"];
  const cls = colorList[(Number(id) || 0) % colorList.length];
  return { code: c.slice(0, 2), bg: "", color: "", cls };
}

function formatInr(paise: number): string {
  return "₹" + Math.round(paise / 100).toLocaleString("en-IN");
}

function formatDate(iso: string): { dateStr: string; timeStr: string } {
  try {
    const d = new Date(iso);
    const dateStr = d.toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
    const timeStr = d.toLocaleTimeString("en-US", {
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    });
    return { dateStr, timeStr };
  } catch {
    return { dateStr: iso, timeStr: "" };
  }
}

export function PriceHistoryPage() {
  // Filters state
  const [courseFilter, setCourseFilter] = useState<string>("all");
  const [adminFilter, setAdminFilter] = useState<string>("all");
  const [fromDate, setFromDate] = useState<string>("");
  const [toDate, setToDate] = useState<string>("");
  const [priceType, setPriceType] = useState<"All" | "Individual" | "Institutional">("All");
  const [page, setPage] = useState<number>(1);
  const perPage = 7;

  // Fetch live courses for dropdown
  const { data: courses = [] } = useGetAdminCoursePricingQuery();

  // Fetch audits with filters
  const { data: historyData, isLoading } = useGetCoursePricingHistoryQuery({
    course_id: courseFilter !== "all" ? courseFilter : undefined,
    changed_by: adminFilter !== "all" ? adminFilter : undefined,
    price_type: priceType !== "All" ? priceType.toLowerCase() : undefined,
    from_date: fromDate || undefined,
    to_date: toDate || undefined,
    page,
    per_page: perPage,
  });

  const audits = historyData?.audits || [];
  const totalCount = historyData?.total || audits.length;
  const totalPages = Math.max(1, Math.ceil(totalCount / perPage));

  // Extract unique admins from audits or defaults
  const availableAdmins = useMemo(() => {
    const set = new Set<string>();
    audits.forEach((a) => {
      if (a.admin_name) set.add(a.admin_name);
    });
    set.add("Neha Rao");
    set.add("Arjun Mehta");
    return Array.from(set);
  }, [audits]);

  const handleClearFilters = () => {
    setCourseFilter("all");
    setAdminFilter("all");
    setFromDate("");
    setToDate("");
    setPriceType("All");
    setPage(1);
  };

  const handleExportCsv = () => {
    if (!audits.length) return;
    const headers = [
      "Course Code",
      "Course Title",
      "Individual Price (₹)",
      "Previous Individual Price (₹)",
      "Institutional Price (₹)",
      "Previous Institutional Price (₹)",
      "Changed By",
      "Role",
      "Reason",
      "Date",
      "Time",
    ];
    const rows = audits.map((a) => {
      const dt = formatDate(a.created_at);
      return [
        `"${a.course_code || ""}"`,
        `"${(a.course_title || "").replace(/"/g, '""')}"`,
        `"${(a.new_individual_price_paise / 100).toFixed(2)}"`,
        `"${a.previous_individual_price_paise ? (a.previous_individual_price_paise / 100).toFixed(2) : "-"}"`,
        `"${(a.new_institutional_price_paise / 100).toFixed(2)}"`,
        `"${a.previous_institutional_price_paise ? (a.previous_institutional_price_paise / 100).toFixed(2) : "-"}"`,
        `"${(a.admin_name || a.admin_email || "").replace(/"/g, '""')}"`,
        `"${(a.admin_role || "Admin").replace(/"/g, '""')}"`,
        `"${(a.reason || "No reason given").replace(/"/g, '""')}"`,
        `"${dt.dateStr}"`,
        `"${dt.timeStr}"`,
      ].join(",");
    });
    const csvContent = "data:text/csv;charset=utf-8," + [headers.join(","), ...rows].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `price_change_history_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const renderIndividualDiff = (item: CoursePricingAuditItem) => {
    const prev = item.previous_individual_price_paise;
    const curr = item.new_individual_price_paise;
    if (!prev) {
      return (
        <div className="pc">
          <span className="n">{formatInr(curr)}</span>
          <span className="d z">Initial price</span>
        </div>
      );
    }
    const diff = curr - prev;
    if (diff === 0) {
      return (
        <div className="pc">
          <span className="n">{formatInr(curr)}</span>
          <span className="d z">No change</span>
        </div>
      );
    }
    const pct = Math.abs((diff / prev) * 100).toFixed(2);
    const absDiffStr = formatInr(Math.abs(diff));
    if (diff > 0) {
      return (
        <div className="pc">
          <span className="o">{formatInr(prev)}</span>
          <span className="n">{formatInr(curr)}</span>
          <span className="d u">▲ +{absDiffStr} (+{pct}%)</span>
        </div>
      );
    }
    return (
      <div className="pc">
        <span className="o">{formatInr(prev)}</span>
        <span className="n">{formatInr(curr)}</span>
        <span className="d w">▼ −{absDiffStr} (−{pct}%)</span>
      </div>
    );
  };

  const renderInstitutionalDiff = (item: CoursePricingAuditItem) => {
    const prev = item.previous_institutional_price_paise;
    const curr = item.new_institutional_price_paise;
    if (!prev) {
      return (
        <div className="pc">
          <span className="n">{formatInr(curr)}</span>
          <span className="d z">Initial price</span>
        </div>
      );
    }
    const diff = curr - prev;
    if (diff === 0) {
      return (
        <div className="pc">
          <span className="n">{formatInr(curr)}</span>
          <span className="d z">No change</span>
        </div>
      );
    }
    const pct = Math.abs((diff / prev) * 100).toFixed(2);
    const absDiffStr = formatInr(Math.abs(diff));
    if (diff > 0) {
      return (
        <div className="pc">
          <span className="o">{formatInr(prev)}</span>
          <span className="n">{formatInr(curr)}</span>
          <span className="d u">▲ +{absDiffStr} (+{pct}%)</span>
        </div>
      );
    }
    return (
      <div className="pc">
        <span className="o">{formatInr(prev)}</span>
        <span className="n">{formatInr(curr)}</span>
        <span className="d w">▼ −{absDiffStr} (−{pct}%)</span>
      </div>
    );
  };

  return (
    <>
      <style>{`
        .course-mgmt-shell {
          --p: #2563EB;
          --ph: #1D4ED8;
          --pt: #EFF6FF;
          --bg: #F8FAFC;
          --s: #fff;
          --t: #0F172A;
          --m: #64748B;
          --b: #E2E8F0;
          --ok: #16A34A;
          --okt: #F0FDF4;
          --okx: #15803D;
          --wa: #F59E0B;
          --wat: #FFFBEB;
          --wax: #B45309;
          --er: #DC2626;
          --ert: #FEF2F2;
          --erx: #B91C1C;
          --in: #0EA5E9;
          --int: #F0F9FF;
          --inx: #0369A1;
          display: block;
          width: 100%;
          min-height: 100vh;
          background: #F8FAFC;
          color: #0F172A;
          font-family: Inter, system-ui, -apple-system, sans-serif;
          margin: 0;
          padding: 0;
          box-sizing: border-box;
        }
        .course-mgmt-shell * {
          box-sizing: border-box;
        }
        .course-mgmt-shell h1,
        .course-mgmt-shell h2,
        .course-mgmt-shell h3,
        .course-mgmt-shell h4 {
          font-family: 'Plus Jakarta Sans', Inter, system-ui, sans-serif;
          margin: 0;
          letter-spacing: -0.01em;
          color: #0F172A;
        }
        .course-mgmt-shell .ic {
          width: 18px;
          height: 18px;
          flex: none;
          stroke: currentColor;
          fill: none;
          stroke-width: 1.8;
          stroke-linecap: round;
          stroke-linejoin: round;
        }
        .course-mgmt-shell .ic.sm {
          width: 16px;
          height: 16px;
        }
        .course-mgmt-shell .main {
          width: 100%;
          display: flex;
          flex-direction: column;
        }
        .course-mgmt-shell .top {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          flex-wrap: wrap;
          padding: 12px 32px;
          background: #fff;
          border-bottom: 1px solid #E2E8F0;
          min-height: 57px;
        }
        .course-mgmt-shell .crumb {
          color: #64748B;
          font-size: 13px;
          display: flex;
          gap: 6px;
          align-items: center;
        }
        .course-mgmt-shell .crumb b {
          color: #0F172A;
          font-weight: 600;
        }
        .course-mgmt-shell .content {
          padding: 28px 32px 48px;
          display: flex;
          flex-direction: column;
          gap: 24px;
        }
        .course-mgmt-shell .ph {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 16px;
          flex-wrap: wrap;
        }
        .course-mgmt-shell .ph h1 {
          font-size: 24px;
          font-weight: 700;
          line-height: 1.25;
        }
        .course-mgmt-shell .ph p {
          margin-top: 4px;
          color: #64748B;
        }
        .course-mgmt-shell .row {
          display: flex;
          gap: 8px;
          align-items: center;
          flex-wrap: wrap;
        }
        .course-mgmt-shell .av {
          width: 30px;
          height: 30px;
          border-radius: 50%;
          background: #DBEAFE;
          color: #1E40AF;
          display: grid;
          place-items: center;
          font-size: 11px;
          font-weight: 700;
          flex: none;
        }
        .course-mgmt-shell .btn {
          height: 40px;
          padding: 0 14px;
          border-radius: 8px;
          border: 1px solid #E2E8F0;
          background: #fff;
          color: #0F172A;
          font: 500 14px Inter, sans-serif;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          cursor: pointer;
          text-decoration: none;
          white-space: nowrap;
          transition: all 0.15s ease;
        }
        .course-mgmt-shell .btn:hover {
          background: #F8FAFC;
        }
        .course-mgmt-shell .btn.p {
          background: #2563EB;
          border-color: #2563EB;
          color: #fff;
        }
        .course-mgmt-shell .btn.p:hover {
          background: #1D4ED8;
        }
        .course-mgmt-shell .btn.ico {
          width: 36px;
          padding: 0;
        }
        .course-mgmt-shell .btn.ghost {
          border-color: transparent;
          background: transparent;
        }
        .course-mgmt-shell .btn.ghost:hover {
          background: #F1F5F9;
        }
        .course-mgmt-shell .card {
          background: #fff;
          border: 1px solid #E2E8F0;
          border-radius: 12px;
          box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05);
        }
        .course-mgmt-shell .tw {
          overflow-x: auto;
        }
        .course-mgmt-shell table {
          width: 100%;
          border-collapse: collapse;
          min-width: 1180px;
        }
        .course-mgmt-shell th {
          text-align: left;
          font-size: 12px;
          font-weight: 600;
          color: #64748B;
          padding: 10px 16px;
          background: #F8FAFC;
          border-bottom: 1px solid #E2E8F0;
          white-space: nowrap;
        }
        .course-mgmt-shell td {
          padding: 12px 16px;
          border-bottom: 1px solid #E2E8F0;
          vertical-align: middle;
        }
        .course-mgmt-shell tbody tr:hover {
          background: #FAFBFD;
        }
        .course-mgmt-shell tbody tr:last-child td {
          border-bottom: 0;
        }
        .course-mgmt-shell .cell {
          display: flex;
          align-items: center;
          gap: 12px;
          min-width: 0;
        }
        .course-mgmt-shell .th {
          width: 56px;
          height: 40px;
          border-radius: 8px;
          flex: none;
          display: grid;
          place-items: center;
          font: 700 13px 'Plus Jakarta Sans', sans-serif;
        }
        .course-mgmt-shell .t1 { background: #DBEAFE; color: #1E40AF; }
        .course-mgmt-shell .t2 { background: #E0F2FE; color: #075985; }
        .course-mgmt-shell .t3 { background: #DCFCE7; color: #166534; }
        .course-mgmt-shell .t4 { background: #FEF3C7; color: #92400E; }
        .course-mgmt-shell .t5 { background: #EDE9FE; color: #5B21B6; }
        .course-mgmt-shell .t6 { background: #FCE7F3; color: #9D174D; }
        .course-mgmt-shell .sub {
          color: #64748B;
          font-size: 12px;
        }
        .course-mgmt-shell .strong {
          font-weight: 600;
        }
        .course-mgmt-shell .muted {
          color: #64748B;
        }
        .course-mgmt-shell .toolbar {
          display: flex;
          gap: 14px;
          flex-wrap: wrap;
          align-items: flex-end;
          padding: 14px 16px;
          border-bottom: 1px solid #E2E8F0;
        }
        .course-mgmt-shell .pager {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 12px;
          padding: 12px 16px;
          flex-wrap: wrap;
          color: #64748B;
          font-size: 13px;
          border-top: 1px solid #E2E8F0;
        }
        .course-mgmt-shell .pg {
          min-width: 32px;
          height: 32px;
          border-radius: 8px;
          border: 1px solid #E2E8F0;
          background: #fff;
          display: inline-grid;
          place-items: center;
          font-size: 13px;
          color: #0F172A;
          cursor: pointer;
        }
        .course-mgmt-shell .pg.on {
          background: #2563EB;
          border-color: #2563EB;
          color: #fff;
          font-weight: 600;
        }
        .course-mgmt-shell .inp {
          height: 40px;
          width: 100%;
          border: 1px solid #CBD5E1;
          border-radius: 8px;
          padding: 0 12px;
          font: 14px Inter, sans-serif;
          color: #0F172A;
          background: #fff;
          display: flex;
          align-items: center;
        }
        .course-mgmt-shell .f {
          display: flex;
          flex-direction: column;
        }
        .course-mgmt-shell .lab {
          display: block;
          font-weight: 500;
          font-size: 13px;
          margin-bottom: 6px;
        }
        .course-mgmt-shell .sel {
          appearance: none;
          -webkit-appearance: none;
          background: #fff url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%2364748B' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E") no-repeat right 10px center;
          padding-right: 32px;
        }
        .course-mgmt-shell .seg {
          display: inline-flex;
          border: 1px solid #E2E8F0;
          border-radius: 8px;
          overflow: hidden;
          background: #fff;
        }
        .course-mgmt-shell .seg button {
          padding: 0 14px;
          height: 38px;
          font: 500 13px Inter, sans-serif;
          color: #334155;
          background: #fff;
          border: 0;
          border-right: 1px solid #E2E8F0;
          cursor: pointer;
          transition: all 0.15s ease;
        }
        .course-mgmt-shell .seg button:last-child {
          border-right: 0;
        }
        .course-mgmt-shell .seg button.on {
          background: #EFF6FF;
          color: #1D4ED8;
          font-weight: 600;
        }
        .course-mgmt-shell .pc {
          display: flex;
          flex-direction: column;
          gap: 2px;
          font-variant-numeric: tabular-nums;
        }
        .course-mgmt-shell .pc .o {
          color: #64748B;
          text-decoration: line-through;
          font-size: 12px;
        }
        .course-mgmt-shell .pc .n {
          font-weight: 600;
        }
        .course-mgmt-shell .pc .d {
          font-size: 12px;
          font-weight: 600;
        }
        .course-mgmt-shell .pc .u {
          color: #B45309;
        }
        .course-mgmt-shell .pc .w {
          color: #0369A1;
        }
        .course-mgmt-shell .pc .z {
          color: #64748B;
          font-weight: 400;
        }
        .course-mgmt-shell .note {
          display: flex;
          gap: 10px;
          padding: 12px 14px;
          border-radius: 10px;
          font-size: 13px;
          align-items: flex-start;
        }
        .course-mgmt-shell .note .ic {
          margin-top: 1px;
        }
        @media (max-width: 800px) {
          .course-mgmt-shell .content {
            padding: 20px 16px 40px;
          }
          .course-mgmt-shell .top {
            padding: 12px 16px;
          }
          .course-mgmt-shell .side {
            max-width: none;
            width: 100%;
          }
        }
      `}</style>

      {/* SVG Icon Definitions */}
      <svg width="0" height="0" style={{ position: "absolute" }} aria-hidden="true">
        <defs>
          <symbol id="i-grid" viewBox="0 0 24 24">
            <path d="M3 3h7v9H3z M14 3h7v5h-7z M14 12h7v9h-7z M3 16h7v5H3z" />
          </symbol>
          <symbol id="i-book" viewBox="0 0 24 24">
            <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20 M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
          </symbol>
          <symbol id="i-plus" viewBox="0 0 24 24">
            <path d="M12 5v14 M5 12h14" />
          </symbol>
          <symbol id="i-layers" viewBox="0 0 24 24">
            <path d="M12 2 2 7l10 5 10-5-10-5z M2 17l10 5 10-5 M2 12l10 5 10-5" />
          </symbol>
          <symbol id="i-clip" viewBox="0 0 24 24">
            <path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2 M9 3h6v4H9z M9 14l2 2 4-4" />
          </symbol>
          <symbol id="i-tag" viewBox="0 0 24 24">
            <path d="M20.6 13.4 13.4 20.6a2 2 0 0 1-2.8 0L2 12V2h10l8.6 8.6a2 2 0 0 1 0 2.8z M7 7h.01" />
          </symbol>
          <symbol id="i-bld" viewBox="0 0 24 24">
            <path d="M3 21h18 M5 21V5a1 1 0 0 1 1-1h8a1 1 0 0 1 1 1v16 M15 9h4a1 1 0 0 1 1 1v11 M9 8h2 M9 12h2 M9 16h2" />
          </symbol>
          <symbol id="i-hist" viewBox="0 0 24 24">
            <path d="M3 12a9 9 0 1 0 3-6.7L3 8 M3 3v5h5 M12 7v5l3 2" />
          </symbol>
          <symbol id="i-dl" viewBox="0 0 24 24">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4 M7 10l5 5 5-5 M12 15V3" />
          </symbol>
          <symbol id="i-lock" viewBox="0 0 24 24">
            <path d="M5 11h14v10H5z M8 11V7a4 4 0 0 1 8 0v4" />
          </symbol>
          <symbol id="i-chevr" viewBox="0 0 24 24">
            <path d="M9 6l6 6-6 6" />
          </symbol>
          <symbol id="i-bell" viewBox="0 0 24 24">
            <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9z M13.7 21a2 2 0 0 1-3.4 0" />
          </symbol>
        </defs>
      </svg>

      <div className="course-mgmt-shell">
        {/* Main Workspace Area */}
        <div className="main">
          {/* Top bar with Breadcrumb & Bell */}
          <header className="top">
            <div className="crumb">
              <Link to="/courses" style={{ color: "#64748B", textDecoration: "none" }}>Course Management</Link>{" "}
              <svg className="ic sm">
                <use href="#i-chevr" />
              </svg>{" "}
              <b>Price Change History</b>
            </div>
            <div className="row">
              <button className="btn ico ghost" aria-label="Notifications" title="Notifications">
                <svg className="ic">
                  <use href="#i-bell" />
                </svg>
              </button>
            </div>
          </header>

          {/* Main Content */}
          <main className="content">
            <div className="ph">
              <div>
                <h1>Price Change History</h1>
                <p>An audit trail of every price change, with who made it and why.</p>
              </div>
              <div className="row">
                <button className="btn" onClick={handleExportCsv} title="Download CSV report">
                  <svg className="ic">
                    <use href="#i-dl" />
                  </svg>
                  Export CSV
                </button>
              </div>
            </div>

            {/* Filter Toolbar & Data Table Section */}
            <section className="card">
              <div className="toolbar">
                <div className="f" style={{ width: 230 }}>
                  <label className="lab" htmlFor="fc">
                    Course
                  </label>
                  <select
                    className="inp sel"
                    id="fc"
                    value={courseFilter}
                    onChange={(e) => {
                      setCourseFilter(e.target.value);
                      setPage(1);
                    }}
                  >
                    <option value="all">All courses</option>
                    {courses.map((c) => (
                      <option key={String(c.course_id)} value={String(c.course_id)}>
                        {c.course_title}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="f" style={{ width: 190 }}>
                  <label className="lab" htmlFor="fa">
                    Changed by
                  </label>
                  <select
                    className="inp sel"
                    id="fa"
                    value={adminFilter}
                    onChange={(e) => {
                      setAdminFilter(e.target.value);
                      setPage(1);
                    }}
                  >
                    <option value="all">All admins</option>
                    {availableAdmins.map((adm) => (
                      <option key={adm} value={adm}>
                        {adm}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="f" style={{ width: 160 }}>
                  <label className="lab" htmlFor="fd1">
                    From
                  </label>
                  <input
                    className="inp"
                    id="fd1"
                    type="date"
                    value={fromDate}
                    onChange={(e) => {
                      setFromDate(e.target.value);
                      setPage(1);
                    }}
                  />
                </div>

                <div className="f" style={{ width: 160 }}>
                  <label className="lab" htmlFor="fd2">
                    To
                  </label>
                  <input
                    className="inp"
                    id="fd2"
                    type="date"
                    value={toDate}
                    onChange={(e) => {
                      setToDate(e.target.value);
                      setPage(1);
                    }}
                  />
                </div>

                <div className="f">
                  <span className="lab">Price type</span>
                  <div className="seg">
                    <button
                      className={priceType === "All" ? "on" : ""}
                      onClick={() => {
                        setPriceType("All");
                        setPage(1);
                      }}
                      type="button"
                    >
                      All
                    </button>
                    <button
                      className={priceType === "Individual" ? "on" : ""}
                      onClick={() => {
                        setPriceType("Individual");
                        setPage(1);
                      }}
                      type="button"
                    >
                      Individual
                    </button>
                    <button
                      className={priceType === "Institutional" ? "on" : ""}
                      onClick={() => {
                        setPriceType("Institutional");
                        setPage(1);
                      }}
                      type="button"
                    >
                      Institutional
                    </button>
                  </div>
                </div>

                <button
                  className="btn ghost"
                  style={{ marginLeft: "auto" }}
                  onClick={handleClearFilters}
                  type="button"
                >
                  Clear filters
                </button>
              </div>

              {/* Data Table */}
              <div className="tw">
                <table>
                  <thead>
                    <tr>
                      <th>Course</th>
                      <th>Individual price</th>
                      <th>Institutional price (per student)</th>
                      <th>Changed by</th>
                      <th>Reason</th>
                      <th>Date and time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {isLoading ? (
                      <tr>
                        <td colSpan={6} style={{ textAlign: "center", padding: "40px 16px", color: "#64748B" }}>
                          Loading price change history...
                        </td>
                      </tr>
                    ) : audits.length === 0 ? (
                      <tr>
                        <td colSpan={6} style={{ textAlign: "center", padding: "40px 16px", color: "#64748B" }}>
                          No price change history found for the selected filters.
                        </td>
                      </tr>
                    ) : (
                      audits.map((item) => {
                        const badge = getCourseBadge(item.course_code, item.course_id);
                        const dt = formatDate(item.created_at);
                        const adminInitials = item.admin_name
                          ? item.admin_name
                              .split(" ")
                              .map((n) => n[0])
                              .join("")
                              .slice(0, 2)
                              .toUpperCase()
                          : "AD";

                        return (
                          <tr key={item.id || item.public_id}>
                            <td>
                              <div className="cell">
                                <span className={`th ${badge.cls}`}>{badge.code}</span>
                                <span className="strong">{item.course_title}</span>
                              </div>
                            </td>
                            <td>{renderIndividualDiff(item)}</td>
                            <td>{renderInstitutionalDiff(item)}</td>
                            <td>
                              <div className="cell">
                                <span className="av">{adminInitials}</span>
                                <div>
                                  {item.admin_name || item.admin_email}
                                  <div className="sub">{item.admin_role || "Admin"}</div>
                                </div>
                              </div>
                            </td>
                            <td>
                              {item.reason ? (
                                item.reason
                              ) : (
                                <span className="muted">No reason given</span>
                              )}
                            </td>
                            <td className="muted">
                              {dt.dateStr}
                              <div className="sub">{dt.timeStr}</div>
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              <div className="pager">
                <span>
                  Showing {audits.length ? (page - 1) * perPage + 1 : 0} to{" "}
                  {Math.min(page * perPage, totalCount)} of {totalCount} changes
                </span>
                <div className="row" style={{ gap: 6 }}>
                  <button
                    className="pg"
                    disabled={page <= 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    aria-label="Previous"
                    type="button"
                    style={{ opacity: page <= 1 ? 0.4 : 1, cursor: page <= 1 ? "default" : "pointer" }}
                  >
                    ‹
                  </button>
                  {Array.from({ length: totalPages }, (_, i) => i + 1).map((pNum) => (
                    <button
                      key={pNum}
                      className={`pg ${pNum === page ? "on" : ""}`}
                      onClick={() => setPage(pNum)}
                      type="button"
                    >
                      {pNum}
                    </button>
                  ))}
                  <button
                    className="pg"
                    disabled={page >= totalPages}
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    aria-label="Next"
                    type="button"
                    style={{ opacity: page >= totalPages ? 0.4 : 1, cursor: page >= totalPages ? "default" : "pointer" }}
                  >
                    ›
                  </button>
                </div>
              </div>
            </section>

            {/* Read-Only Notice Note */}
            <div
              className="note"
              style={{ background: "#F8FAFC", color: "#64748B", border: "1px solid #E2E8F0" }}
            >
              <svg className="ic">
                <use href="#i-lock" />
              </svg>
              <span>
                History is read-only. Entries cannot be edited or deleted, and each one records the admin who saved it.
              </span>
            </div>
          </main>
        </div>
      </div>
    </>
  );
}

export default PriceHistoryPage;

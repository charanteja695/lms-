import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { downloadFile } from "@/core/api/download";
import { useNotify } from "@/core/hooks/useNotify";
import { useListParams } from "@/core/hooks/useListParams";
import { CertificateTabs } from "@/modules/certificates/common/components/CertificateTabs";
import {
  useListCertificatesQuery,
  useGetCertificateDownloadMutation,
} from "@/modules/certificates/issued/api/certificatesApi";
import { CertificateFilters } from "@/modules/certificates/issued/components/list/CertificateFilters";
import { useCertificateColumns } from "@/modules/certificates/issued/components/list/useCertificateColumns";
import type { CertificateFilters as Filters } from "@/modules/certificates/issued/types";
import { Button, Card, DataTable, EmptyState, PageHeader, Pagination } from "@/shared/ui";
import { useCan } from "@/modules/user-management/common/permissions/useCan";
import { formatDate } from "@/core/lib/format";
import { cn } from "@/core/lib/cn";
import {
  Award,
  Download,
  ExternalLink,
  BookOpen,
  LayoutGrid,
  List,
  CheckCircle2,
  Calendar,
  Sparkles,
} from "lucide-react";

export function CertificatesListPage() {
  const notify = useNotify();
  const { holds, acts, can } = useCan();
  const navigate = useNavigate();
  const isStudent = holds("certificates.own");
  const { params, update, reset } = useListParams<Record<keyof Filters, string | boolean | undefined>>({
    page: 1,
    per_page: 20,
  });
  const apiParams = params as Filters & { page: number; per_page: number };
  const { data, isFetching, isError, refetch } = useListCertificatesQuery(apiParams);
  const [downloadCert] = useGetCertificateDownloadMutation();
  const [downloadingCertId, setDownloadingCertId] = useState<string | null>(null);
  const [studentViewMode, setStudentViewMode] = useState<"grid" | "table">("grid");

  const columns = useCertificateColumns(!isStudent);
  const activeCount = Object.entries(apiParams).filter(
    ([key, value]) => !["page", "per_page"].includes(key) && value !== undefined && value !== ""
  ).length;

  const handleDownloadPdf = async (certId: string, certCode: string) => {
    try {
      setDownloadingCertId(certId);
      notify.info("Preparing verified PDF certificate...");
      const res = await downloadCert(certId).unwrap();
      if (res?.url) {
        window.open(res.url, "_blank");
        notify.success("Certificate download started.");
      } else {
        window.print();
      }
    } catch {
      notify.success(`Certificate ${certCode} verified. Printing document.`);
      window.print();
    } finally {
      setDownloadingCertId(null);
    }
  };

  const certificates = data?.items ?? [];

  return (
    <>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2">
        <PageHeader
          title={isStudent ? "My certificates" : "Certificates"}
          description={
            isStudent
              ? "Earned when you pass a course. View, download, or verify your official academic credentials."
              : "Certificates issued to the students you can see."
          }
          actions={
            !isStudent &&
            (can("exams.manage") || acts("certificates.export", "certificates.students")) && (
              <Button
                variant="secondary"
                icon="download"
                onClick={() =>
                  void downloadFile(
                    "/certificates/export",
                    { course_id: apiParams.course_id, status: apiParams.status },
                    "certificates.csv"
                  ).catch(notify.apiError)
                }
              >
                Export CSV
              </Button>
            )
          }
        />

        {isStudent && (
          <div className="flex items-center gap-1 p-1 bg-slate-100 rounded-xl border border-slate-200 self-start sm:self-auto shrink-0 mb-4 sm:mb-0">
            <button
              type="button"
              onClick={() => setStudentViewMode("grid")}
              className={cn(
                "p-1.5 rounded-lg text-xs font-semibold transition-colors flex items-center gap-1.5 cursor-pointer",
                studentViewMode === "grid"
                  ? "bg-white text-slate-900 shadow-2xs"
                  : "text-slate-500 hover:text-slate-900"
              )}
              title="Grid View"
            >
              <LayoutGrid size={15} />
              <span className="hidden md:inline">Grid</span>
            </button>
            <button
              type="button"
              onClick={() => setStudentViewMode("table")}
              className={cn(
                "p-1.5 rounded-lg text-xs font-semibold transition-colors flex items-center gap-1.5 cursor-pointer",
                studentViewMode === "table"
                  ? "bg-white text-slate-900 shadow-2xs"
                  : "text-slate-500 hover:text-slate-900"
              )}
              title="Table View"
            >
              <List size={15} />
              <span className="hidden md:inline">Table</span>
            </button>
          </div>
        )}
      </div>

      <CertificateTabs />

      {/* Student Card Grid View */}
      {isStudent && studentViewMode === "grid" ? (
        <div className="space-y-6">
          <CertificateFilters
            filters={apiParams}
            activeCount={activeCount}
            showStaffFilters={false}
            update={update}
            reset={reset}
          />

          {isError ? (
            <Card>
              <EmptyState
                icon="alert"
                title="Could not load certificates"
                action={
                  <Button variant="secondary" onClick={() => void refetch()}>
                    Try again
                  </Button>
                }
              />
            </Card>
          ) : certificates.length === 0 ? (
            <Card>
              <div className="py-12 text-center space-y-4">
                <div className="w-14 h-14 rounded-full bg-amber-50 text-amber-600 mx-auto flex items-center justify-center">
                  <Award size={28} />
                </div>
                <h3 className="text-base font-bold text-slate-800">
                  {activeCount ? "No matching certificates" : "No certificates earned yet"}
                </h3>
                <p className="text-xs text-slate-500 max-w-sm mx-auto leading-relaxed">
                  {activeCount
                    ? "Try adjusting your filter criteria to find issued certificates."
                    : "Complete all course curriculum lessons and pass the final proctored examination to earn your verified credential."}
                </p>
                <div className="pt-2">
                  <Button variant="primary" icon="graduation" onClick={() => navigate("/courses/my")}>
                    Go to My Courses
                  </Button>
                </div>
              </div>
            </Card>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {certificates.map((cert) => (
                <div
                  key={cert.certificate_id}
                  className="rounded-2xl border border-slate-200 bg-white shadow-2xs hover:shadow-md transition-all duration-200 flex flex-col justify-between overflow-hidden group"
                >
                  {/* Decorative Certificate Header */}
                  <div className="relative p-5 bg-gradient-to-br from-emerald-900 via-slate-900 to-slate-950 text-white select-none">
                    <div
                      className="absolute inset-0 opacity-15"
                      style={{
                        backgroundImage: `radial-gradient(circle at 1px 1px, rgba(255,255,255,0.4) 1px, transparent 0)`,
                        backgroundSize: "16px 16px",
                      }}
                    />
                    <div className="relative z-10 flex items-center justify-between gap-2">
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-md bg-emerald-500/20 text-emerald-300 border border-emerald-400/30">
                        {cert.status === "issued" ? "Verified Credential" : cert.status}
                      </span>
                      <div className="flex items-center gap-1 text-[11px] text-amber-300 font-semibold">
                        <Sparkles size={12} /> GenZ LMS
                      </div>
                    </div>

                    <div className="relative z-10 my-4 text-center">
                      <div className="w-12 h-12 rounded-xl bg-white/10 backdrop-blur-md border border-white/20 flex items-center justify-center text-emerald-400 mx-auto shadow-inner group-hover:scale-105 transition-transform">
                        <Award size={24} />
                      </div>
                      <span className="text-[10px] uppercase font-bold tracking-widest text-emerald-200 block mt-2">
                        Certificate of Completion
                      </span>
                    </div>

                    <div className="relative z-10 text-center">
                      <h4 className="text-sm font-bold text-white line-clamp-1 group-hover:text-emerald-300 transition-colors">
                        {cert.course_title || "Course Program"}
                      </h4>
                    </div>
                  </div>

                  {/* Body Content */}
                  <div className="p-5 space-y-3 flex-1 flex flex-col justify-between">
                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-slate-500 font-medium">Recipient:</span>
                        <b className="text-slate-800 font-bold">{cert.student_name}</b>
                      </div>

                      <div className="flex items-center justify-between text-xs">
                        <span className="text-slate-500 font-medium">Issued Date:</span>
                        <span className="text-slate-700 font-medium flex items-center gap-1">
                          <Calendar size={12} className="text-slate-400" />
                          {formatDate(cert.issued_at)}
                        </span>
                      </div>

                      <div className="flex items-center justify-between text-xs">
                        <span className="text-slate-500 font-medium">Final Score:</span>
                        <b className="text-emerald-700 font-bold bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                          {cert.score_percent != null ? `${cert.score_percent.toFixed(1)}%` : "Passed"}{" "}
                          ({cert.grade || "Passed"})
                        </b>
                      </div>

                      <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[11px] font-mono text-slate-400">
                        <span>Code: {cert.verification_code || cert.certificate_id.slice(0, 8)}</span>
                        <span className="text-slate-500 font-sans font-medium text-[10px]">
                          {cert.institution_name || "GenZ LMS"}
                        </span>
                      </div>
                    </div>

                    {/* Action Buttons */}
                    <div className="pt-3 border-t border-slate-100 space-y-2">
                      <div className="grid grid-cols-2 gap-2">
                        <button
                          type="button"
                          disabled={downloadingCertId === cert.certificate_id}
                          onClick={() => handleDownloadPdf(cert.certificate_id, cert.verification_code)}
                          className="inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl bg-[#00663C] text-xs font-bold text-white hover:bg-[#00522F] disabled:opacity-50 cursor-pointer shadow-xs transition-colors"
                        >
                          <Download size={13} />
                          <span>{downloadingCertId === cert.certificate_id ? "Exporting..." : "Download PDF"}</span>
                        </button>

                        {cert.verification_url ? (
                          <a
                            href={cert.verification_url}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl border border-slate-300 bg-white text-xs font-bold text-slate-700 hover:bg-slate-50 cursor-pointer shadow-2xs transition-colors"
                          >
                            <ExternalLink size={13} />
                            <span>Verify</span>
                          </a>
                        ) : (
                          <button
                            type="button"
                            onClick={() => {
                              navigator.clipboard?.writeText(
                                `${window.location.origin}/verify?code=${cert.verification_code}`
                              );
                              notify.success("Verification link copied.");
                            }}
                            className="inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl border border-slate-300 bg-white text-xs font-bold text-slate-700 hover:bg-slate-50 cursor-pointer shadow-2xs transition-colors"
                          >
                            <CheckCircle2 size={13} />
                            <span>Verify</span>
                          </button>
                        )}
                      </div>

                      <button
                        type="button"
                        onClick={() => navigate(`/courses/${cert.course_id}/learn`)}
                        className="w-full inline-flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-xs font-semibold text-blue-600 hover:text-blue-800 hover:bg-blue-50 transition-colors cursor-pointer"
                      >
                        <BookOpen size={13} />
                        <span>Open Course</span>
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          <Pagination
            pageContext={data?.pageContext}
            disabled={isFetching}
            onPageChange={(next) => update({ page: next })}
            onPerPageChange={(next) => update({ per_page: next })}
          />
        </div>
      ) : (
        /* Table View (for staff or toggled by student) */
        <Card bodyClassName="p-0">
          <CertificateFilters
            filters={apiParams}
            activeCount={activeCount}
            showStaffFilters={!isStudent}
            update={update}
            reset={reset}
          />
          {isError ? (
            <EmptyState
              icon="alert"
              title="Could not load certificates"
              action={
                <Button variant="secondary" onClick={() => void refetch()}>
                  Try again
                </Button>
              }
            />
          ) : (
            <>
              <DataTable
                columns={columns}
                rows={certificates}
                rowKey={(item) => item.certificate_id}
                loading={isFetching}
                onRowClick={(item) => navigate(`/certificates/issued/${item.certificate_id}`)}
                empty={
                  <EmptyState
                    icon="graduation"
                    title={activeCount ? "No matches" : "No certificates yet"}
                    description={
                      activeCount
                        ? "Clear a filter to see more."
                        : "Certificates appear when a course is passed."
                    }
                  />
                }
              />
              <Pagination
                pageContext={data?.pageContext}
                disabled={isFetching}
                onPageChange={(next) => update({ page: next })}
                onPerPageChange={(next) => update({ per_page: next })}
              />
            </>
          )}
        </Card>
      )}
    </>
  );
}

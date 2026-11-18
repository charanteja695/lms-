import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { cn } from "@/core/lib/cn";
import { useGetResultsSummaryQuery } from "@/modules/assessments/results/api/resultsApi";
import { useGetAcademicsQuery, useGetSectionStudentsQuery } from "@/modules/user-management/academics/api/academicsApi";
import { useAuth } from "@/modules/user-management/auth/hooks/useAuth";
import { useInstitutionOptions } from "@/modules/user-management/common/hooks/useEntityOptions";
import { Button, Card, EmptyState, EntityPicker, Field, Icon, Input, PageHeader, Select, Spinner, StatTile } from "@/shared/ui";

/** A section's marks: one row per student, one column per test (best score, pass or not, attempts). */
export function ResultsPage() {
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const own = user?.institution?.organization_id;
  const organizationId = own ?? params.get("organization_id") ?? "";
  const { data: structure } = useGetAcademicsQuery(organizationId, { skip: !organizationId });
  const sections = useMemo(
    () => (structure?.departments ?? []).flatMap((d) => d.programs.flatMap((p) => p.sections.map((s) => ({ value: s.section_id, label: `${s.label} · ${d.code}` })))),
    [structure],
  );
  const [sectionId, setSectionId] = useState("");
  const chosen = sectionId || sections[0]?.value || "";
  const { data: roster, isFetching: loadingRoster } = useGetSectionStudentsQuery({ organizationId, sectionId: chosen }, { skip: !organizationId || !chosen });
  const userIds = useMemo(() => (roster?.students ?? []).map((s) => s.user_id), [roster]);
  const { data: results, isFetching: loadingResults } = useGetResultsSummaryQuery({ user_ids: userIds }, { skip: userIds.length === 0 });

  // Filtering & search
  const [search, setSearch] = useState("");

  const cell = useMemo(() => new Map((results?.rows ?? []).map((r) => [`${r.user_id}:${r.test_id}`, r])), [results]);
  const tests = results?.tests ?? [];
  const attempted = new Set((results?.rows ?? []).map((r) => r.user_id)).size;
  const passes = (results?.rows ?? []).filter((r) => r.passed).length;
  const average = results?.rows.length ? Math.round(results.rows.reduce((sum, r) => sum + (r.best_percent ?? 0), 0) / results.rows.length) : null;

  const filteredStudents = useMemo(() => {
    const list = roster?.students ?? [];
    if (!search.trim()) return list;
    const q = search.toLowerCase();
    return list.filter(
      (s) =>
        s.full_name.toLowerCase().includes(q) ||
        (s.admission_number && s.admission_number.toLowerCase().includes(q)) ||
        (s.email && s.email.toLowerCase().includes(q)),
    );
  }, [roster, search]);

  const handleExportCSV = () => {
    if (!filteredStudents.length || !tests.length) return;
    const headers = ["Student Name", "Admission Number", ...tests.map((t) => `${t.title} (%)`), "Overall Status"];
    const rows = filteredStudents.map((s) => {
      const studentScores = tests.map((t) => {
        const r = cell.get(`${s.user_id}:${t.test_id}`);
        return r ? `${r.best_percent != null ? Math.round(r.best_percent) + "%" : "Pending"} (${r.passed ? "Pass" : "Fail"})` : "Not taken";
      });
      const hasFailed = tests.some((t) => {
        const r = cell.get(`${s.user_id}:${t.test_id}`);
        return r && !r.passed;
      });
      const overall = hasFailed ? "Needs Improvement" : "Good Standing";
      return [
        `"${s.full_name.replace(/"/g, '""')}"`,
        `"${s.admission_number || ""}"`,
        ...studentScores.map((score) => `"${score}"`),
        `"${overall}"`,
      ].join(",");
    });

    const csvContent = "data:text/csv;charset=utf-8," + [headers.join(","), ...rows].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `marks_results_section_${chosen}_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <>
      <PageHeader
        title="Marks & Results"
        description="Comprehensive evaluation metrics and test scores across batches and academic sections."
        actions={
          filteredStudents.length > 0 && tests.length > 0 ? (
            <Button variant="secondary" icon="download" onClick={handleExportCSV}>
              Export Results (CSV)
            </Button>
          ) : undefined
        }
      />
      <Card className="mb-6">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {!own && (
            <EntityPicker
              label="Institution"
              value={organizationId}
              selectedLabel={params.get("organization_label") ?? undefined}
              useOptions={useInstitutionOptions}
              onChange={(id, label) => {
                setSectionId("");
                setParams(id ? { organization_id: id, organization_label: label } : {});
              }}
            />
          )}
          <Field label="Section">
            {(p) => (
              <Select
                {...p}
                value={chosen}
                disabled={sections.length === 0}
                placeholder={sections.length ? undefined : "No sections yet"}
                options={sections}
                onChange={(e) => setSectionId(e.target.value)}
              />
            )}
          </Field>

          {userIds.length > 0 && (
            <Field label="Search Student">
              {(p) => (
                <div className="relative">
                  <Input
                    {...p}
                    placeholder="Search name or ID..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="pl-8"
                  />
                  <div className="absolute left-2.5 top-2.5 text-slate-400">
                    <Icon name="search" size={15} />
                  </div>
                </div>
              )}
            </Field>
          )}
        </div>
      </Card>

      {!organizationId ? (
        <EmptyState icon="building" title="Choose an institution" />
      ) : sections.length === 0 ? (
        <EmptyState icon="layers" title="No sections yet" description="Set up departments, programs and sections under Academic structure first." />
      ) : loadingRoster || loadingResults ? (
        <div className="flex justify-center py-20"><Spinner /></div>
      ) : userIds.length === 0 ? (
        <EmptyState icon="users" title="No students in this section" description="Place students in it under Academic structure." />
      ) : (
        <>
          <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
            <StatTile icon="users" label="Total Students" value={userIds.length} />
            <StatTile icon="fileText" label="Attempted Tests" value={attempted} />
            <StatTile icon="check" label="Passing Submissions" value={passes} />
            <StatTile icon="chart" label="Average Best Score" value={average == null ? "—" : `${average}%`} />
          </div>
          {tests.length === 0 ? (
            <EmptyState icon="fileText" title="No test results yet" description="Results appear here once these students submit a test." />
          ) : filteredStudents.length === 0 ? (
            <EmptyState
              icon="search"
              title="No students match search"
              description="Try adjusting your search criteria."
              action={<Button variant="secondary" onClick={() => setSearch("")}>Clear Search</Button>}
            />
          ) : (
            <div className="overflow-x-auto rounded-2xl border border-slate-200/80 bg-white shadow-card">
              <table className="w-full min-w-max text-sm">
                <thead>
                  <tr className="border-b border-slate-100 bg-slate-50/70 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                    <th className="sticky left-0 z-10 bg-slate-50 px-4 py-3">Student</th>
                    {tests.map((t) => (
                      <th key={t.test_id} className="px-4 py-3" title={`Pass mark ${t.pass_mark_percent}%`}>
                        <span className="block max-w-48 truncate normal-case tracking-normal text-navy-950">{t.title}</span>
                        <span className="block font-normal normal-case tracking-normal text-slate-500">pass {t.pass_mark_percent}%</span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredStudents.map((s) => (
                    <tr key={s.user_id} className="hover:bg-slate-50/50 transition-colors">
                      <td className="sticky left-0 z-10 bg-white px-4 py-3">
                        <span className="block font-semibold text-navy-950">{s.full_name}</span>
                        <span className="block text-xs text-slate-500">{s.admission_number || s.email}</span>
                      </td>
                      {tests.map((t) => {
                        const r = cell.get(`${s.user_id}:${t.test_id}`);
                        return (
                          <td key={t.test_id} className="px-4 py-3">
                            {r ? (
                              <span className="inline-flex items-center gap-2">
                                <span className={cn("rounded-md px-2 py-0.5 text-xs font-bold tabular-nums ring-1", r.passed ? "bg-brand-50 text-brand-700 ring-brand-100" : "bg-accent-50 text-accent-700 ring-accent-100")}>
                                  {r.best_percent == null ? "Pending" : `${Math.round(r.best_percent)}%`}
                                </span>
                                <span className="text-xs text-slate-500">{r.attempts} try{r.attempts === 1 ? "" : "s"}</span>
                              </span>
                            ) : (
                              <span className="text-xs text-slate-400">Not taken</span>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </>
  );
}

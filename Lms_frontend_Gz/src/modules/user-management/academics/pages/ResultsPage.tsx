import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { cn } from "@/core/lib/cn";
import { useGetResultsSummaryQuery } from "@/modules/assessments/results/api/resultsApi";
import { useGetAcademicsQuery, useGetSectionStudentsQuery } from "@/modules/user-management/academics/api/academicsApi";
import { useAuth } from "@/modules/user-management/auth/hooks/useAuth";
import { useInstitutionOptions } from "@/modules/user-management/common/hooks/useEntityOptions";
import { Card, EmptyState, EntityPicker, Field, PageHeader, Select, Spinner, StatTile } from "@/shared/ui";

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
  const userIds = (roster?.students ?? []).map((s) => s.user_id);
  const { data: results, isFetching: loadingResults } = useGetResultsSummaryQuery({ user_ids: userIds }, { skip: userIds.length === 0 });

  const cell = new Map((results?.rows ?? []).map((r) => [`${r.user_id}:${r.test_id}`, r]));
  const tests = results?.tests ?? [];
  const attempted = new Set((results?.rows ?? []).map((r) => r.user_id)).size;
  const passes = (results?.rows ?? []).filter((r) => r.passed).length;
  const average = results?.rows.length ? Math.round(results.rows.reduce((sum, r) => sum + (r.best_percent ?? 0), 0) / results.rows.length) : null;

  return (
    <>
      <PageHeader title="Marks & results" description="Each student's best score on every test, section by section." />
      <Card className="mb-6">
        <div className="grid gap-4 sm:grid-cols-2">
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
            {(p) => <Select {...p} value={chosen} disabled={sections.length === 0} placeholder={sections.length ? undefined : "No sections yet"} options={sections} onChange={(e) => setSectionId(e.target.value)} />}
          </Field>
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
            <StatTile icon="users" label="Students" value={userIds.length} />
            <StatTile icon="fileText" label="Took a test" value={attempted} />
            <StatTile icon="check" label="Passes" value={passes} />
            <StatTile icon="chart" label="Average best score" value={average == null ? "—" : `${average}%`} />
          </div>
          {tests.length === 0 ? (
            <EmptyState icon="fileText" title="No test results yet" description="Results appear here once these students submit a test." />
          ) : (
            <div className="overflow-x-auto rounded-2xl border border-slate-200/80 bg-white shadow-card">
              <table className="w-full min-w-max text-sm">
                <thead>
                  <tr className="border-b border-slate-100 bg-slate-50/70 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                    <th className="sticky left-0 z-10 bg-slate-50 px-4 py-3">Student</th>
                    {tests.map((t) => (
                      <th key={t.test_id} className="px-4 py-3" title={`Pass mark ${t.pass_mark_percent}%`}>
                        <span className="block max-w-48 truncate normal-case tracking-normal text-navy-950">{t.title}</span>
                        <span className="block font-normal normal-case tracking-normal">pass {t.pass_mark_percent}%</span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {(roster?.students ?? []).map((s) => (
                    <tr key={s.user_id}>
                      <td className="sticky left-0 z-10 bg-white px-4 py-3">
                        <span className="block font-semibold text-navy-950">{s.full_name}</span>
                        <span className="block text-xs text-slate-500">{s.admission_number}</span>
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

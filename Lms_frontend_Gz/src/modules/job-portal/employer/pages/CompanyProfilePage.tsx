import { useEffect, useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { JobTabs } from "@/modules/job-portal/common/components/JobTabs";
import { EmployerStatusBadge } from "@/modules/job-portal/common/components/JobBadges";
import { useJobRights } from "@/modules/job-portal/common/hooks/useJobRights";
import { COMPANY_SIZES } from "@/modules/job-portal/common/labels";
import { useGetMyCompanyQuery, useSubmitMyCompanyMutation, useUpdateMyCompanyMutation } from "@/modules/job-portal/employer/api/employerJobsApi";
import { Alert, Button, Card, EmptyState, Field, Input, PageHeader, PageLoader, Select, Textarea } from "@/shared/ui";

/** The company's public profile. Jobs go live only once a careers manager verifies it; only the company admin edits it. */
export function CompanyProfilePage() {
  const notify = useNotify();
  const { isEmployerAdmin } = useJobRights();
  const { data: company, isLoading, isError } = useGetMyCompanyQuery();
  const [update, { isLoading: saving }] = useUpdateMyCompanyMutation();
  const [submit, { isLoading: submitting }] = useSubmitMyCompanyMutation();
  const [form, setForm] = useState({ about: "", website: "", industry: "", company_size: "", headquarters: "" });

  useEffect(() => {
    if (company) setForm({ about: company.about ?? "", website: company.website ?? "", industry: company.industry ?? "", company_size: company.company_size ?? "", headquarters: company.headquarters ?? "" });
  }, [company]);

  if (isLoading) return <PageLoader />;
  if (isError || !company) return <EmptyState icon="alert" title="Could not load the company profile" />;
  const set = (key: keyof typeof form) => (value: string) => setForm((current) => ({ ...current, [key]: value }));
  const editable = isEmployerAdmin && company.status !== "pending" && company.status !== "suspended";

  const save = async () => {
    try {
      await update({ about: form.about || null, website: form.website || null, industry: form.industry || null, company_size: form.company_size || null, headquarters: form.headquarters || null }).unwrap();
      notify.success("Profile saved");
    } catch (error) {
      notify.apiError(error);
    }
  };

  return (
    <>
      <PageHeader title="Jobs" description={`${company.company_name} · company profile`} actions={<EmployerStatusBadge status={company.status} />} />
      <JobTabs />
      <div className="space-y-4">
        {company.status === "draft" && <Alert tone="info" title="Not verified yet">Fill in about, website and industry, then submit. Jobs go live once a careers manager verifies the company.</Alert>}
        {company.status === "pending" && <Alert tone="warning" title="Waiting for verification" />}
        {company.status === "rejected" && <Alert tone="error" title="Verification was refused">{company.review_note}</Alert>}
        {company.status === "suspended" && <Alert tone="error" title="Suspended — open jobs are paused">{company.review_note}</Alert>}
        <Card title="About the company">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="About" className="sm:col-span-2">{(p) => <Textarea {...p} rows={5} maxLength={4000} disabled={!editable} value={form.about} onChange={(e) => set("about")(e.target.value)} />}</Field>
            <Field label="Website">{(p) => <Input {...p} disabled={!editable} value={form.website} placeholder="https://" onChange={(e) => set("website")(e.target.value)} />}</Field>
            <Field label="Industry">{(p) => <Input {...p} disabled={!editable} maxLength={100} value={form.industry} onChange={(e) => set("industry")(e.target.value)} />}</Field>
            <Field label="Company size">{(p) => <Select {...p} disabled={!editable} value={form.company_size} placeholder="Choose" options={COMPANY_SIZES.map((s) => ({ value: s, label: `${s} people` }))} onChange={(e) => set("company_size")(e.target.value)} />}</Field>
            <Field label="Headquarters">{(p) => <Input {...p} disabled={!editable} maxLength={120} value={form.headquarters} onChange={(e) => set("headquarters")(e.target.value)} />}</Field>
          </div>
          {editable && (
            <div className="mt-4 flex justify-end gap-2">
              <Button variant="secondary" loading={saving} onClick={() => void save()}>Save</Button>
              {(company.status === "draft" || company.status === "rejected") && (
                <Button loading={submitting} onClick={async () => { await save(); await submit().unwrap().then(() => notify.success("Submitted for verification"), notify.apiError); }}>Submit for verification</Button>
              )}
            </div>
          )}
          {!isEmployerAdmin && <p className="mt-3 text-xs text-slate-500">Only your company's admin can change this.</p>}
        </Card>
      </div>
    </>
  );
}

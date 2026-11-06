import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { useNotify } from "@/core/hooks/useNotify";
import { EmployerStatusBadge } from "@/modules/job-portal/common/components/JobBadges";
import { COMPANY_SIZES } from "@/modules/job-portal/common/labels";
import { useGetCompanyHiringProfileQuery, useKeepCompanyProfileMutation } from "@/modules/job-portal/admin/api/companyProfileApi";
import { Button, Card, Field, Input, Select, Textarea } from "@/shared/ui";

const EMPTY = { about: "", website: "", industry: "", company_size: "", headquarters: "" };

/**
 * The company's hiring profile, kept by the super admin (companies have no logins). Saving it complete verifies the
 * company, so its jobs can go live; then post its jobs from Jobs.
 */
export function CompanyHiringProfileCard({ organizationId, industry }: { organizationId: string; industry?: string | null }) {
  const notify = useNotify();
  const { data: company, isFetching } = useGetCompanyHiringProfileQuery(organizationId);
  const [keep, { isLoading: saving }] = useKeepCompanyProfileMutation();
  const [form, setForm] = useState(EMPTY);

  useEffect(() => {
    setForm(
      company
        ? { about: company.about ?? "", website: company.website ?? "", industry: company.industry ?? "", company_size: company.company_size ?? "", headquarters: company.headquarters ?? "" }
        : { ...EMPTY, industry: industry ?? "" },
    );
  }, [company, industry]);

  const set = (key: keyof typeof form) => (value: string) => setForm((current) => ({ ...current, [key]: value }));
  const save = () =>
    keep({
      organizationId,
      body: { about: form.about || null, website: form.website || null, industry: form.industry || null, company_size: form.company_size || null, headquarters: form.headquarters || null },
    })
      .unwrap()
      .then(() => notify.success("Hiring profile saved", "The company is verified: its jobs can go live."), notify.apiError);

  const verified = company?.status === "verified";
  return (
    <Card
      title="Hiring profile"
      actions={company ? <EmployerStatusBadge status={company.status} /> : undefined}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="About" required className="sm:col-span-2">{(p) => <Textarea {...p} rows={4} maxLength={2000} value={form.about} onChange={(e) => set("about")(e.target.value)} />}</Field>
        <Field label="Website" required>{(p) => <Input {...p} value={form.website} placeholder="https://" onChange={(e) => set("website")(e.target.value)} />}</Field>
        <Field label="Industry" required>{(p) => <Input {...p} maxLength={100} value={form.industry} onChange={(e) => set("industry")(e.target.value)} />}</Field>
        <Field label="Company size">{(p) => <Select {...p} value={form.company_size} placeholder="Choose" options={COMPANY_SIZES.map((s) => ({ value: s, label: `${s} people` }))} onChange={(e) => set("company_size")(e.target.value)} />}</Field>
        <Field label="Headquarters">{(p) => <Input {...p} maxLength={120} value={form.headquarters} onChange={(e) => set("headquarters")(e.target.value)} />}</Field>
      </div>
      <div className="mt-5 flex flex-wrap items-center justify-end gap-2">
        {verified && (
          <Link to={`/jobs/employer?employer_org_id=${organizationId}`} className="mr-auto text-sm font-semibold text-brand-700 hover:text-brand-800">
            {company.open_jobs} open job{company.open_jobs === 1 ? "" : "s"} · see its jobs
          </Link>
        )}
        <Button loading={saving} disabled={isFetching} onClick={() => void save()}>{verified ? "Save" : "Save and verify"}</Button>
      </div>
    </Card>
  );
}

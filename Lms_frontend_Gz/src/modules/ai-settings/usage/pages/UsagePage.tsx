import { useState } from "react";

import { AiTabs } from "@/modules/ai-settings/common/components/AiTabs";
import { useAiRights } from "@/modules/ai-settings/common/hooks/useAiRights";
import { QuotaForm } from "@/modules/ai-settings/usage/components/QuotaForm";
import { UsageMeters } from "@/modules/ai-settings/usage/components/UsageMeters";
import { useGetAiQuotaQuery, useGetAiUsageQuery } from "@/modules/ai-settings/usage/api/usageApi";
import { useAnyInstitutionOptions } from "@/modules/user-management/common/hooks/useDirectoryOptions";
import { Alert, Card, EmptyState, EntityPicker, Field, Input, PageHeader, PageLoader } from "@/shared/ui";

const thisMonth = () => new Date().toISOString().slice(0, 7);

/** An organisation's AI usage this month against its limits. AI managers pick any institution and edit the limits. */
export function UsagePage() {
  const { isManager, ownOrganizationId } = useAiRights();
  const [picked, setPicked] = useState<{ id: string; label: string } | null>(null);
  const [period, setPeriod] = useState(thisMonth);
  const organizationId = isManager ? (picked?.id ?? ownOrganizationId ?? "") : (ownOrganizationId ?? "");
  const usage = useGetAiUsageQuery({ organizationId, period }, { skip: !organizationId });
  const quota = useGetAiQuotaQuery(organizationId, { skip: !organizationId || !isManager });

  const month = <Field label="Month">{(p) => <Input {...p} type="month" value={period} max={thisMonth()} onChange={(e) => setPeriod(e.target.value || thisMonth())} />}</Field>;

  return (
    <>
      {isManager ? (
        <>
          <PageHeader title="AI usage & settings" description="How much AI each organisation uses, and the limits that keep it in budget." />
          <AiTabs />
          <Card className="mb-6" bodyClassName="grid gap-4 sm:grid-cols-[1fr_12rem]">
            <EntityPicker label="Institution" value={picked?.id ?? ""} selectedLabel={picked?.label} placeholder="Search institutions…" useOptions={useAnyInstitutionOptions} onChange={(id, label) => setPicked(id ? { id, label } : null)} />
            {month}
          </Card>
        </>
      ) : (
        <PageHeader title="AI usage" description="Your institution's AI use this month. The platform team sets the limits." actions={<div className="w-48">{month}</div>} />
      )}

      {!organizationId ? (
        <Card><EmptyState icon="sparkles" title="Choose an institution" description="Its AI usage and limits appear here." /></Card>
      ) : usage.isLoading ? (
        <PageLoader />
      ) : usage.isError || !usage.data ? (
        <Alert tone="error">Could not load the usage. Try again in a moment.</Alert>
      ) : (
        <div className="space-y-6">
          <UsageMeters usage={usage.data} />
          {isManager && quota.data && <QuotaForm key={organizationId} quota={quota.data} />}
        </div>
      )}
    </>
  );
}

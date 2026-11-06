import { useParams } from "react-router-dom";

import { formatDateTime } from "@/core/lib/format";
import { CourseTitleCell } from "@/modules/catalog/common/components/CourseTitleCell";
import { TemplateStatusBadge } from "@/modules/certificates/common/components/StatusBadges";
import { useGetTemplateQuery } from "@/modules/certificates/templates/api/templatesApi";
import { TemplateLifecycleActions } from "@/modules/certificates/templates/components/TemplateLifecycleActions";
import { useTemplateRights } from "@/modules/certificates/templates/hooks/useTemplateRights";
import { Card, DescriptionList, EmptyState, PageHeader, PageLoader } from "@/shared/ui";

export function TemplateDetailPage() {
  const { templateId = "" } = useParams();
  const { canAuthor, canPublish } = useTemplateRights();
  const { data: template, isLoading, isError } = useGetTemplateQuery(templateId, { skip: !templateId });

  if (isLoading) return <PageLoader />;
  if (isError || !template) return <EmptyState icon="alert" title="Template not found" />;

  return (
    <>
      <PageHeader
        title={template.name}
        backTo="/certificates/templates"
        backLabel="Templates"
        actions={<TemplateLifecycleActions template={template} canAuthor={canAuthor} canPublish={canPublish} />}
      />
      <div className="space-y-4">
        <Card title="Template">
          <DescriptionList
            items={[
              { label: "Course", value: template.course_id ? <CourseTitleCell courseId={template.course_id} /> : "Platform default" },
              { label: "Status", value: <TemplateStatusBadge status={template.status} /> },
              { label: "Updated", value: formatDateTime(template.updated_at) },
              { label: "Activated", value: template.activated_at ? formatDateTime(template.activated_at) : null },
              {
                label: "Accent colour",
                value: (
                  <span className="flex items-center gap-2">
                    <span className="h-4 w-4 rounded border border-slate-200" style={{ backgroundColor: template.accent_color }} />
                    {template.accent_color}
                  </span>
                ),
              },
            ]}
          />
        </Card>
        <Card title="Wording">
          <DescriptionList
            columns={1}
            items={[
              { label: "Title", value: template.title_text },
              { label: "Body", value: <span className="whitespace-pre-wrap">{template.body_text}</span> },
              { label: "Footer", value: template.footer_text },
            ]}
          />
        </Card>
        <Card title="Signatories and grades">
          <DescriptionList
            items={[
              { label: "Signatories", value: template.signatories.length ? template.signatories.map((s) => (s.title ? `${s.name} (${s.title})` : s.name)).join(", ") : "Issuer only" },
              { label: "Grade bands", value: template.grade_bands.map((band) => `${band.label} ≥ ${band.min_percent}%`).join(", ") },
            ]}
          />
        </Card>
      </div>
    </>
  );
}

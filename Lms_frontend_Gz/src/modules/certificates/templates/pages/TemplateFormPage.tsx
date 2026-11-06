import { useMemo } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";

import { useNotify } from "@/core/hooks/useNotify";
import { useCourseTitle } from "@/modules/catalog/common/hooks/useCourseTitle";
import { useCreateTemplateMutation, useGetTemplateQuery, useUpdateTemplateMutation } from "@/modules/certificates/templates/api/templatesApi";
import { TemplateForm } from "@/modules/certificates/templates/components/form/TemplateForm";
import { emptyTemplateForm, templateToForm, toTemplateCreateBody, toTemplateUpdateBody } from "@/modules/certificates/templates/form/templateForm";
import { useTemplateFormErrors } from "@/modules/certificates/templates/hooks/useTemplateFormErrors";
import type { CertificateTemplate } from "@/modules/certificates/templates/types";
import { EmptyState, PageHeader, PageLoader } from "@/shared/ui";

/** Create (optionally copied from an existing template, passed in router state) or edit a draft. */
export function TemplateFormPage() {
  const { templateId } = useParams();
  const isEdit = Boolean(templateId);
  const location = useLocation();
  const navigate = useNavigate();
  const notify = useNotify();
  const copyFrom = (location.state as { copyFrom?: CertificateTemplate } | null)?.copyFrom;
  const { data: existing, isLoading, isError } = useGetTemplateQuery(templateId ?? "", { skip: !isEdit });
  const source = existing ?? copyFrom;
  const { title: courseTitle, isFetching: courseLoading } = useCourseTitle(source?.course_id ?? "");
  const [create, { isLoading: creating }] = useCreateTemplateMutation();
  const [update, { isLoading: updating }] = useUpdateTemplateMutation();
  const { formError, setFormError, handle } = useTemplateFormErrors();

  const defaults = useMemo(() => {
    if (!source) return emptyTemplateForm();
    const values = templateToForm(source, courseTitle ?? source.course_id ?? "");
    return isEdit ? values : { ...values, name: `${values.name} (copy)` };
  }, [source, courseTitle, isEdit]);

  if (isEdit && isLoading) return <PageLoader />;
  if (isEdit && (isError || !existing)) return <EmptyState icon="alert" title="Template not found" />;
  if (source?.course_id && courseLoading && !courseTitle) return <PageLoader />;

  return (
    <>
      <PageHeader title={isEdit ? `Edit ${existing?.name}` : "New template"} backTo="/certificates/templates" backLabel="Templates" />
      <TemplateForm
        key={source?.template_id ?? "new"}
        defaultValues={defaults}
        isEdit={isEdit}
        submitting={creating || updating}
        formError={formError}
        onCancel={() => navigate(-1)}
        onSubmit={async (values, form) => {
          setFormError(null);
          try {
            const saved = isEdit && templateId
              ? await update({ templateId, body: toTemplateUpdateBody(values) }).unwrap()
              : await create(toTemplateCreateBody(values)).unwrap();
            notify.success(isEdit ? "Template saved" : "Draft created", isEdit ? undefined : "Preview it, then ask a reviewer to activate it.");
            navigate(`/certificates/templates/${saved.template_id}`, { replace: true });
          } catch (error) {
            handle(error, form.setError);
          }
        }}
      />
    </>
  );
}

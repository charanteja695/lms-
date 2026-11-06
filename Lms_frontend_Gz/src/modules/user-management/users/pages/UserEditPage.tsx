import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { useNotify } from "@/core/hooks/useNotify";
import { useGetUserQuery, type UserResource, useUpdateUserMutation } from "@/modules/user-management/users/api/usersApi";
import { UserForm } from "@/modules/user-management/users/components/form/UserForm";
import { toUpdateBody } from "@/modules/user-management/users/form/userFormBody";
import { userToForm } from "@/modules/user-management/users/form/userFormDefaults";
import { SubmitHandler, useServerErrorHandler } from "@/modules/user-management/users/hooks/useUserFormErrors";
import { Button, EmptyState, PageHeader, PageLoader } from "@/shared/ui";

export function UserEditPage({ resource }: { resource: UserResource }) {
  const { userId = "" } = useParams();
  const navigate = useNavigate();
  const notify = useNotify();
  const { data: user, isLoading, isError } = useGetUserQuery({ resource, userId });
  const [updateUser, { isLoading: saving }] = useUpdateUserMutation();
  const [formError, setFormError] = useState<string | null>(null);
  const handleError = useServerErrorHandler(setFormError);
  const initial = useMemo(() => (user ? userToForm(user) : null), [user]);

  if (isLoading) return <PageLoader />;
  if (isError || !user || !initial) return <EmptyState icon="alert" title="User not found" action={<Button onClick={() => navigate(`/${resource}`)}>Back to list</Button>} />;

  const onSubmit: SubmitHandler = async (values, form, options) => {
    setFormError(null);
    const body = toUpdateBody(initial, values, options);
    if (Object.keys(body).length === 0) {
      notify.info("No changes to save");
      return;
    }
    try {
      await updateUser({ resource, userId, body }).unwrap();
      notify.success(
        "Changes saved",
        body.role || body.organization_id || body.scopes ? "The user was signed out because their access changed." : undefined,
      );
      navigate(`/${resource}/${userId}`, { replace: true });
    } catch (error) {
      handleError(error, form);
    }
  };

  return (
    <>
      <PageHeader title={`Edit ${user.personal_info.full_name}`} backTo={`/${resource}/${userId}`} backLabel="Profile" />
      <UserForm
        mode="edit"
        defaultValues={initial}
        userId={userId}
        submitting={saving}
        formError={formError}
        onSubmit={onSubmit}
        onCancel={() => navigate(`/${resource}/${userId}`)}
      />
    </>
  );
}

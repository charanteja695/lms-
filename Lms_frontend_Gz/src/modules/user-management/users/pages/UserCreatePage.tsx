import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useNotify } from "@/core/hooks/useNotify";
import { useAuth } from "@/modules/user-management/auth/hooks/useAuth";
import { useCreateUserMutation, type UserResource } from "@/modules/user-management/users/api/usersApi";
import { TemporaryPasswordDialog } from "@/modules/user-management/users/components/form/TemporaryPasswordDialog";
import { UserForm } from "@/modules/user-management/users/components/form/UserForm";
import { toCreateBody } from "@/modules/user-management/users/form/userFormBody";
import { emptyUserForm } from "@/modules/user-management/users/form/userFormDefaults";
import { SubmitHandler, useServerErrorHandler } from "@/modules/user-management/users/hooks/useUserFormErrors";
import type { Credentials } from "@/modules/user-management/users/types";
import { PageHeader } from "@/shared/ui";

export function UserCreatePage({ resource }: { resource: UserResource }) {
  const isAdmins = resource === "admins";
  const navigate = useNavigate();
  const notify = useNotify();
  const { user: actor } = useAuth();
  const [createUser, { isLoading }] = useCreateUserMutation();
  const [formError, setFormError] = useState<string | null>(null);
  const [created, setCreated] = useState<{
    credentials: Credentials;
    name: string;
    username?: string;
    email?: string | null;
    userId: string;
  } | null>(null);
  const handleError = useServerErrorHandler(setFormError);

  const defaults = useMemo(
    () => emptyUserForm(isAdmins ? { role: "admin" } : { organization_id: actor?.institution?.organization_id, organization_label: actor?.institution?.name }),
    [actor, isAdmins],
  );
  const onSubmit: SubmitHandler = async (values, form, options) => {
    setFormError(null);
    const body = toCreateBody(values, options);
    try {
      const result = await createUser(isAdmins ? { resource, body: { ...body, role: undefined } as never } : { resource, body }).unwrap();
      if (
        result.credentials.delivery === "temporary_password" ||
        result.credentials.temporary_password ||
        (!result.credentials.email_sent && result.credentials.setup_link)
      ) {
        setCreated({
          credentials: result.credentials,
          name: result.user.personal_info.full_name,
          username: result.user.account.username,
          email: result.user.account.email,
          userId: result.user.user_id,
        });
        return;
      }
      notify.success(
        `${result.user.personal_info.full_name} created`,
        result.credentials.delivery === "initial_password" ? "Share the initial password securely." : "An account set-up email has been sent.",
      );
      navigate(`/${resource}`, { replace: true });
    } catch (error) {
      handleError(error, form);
    }
  };

  return (
    <>
      <PageHeader title={isAdmins ? "New admin" : "New user"} backTo={`/${resource}`} backLabel={isAdmins ? "Admins" : "Users"} />
      <UserForm
        mode="create"
        defaultValues={defaults}
        submitting={isLoading}
        formError={formError}
        onSubmit={onSubmit}
        onCancel={() => navigate(`/${resource}`)}
      />
      <TemporaryPasswordDialog
        open={created !== null}
        name={created?.name ?? ""}
        username={created?.username}
        email={created?.email}
        password={created?.credentials.temporary_password}
        delivery={created?.credentials.delivery}
        emailSent={created?.credentials.email_sent}
        setupLink={created?.credentials.setup_link}
        message={created?.credentials.message}
        onClose={() => navigate(`/${resource}`, { replace: true })}
      />
    </>
  );
}

import { useId, useMemo, useState } from "react";
import { FormProvider, useForm } from "react-hook-form";

import { useNotify } from "@/core/hooks/useNotify";
import { useAuth } from "@/modules/user-management/auth/hooks/useAuth";
import { useGetUserFormOptionsQuery } from "@/modules/user-management/common/permissions/permissionsApi";
import type { UserFormOptions } from "@/modules/user-management/common/permissions/types";
import { PersonFields } from "@/modules/user-management/manage/people/components/PersonFields";
import { capitalize, PERSON_SCREENS, type PersonKind } from "@/modules/user-management/manage/people/config";
import { useCreateUserMutation, useGetUserQuery, useUpdateUserMutation } from "@/modules/user-management/users/api/usersApi";
import { toCreateBody, toUpdateBody } from "@/modules/user-management/users/form/userFormBody";
import { emptyUserForm, userToForm } from "@/modules/user-management/users/form/userFormDefaults";
import type { UserFormValues } from "@/modules/user-management/users/form/userFormValues";
import { useServerErrorHandler } from "@/modules/user-management/users/hooks/useUserFormErrors";
import { Alert, Button, EmptyState, Modal, Spinner } from "@/shared/ui";

export interface TemporaryPassword {
  name: string;
  username?: string;
  email?: string | null;
  password?: string | null;
  delivery?: "email_link" | "initial_password" | "temporary_password";
  emailSent?: boolean | null;
  setupLink?: string | null;
  message?: string | null;
}

/**
 * Add or edit one person in a pop-up. Adding and editing use the same form: `userId` set means edit.
 * A student created without an email or with temporary password gets credentials handed to `onTemporaryPassword` to show.
 */
export function PersonFormModal({ kind, userId, onClose, onTemporaryPassword }: {
  kind: PersonKind;
  userId: string | null;
  onClose: () => void;
  onTemporaryPassword: (created: TemporaryPassword) => void;
}) {
  const screen = PERSON_SCREENS[kind];
  const editing = userId !== null;
  const { user: actor } = useAuth();
  const userQuery = useGetUserQuery({ resource: screen.resource, userId: userId ?? "" }, { skip: !editing });
  const optionsQuery = useGetUserFormOptionsQuery({ role: kind, userId: userId ?? undefined });

  const initial = useMemo<UserFormValues | null>(() => {
    if (editing) return userQuery.data ? userToForm(userQuery.data) : null;
    // A head or staff member adds people to their own institution; the server fixes it, this only shows its name.
    return emptyUserForm({ role: kind, organization_id: actor?.institution?.organization_id, organization_label: actor?.institution?.name });
  }, [actor, editing, kind, userQuery.data]);

  const failed = userQuery.isError || optionsQuery.isError;
  const ready = initial !== null && optionsQuery.data !== undefined;

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title={`${editing ? "Edit" : "Add"} ${screen.one}`}
      description={editing ? "Change the details and save." : screen.addHint}
    >
      {failed ? (
        <EmptyState icon="alert" title="Could not open the form" description="Close it and try again." />
      ) : !ready ? (
        <div className="flex justify-center py-12"><Spinner /></div>
      ) : (
        <PersonForm kind={kind} userId={userId} initial={initial} options={optionsQuery.data} onDone={onClose} onTemporaryPassword={onTemporaryPassword} />
      )}
    </Modal>
  );
}

function PersonForm({ kind, userId, initial, options, onDone, onTemporaryPassword }: {
  kind: PersonKind;
  userId: string | null;
  initial: UserFormValues;
  options: UserFormOptions;
  onDone: () => void;
  onTemporaryPassword: (created: TemporaryPassword) => void;
}) {
  const screen = PERSON_SCREENS[kind];
  const formId = useId();
  const notify = useNotify();
  // The server checks the fields; a field's error stays until the person edits that field.
  const form = useForm<UserFormValues>({ defaultValues: initial, mode: "onSubmit", reValidateMode: "onChange" });
  const [createUser, { isLoading: creating }] = useCreateUserMutation();
  const [updateUser, { isLoading: saving }] = useUpdateUserMutation();
  const [formError, setFormError] = useState<string | null>(null);
  const handleError = useServerErrorHandler(setFormError);

  const submit = form.handleSubmit(async (values) => {
    setFormError(null);
    try {
      if (userId === null) {
        const body = toCreateBody(values, options);
        // /admins takes no role: everyone created there is an admin
        const result = await createUser({ resource: screen.resource, body: screen.resource === "admins" ? { ...body, role: undefined } : body }).unwrap();
        const name = result.user.personal_info.full_name;
        if (
          result.credentials.delivery === "temporary_password" ||
          result.credentials.temporary_password ||
          (!result.credentials.email_sent && result.credentials.setup_link)
        ) {
          onTemporaryPassword({
            name,
            username: result.user.account.username,
            email: result.user.account.email,
            password: result.credentials.temporary_password,
            delivery: result.credentials.delivery,
            emailSent: result.credentials.email_sent,
            setupLink: result.credentials.setup_link,
            message: result.credentials.message,
          });
        } else {
          notify.success(
            `${capitalize(screen.one)} added`,
            result.credentials.delivery === "initial_password"
              ? "Share the password securely."
              : `${name} gets an email to set a password.`
          );
        }
        onDone();
        return;
      }
      const body = toUpdateBody(initial, values, options);
      if (Object.keys(body).length === 0) {
        notify.info("Nothing changed");
        onDone();
        return;
      }
      await updateUser({ resource: screen.resource, userId, body }).unwrap();
      notify.success("Changes saved", body.organization_id ? "They were signed out because their institution changed." : undefined);
      onDone();
    } catch (error) {
      handleError(error, form);
    }
  });

  return (
    <FormProvider {...form}>
      <form id={formId} onSubmit={submit} noValidate className="space-y-6">
        {formError && <Alert tone="error">{formError}</Alert>}
        <PersonFields kind={kind} options={options} editing={userId !== null} />
        {/* pinned to the bottom of the pop-up while the fields scroll */}
        <div className="sticky bottom-0 -mx-6 -mb-5 flex flex-col-reverse gap-2 border-t border-slate-100 bg-white px-6 py-4 sm:flex-row sm:justify-end">
          <Button variant="secondary" onClick={onDone} disabled={creating || saving}>
            Cancel
          </Button>
          <Button type="submit" loading={creating || saving}>
            {userId === null ? `Add ${screen.one}` : "Save changes"}
          </Button>
        </div>
      </form>
    </FormProvider>
  );
}

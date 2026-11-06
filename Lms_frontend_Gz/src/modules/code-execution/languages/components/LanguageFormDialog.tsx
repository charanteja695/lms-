import { FormProvider, useForm } from "react-hook-form";

import { useNotify } from "@/core/hooks/useNotify";
import { useCreateLanguageMutation, useUpdateLanguageMutation } from "@/modules/code-execution/languages/api/languagesApi";
import type { LanguageAdmin } from "@/modules/code-execution/languages/types";
import { CheckboxField, TextField } from "@/shared/form";
import { Button, Modal } from "@/shared/ui";

interface LanguageFormValues {
  code: string;
  name: string;
  version: string;
  file_name: string;
  editor_mode: string;
  compiler_options: string;
  time_multiplier: string;
  memory_multiplier: string;
  sort_order: string;
  enabled: boolean;
}

export function LanguageFormDialog({ open, onClose, language: existing }: { open: boolean; onClose: () => void; language?: LanguageAdmin }) {
  const notify = useNotify();
  const [createLanguage, { isLoading: creating }] = useCreateLanguageMutation();
  const [updateLanguage, { isLoading: updating }] = useUpdateLanguageMutation();
  const isLoading = creating || updating;
  const form = useForm<LanguageFormValues>({
    values: {
      code: existing?.code ?? "",
      name: existing?.name ?? "",
      version: existing?.version ?? "",
      file_name: existing?.file_name ?? "main",
      editor_mode: existing?.editor_mode ?? "",
      compiler_options: existing?.compiler_options ?? "",
      time_multiplier: String(existing?.time_multiplier ?? 1),
      memory_multiplier: String(existing?.memory_multiplier ?? 1),
      sort_order: String(existing?.sort_order ?? 0),
      enabled: existing?.enabled ?? true,
    },
  });

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={existing ? "Edit language" : "Add language"}
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button type="submit" form="language-form" loading={isLoading}>
            {existing ? "Save" : "Add language"}
          </Button>
        </>
      }
    >
      <FormProvider {...form}>
        <form
          id="language-form"
          noValidate
          className="grid gap-4 sm:grid-cols-2"
          onSubmit={form.handleSubmit(async (values) => {
            const shared = {
              name: values.name,
              version: values.version,
              file_name: values.file_name,
              editor_mode: values.editor_mode,
              compiler_options: values.compiler_options || null,
              time_multiplier: Number(values.time_multiplier),
              memory_multiplier: Number(values.memory_multiplier),
              sort_order: Number(values.sort_order),
              enabled: values.enabled,
            };
            try {
              if (existing) {
                await updateLanguage({ code: existing.code, body: shared }).unwrap();
                notify.success("Language updated");
              } else {
                await createLanguage({ ...shared, code: values.code }).unwrap();
                notify.success("Language added");
              }
              onClose();
            } catch (error) {
              notify.apiError(error);
            }
          })}
        >
          {existing ? <TextField<LanguageFormValues> name="code" label="Code" disabled /> : <TextField<LanguageFormValues> name="code" label="Code" required placeholder="python3" />}
          <TextField<LanguageFormValues> name="name" label="Name" required placeholder="Python" />
          <TextField<LanguageFormValues> name="version" label="Version" required placeholder="3.12" />
          <TextField<LanguageFormValues> name="file_name" label="File name" required placeholder="main.py" />
          <TextField<LanguageFormValues> name="editor_mode" label="Editor mode" required placeholder="python" />
          <TextField<LanguageFormValues> name="compiler_options" label="Compiler options" placeholder="-std=c++20 -O2" />
          <TextField<LanguageFormValues> name="time_multiplier" label="Time multiplier" type="number" required />
          <TextField<LanguageFormValues> name="memory_multiplier" label="Memory multiplier" type="number" required />
          <TextField<LanguageFormValues> name="sort_order" label="Sort order" type="number" required />
          <div className="sm:col-span-2">
            <CheckboxField<LanguageFormValues> name="enabled" label="Enabled" hint="Disabled languages are hidden from the editor's language switcher." />
          </div>
        </form>
      </FormProvider>
    </Modal>
  );
}

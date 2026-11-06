import { useState } from "react";
import { Navigate } from "react-router-dom";

import { CodeTabs } from "@/modules/code-execution/common/components/CodeTabs";
import { useAuth } from "@/modules/user-management/auth/hooks/useAuth";
import { useListLanguagesAdminQuery } from "@/modules/code-execution/languages/api/languagesApi";
import { LanguageFormDialog } from "@/modules/code-execution/languages/components/LanguageFormDialog";
import type { LanguageAdmin } from "@/modules/code-execution/languages/types";
import { Badge, Button, Card, DataTable, type Column, EmptyState, Icon, PageHeader } from "@/shared/ui";

export function LanguagesAdminPage() {
  const { role } = useAuth();
  const { data: languages, isFetching } = useListLanguagesAdminQuery(undefined, { skip: role !== "super_admin" });
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<LanguageAdmin | null>(null);

  // Managing the language catalog (compiler options, engine ids) is a super_admin-only concern,
  // narrower than the "code_execution" section everyone with it shares.
  if (role !== "super_admin") return <Navigate to="/problems" replace />;

  const columns: Column<LanguageAdmin>[] = [
    { key: "name", header: "Language", render: (item) => `${item.name} ${item.version}` },
    { key: "code", header: "Code", hideOnMobile: true, render: (item) => item.code },
    { key: "kind", header: "Kind", hideOnMobile: true, render: (item) => item.kind },
    { key: "enabled", header: "Status", render: (item) => <Badge tone={item.enabled ? "green" : "gray"}>{item.enabled ? "Enabled" : "Disabled"}</Badge> },
    {
      key: "actions",
      header: <span className="sr-only">Actions</span>,
      className: "w-12 text-right",
      render: (item) => (
        <Button variant="ghost" size="icon" aria-label={`Edit ${item.name}`} onClick={() => setEditing(item)}>
          <Icon name="edit" />
        </Button>
      ),
    },
  ];

  return (
    <>
      <PageHeader title="Coding practice" description="The programming languages the compiler and the judge can run." actions={<Button icon="plus" onClick={() => setAdding(true)}>New language</Button>} />
      <CodeTabs />
      <Card bodyClassName="p-0">
        <DataTable columns={columns} rows={languages ?? []} rowKey={(item) => item.code} loading={isFetching} empty={<EmptyState icon="terminal" title="No languages configured" description="Add a language so the compiler can run it." />} />
      </Card>
      {adding && <LanguageFormDialog open={adding} onClose={() => setAdding(false)} />}
      {editing && <LanguageFormDialog open={Boolean(editing)} onClose={() => setEditing(null)} language={editing} />}
    </>
  );
}

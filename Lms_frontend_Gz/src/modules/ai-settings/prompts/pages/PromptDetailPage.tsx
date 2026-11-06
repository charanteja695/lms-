import { useState } from "react";
import { useParams } from "react-router-dom";

import { AiTabs } from "@/modules/ai-settings/common/components/AiTabs";
import { useGetPromptQuery } from "@/modules/ai-settings/prompts/api/promptsApi";
import { NewVersionDialog } from "@/modules/ai-settings/prompts/components/NewVersionDialog";
import { VersionCard } from "@/modules/ai-settings/prompts/components/VersionCard";
import { Button, Card, DescriptionList, EmptyState, PageHeader, PageLoader } from "@/shared/ui";

/** One prompt and all its versions, newest first: write a new one, put a draft in use, retire an old one. */
export function PromptDetailPage() {
  const { promptKey = "" } = useParams();
  const { data, isLoading, isError } = useGetPromptQuery(promptKey, { skip: !promptKey });
  const [drafting, setDrafting] = useState<string | null>(null);

  if (isLoading) return <PageLoader />;
  if (isError || !data) return <EmptyState icon="alert" title="Prompt not found" />;
  const active = data.versions.find((v) => v.status === "active");

  return (
    <>
      <PageHeader
        title={<span className="font-mono text-[22px] sm:text-[26px]">{data.prompt.key}</span>}
        description={data.prompt.description || "No description."}
        backTo="/ai/prompts"
        backLabel="Prompts"
        actions={<Button icon="plus" onClick={() => setDrafting(active?.template ?? "")}>New version</Button>}
      />
      <AiTabs />
      <div className="grid gap-6 lg:grid-cols-[1fr_18rem]">
        <section className="space-y-4" aria-label="Versions">
          {data.versions.length === 0 ? (
            <Card><EmptyState icon="fileText" title="No versions yet" description="Write the first version; another AI manager then puts it in use." action={<Button onClick={() => setDrafting("")}>Write version 1</Button>} /></Card>
          ) : (
            data.versions.map((v) => <VersionCard key={v.version_id} promptKey={data.prompt.key} version={v} onCopy={setDrafting} />)
          )}
        </section>
        <Card title="About" className="self-start">
          <DescriptionList
            items={[
              { label: "Used by", value: data.prompt.owner_service },
              { label: "Kind", value: data.prompt.capability === "chat" ? "Chat" : "Search" },
              { label: "In use", value: active ? `Version ${active.version}` : "None: calls fail until a version is in use" },
            ]}
          />
        </Card>
      </div>
      {drafting !== null && <NewVersionDialog promptKey={data.prompt.key} initialTemplate={drafting} onClose={() => setDrafting(null)} />}
    </>
  );
}

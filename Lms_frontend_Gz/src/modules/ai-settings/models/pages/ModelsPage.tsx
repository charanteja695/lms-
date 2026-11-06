import { AiTabs } from "@/modules/ai-settings/common/components/AiTabs";
import { RouteEditor } from "@/modules/ai-settings/models/components/RouteEditor";
import { useGetModelRoutesQuery } from "@/modules/ai-settings/models/api/modelsApi";
import { Alert, EmptyState, PageHeader, PageLoader } from "@/shared/ui";

/** Which AI providers answer, in which order: the first is used; the next ones only if it fails. */
export function ModelsPage() {
  const { data, isLoading, isError } = useGetModelRoutesQuery();
  return (
    <>
      <PageHeader title="AI usage & settings" description="Which AI models answer, in order. The first is used; the next only if it fails." />
      <AiTabs />
      {isLoading ? (
        <PageLoader />
      ) : isError || !data ? (
        <EmptyState icon="alert" title="Could not load the model order" description="Only AI managers can see this. Try again in a moment." />
      ) : (
        <div className="space-y-6">
          <Alert tone="info">A provider is used only once its API key is set on the server; until then it is skipped and the next one answers.</Alert>
          <RouteEditor key={`chat-${JSON.stringify(data.chat)}`} capability="chat" title="Chat" description="Tutor answers, interview questions, resume and screening help." initial={data.chat} />
          <RouteEditor key={`emb-${JSON.stringify(data.embedding)}`} capability="embedding" title="Search (embeddings)" description="Finding the right course notes and matching jobs by meaning." initial={data.embedding} />
        </div>
      )}
    </>
  );
}

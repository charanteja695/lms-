import { useState } from "react";

import { useListStudentFaqQuery } from "@/modules/ai-tutor/faq/api/faqApi";
import { Card, EmptyState, PageHeader, PageLoader, SearchInput } from "@/shared/ui";

/** The student's FAQ: published entries from the platform, their institution and their courses (the server decides which). */
export function FaqPage() {
  const [search, setSearch] = useState("");
  const query = search.trim();
  const { data: faqs = [], isLoading, isFetching } = useListStudentFaqQuery({ q: query || undefined });

  return (
    <>
      <PageHeader title="Frequently asked questions" description="Answers your institution and course authors have published." backTo="/tutor/chat" backLabel="AI tutor" />
      <div className="mb-4 max-w-md">
        <SearchInput value={search} onChange={setSearch} placeholder="Search the FAQ" />
      </div>
      {isLoading ? (
        <PageLoader />
      ) : faqs.length === 0 ? (
        <EmptyState icon="helpCircle" title={query ? "No matching questions" : "No FAQ entries yet"} description={query ? "Try other words, or ask the AI tutor." : "Answers your institution publishes appear here."} />
      ) : (
        <div className={isFetching ? "space-y-3 opacity-60" : "space-y-3"}>
          {faqs.map((faq) => (
            <Card key={faq.faq_id}>
              <details>
                <summary className="cursor-pointer font-medium text-slate-900">{faq.question}</summary>
                <p className="mt-3 whitespace-pre-wrap text-sm text-slate-700">{faq.answer}</p>
              </details>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}

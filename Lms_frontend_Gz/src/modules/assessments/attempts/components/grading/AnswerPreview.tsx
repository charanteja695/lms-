import { useNotify } from "@/core/hooks/useNotify";
import { formatBytes } from "@/core/lib/format";
import { useGetAnswerFileLinkMutation } from "@/modules/assessments/attempts/api/attemptsApi";
import type { GradingQueueItem } from "@/modules/assessments/attempts/gradingTypes";
import { Badge, Icon } from "@/shared/ui";

interface AnswerFile {
  filename: string;
  size?: number;
}

/**
 * What the student answered, shown the way a grader needs it: a written answer as text, code as code (with its
 * language), and uploaded files as links that open a fresh short-lived copy. Never raw data.
 */
export function AnswerPreview({ item }: { item: GradingQueueItem }) {
  const notify = useNotify();
  const [getLink] = useGetAnswerFileLinkMutation();
  const response = item.response ?? {};
  const text = typeof response.text === "string" ? response.text : null;
  const source = typeof response.source === "string" ? response.source : null;
  const files = Array.isArray(response.files) ? (response.files as AnswerFile[]) : null;

  const open = async (index: number) => {
    const tab = window.open("", "_blank"); // opened during the click, so pop-up blockers allow it
    try {
      const { url } = await getLink({ attemptId: item.attempt_id, questionId: item.question_id, index }).unwrap();
      if (tab) tab.location.href = url;
      else window.location.assign(url);
    } catch (error) {
      tab?.close();
      notify.apiError(error);
    }
  };

  if (!item.response) return <p className="text-sm italic text-slate-500">No answer was given.</p>;
  if (files) {
    return files.length === 0 ? (
      <p className="text-sm italic text-slate-500">No file was uploaded.</p>
    ) : (
      <ul className="flex flex-wrap gap-2">
        {files.map((file, index) => (
          <li key={`${file.filename}-${index}`}>
            <button type="button" onClick={() => void open(index)} className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-card transition-colors hover:border-brand-300 hover:text-brand-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500">
              <Icon name="download" size={16} className="text-slate-400" />
              {file.filename}
              {file.size ? <span className="text-xs text-slate-400">{formatBytes(file.size)}</span> : null}
            </button>
          </li>
        ))}
      </ul>
    );
  }
  if (source !== null) {
    return (
      <div className="space-y-2">
        {typeof response.language === "string" && <Badge tone="indigo">{response.language}</Badge>}
        <pre className="max-h-80 overflow-auto rounded-xl bg-ink-950 p-4 font-mono text-[13px] leading-relaxed text-slate-100">{source}</pre>
      </div>
    );
  }
  if (text !== null) return <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-800">{text}</p>;
  return <pre className="overflow-auto whitespace-pre-wrap text-xs text-slate-700">{JSON.stringify(item.response, null, 2)}</pre>;
}

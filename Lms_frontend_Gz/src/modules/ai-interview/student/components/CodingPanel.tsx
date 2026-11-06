import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { useRunInterviewCodeMutation } from "@/modules/ai-interview/student/api/studentInterviewsApi";
import { Button, Card, CodeEditor, Select, Textarea } from "@/shared/ui";

/** The coding round's editor. A run goes through code-execution and both the code and its output join the transcript. */
export function CodingPanel({ interviewId, languages, onRan }: { interviewId: string; languages: string[]; onRan: () => void }) {
  const notify = useNotify();
  const [run, { isLoading }] = useRunInterviewCodeMutation();
  const [language, setLanguage] = useState(languages[0] ?? "");
  const [source, setSource] = useState("");
  const [stdin, setStdin] = useState("");

  return (
    <Card title="Code" actions={<Select aria-label="Language" className="w-40" value={language} options={languages.map((l) => ({ value: l, label: l }))} onChange={(e) => setLanguage(e.target.value)} />}>
      <div className="space-y-2">
        <CodeEditor value={source} onChange={setSource} rows={14} language={language} />
        <Textarea aria-label="Input" rows={2} placeholder="Input (stdin), optional" value={stdin} onChange={(e) => setStdin(e.target.value)} />
        <div className="flex justify-end">
          <Button
            icon="play"
            loading={isLoading}
            disabled={!source.trim() || !language}
            onClick={async () => {
              try {
                await run({ id: interviewId, language, source, stdin: stdin || undefined }).unwrap();
                onRan();
              } catch (error) {
                notify.apiError(error);
              }
            }}
          >
            Run
          </Button>
        </div>
      </div>
    </Card>
  );
}

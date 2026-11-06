import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useNotify } from "@/core/hooks/useNotify";
import { useListLanguagesQuery } from "@/modules/code-execution/languages/api/languagesApi";
import { LanguageSelect } from "@/modules/code-execution/languages/components/LanguageSelect";
import { useRunExecution } from "@/modules/code-execution/runs/hooks/useRunExecution";
import { Badge, Button, Card, CodeEditor, Icon, PageHeader, Spinner, Textarea } from "@/shared/ui";
import { cn } from "@/core/lib/cn";

export function CompilerPage() {
  const navigate = useNavigate();
  const notify = useNotify();
  const { data: languages } = useListLanguagesQuery();
  const { run, isExecuting, execute } = useRunExecution();

  const [language, setLanguage] = useState("");
  const [source, setSource] = useState("");
  const [stdin, setStdin] = useState("");
  const [expectedOutput, setExpectedOutput] = useState("");
  const [activeTab, setActiveTab] = useState<"output" | "stdin" | "compare" | "tutor">("output");
  const [copied, setCopied] = useState(false);

  const current = languages?.find((item) => item.code === language);

  // Default to first language when loaded
  useEffect(() => {
    if (!language && languages && languages.length > 0) {
      const first = languages[0];
      if (first) {
        setLanguage(first.code);
        setSource(first.starter_template);
      }
    }
  }, [language, languages]);

  // Keyboard shortcut: Ctrl+Enter (or Cmd+Enter) executes code
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        e.preventDefault();
        if (language && !isExecuting) {
          void execute({ language, source, stdin });
          setActiveTab("output");
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [execute, isExecuting, language, source, stdin]);

  const handleResetCode = () => {
    if (current) {
      setSource(current.starter_template);
      setStdin("");
      setExpectedOutput("");
      notify.info("Code reset to starter template");
    }
  };

  const handleCopyCode = () => {
    navigator.clipboard.writeText(source);
    setCopied(true);
    notify.success("Code copied to clipboard");
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownloadCode = () => {
    const extMap: Record<string, string> = {
      python: "py",
      javascript: "js",
      typescript: "ts",
      cpp: "cpp",
      c: "c",
      java: "java",
      sql: "sql",
      go: "go",
      rust: "rs",
    };
    const ext = extMap[language.toLowerCase()] ?? "txt";
    const filename = `solution.${ext}`;
    const blob = new Blob([source], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    notify.success(`Downloaded ${filename}`);
  };

  // Compare actual vs expected output
  const comparisonResult = useMemo(() => {
    if (!run?.stdout || !expectedOutput.trim()) return null;
    const actual = run.stdout.trim().replace(/\r\n/g, "\n");
    const expected = expectedOutput.trim().replace(/\r\n/g, "\n");
    const passed = actual === expected;
    return { passed, actual, expected };
  }, [run?.stdout, expectedOutput]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Compiler"
        description="Write and run code in any supported language. Add input, compare with an expected output, or ask the AI tutor."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="secondary" icon="sparkles" onClick={() => navigate("/tutor")}>Ask AI tutor</Button>
            <Button
              icon="play"
              loading={isExecuting}
              disabled={!language}
              onClick={() => {
                void execute({ language, source, stdin });
                setActiveTab("output");
              }}
            >
              Run code <span className="ml-1 text-xs font-normal opacity-80">Ctrl+Enter</span>
            </Button>
          </div>
        }
      />

      {/* Main Compiler IDE & Terminal Layout */}
      <div className="grid gap-6 lg:grid-cols-12">
        {/* Left Side: Code Editor (7 cols on lg) */}
        <div className="lg:col-span-7 space-y-4">
          <div className="rounded-2xl border border-slate-200/90 bg-white shadow-card overflow-hidden">
            {/* Editor Top Navigation & Action Controls */}
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200/80 bg-slate-50/70 px-4 py-3">
              <div className="flex items-center gap-3">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-navy-950 text-brand-300 shadow-sm">
                  <Icon name="terminal" size={14} />
                </span>
                <div className="w-48 sm:w-56">
                  <LanguageSelect
                    value={language}
                    onChange={(code) => {
                      setLanguage(code);
                      const picked = languages?.find((item) => item.code === code);
                      if (picked) {
                        setSource(picked.starter_template);
                                        }
                    }}
                  />
                </div>
              </div>

              <div className="flex items-center gap-1.5">
                <Button
                  size="sm"
                  variant="ghost"
                  icon="refresh"
                  onClick={handleResetCode}
                  title="Reset code to default template"
                >
                  Reset
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  icon={copied ? "check" : "layers"}
                  onClick={handleCopyCode}
                  title="Copy code"
                >
                  {copied ? "Copied" : "Copy"}
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  icon="download"
                  onClick={handleDownloadCode}
                  title="Download source code"
                >
                  Download
                </Button>
              </div>
            </div>

            {/* Code Editor Surface */}
            <div className="p-2 sm:p-3">
              <CodeEditor
                value={source}
                onChange={setSource}
                language={current ? `${current.name} ${current.version}` : undefined}
                rows={20}
              />
            </div>

            {/* Editor Bottom Status Bar */}
            <div className="flex items-center justify-between border-t border-slate-100 bg-slate-50/80 px-4 py-2 text-xs text-slate-500">
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-emerald-500" />
                <span>Language: <strong className="text-navy-950 font-semibold">{current ? current.name : "Auto"}</strong></span>
                {current?.version && <span className="text-slate-400">({current.version})</span>}
              </div>
              <div className="flex items-center gap-2">
                <span>Shortcut: <kbd className="rounded bg-slate-200/80 px-1.5 py-0.5 font-mono text-[11px] text-slate-700">Ctrl+Enter</kbd></span>
              </div>
            </div>
          </div>
        </div>

        {/* Right Side: Interactive Execution Console & Test Cases (5 cols on lg) */}
        <div className="lg:col-span-5 space-y-4">
          <Card bodyClassName="p-0">
            {/* Terminal Tab Bar */}
            <div className="flex items-center justify-between border-b border-slate-200/80 bg-slate-50/70 px-4 pt-2">
              <div className="flex items-center gap-1 overflow-x-auto">
                {[
                  { id: "output" as const, label: "Output", icon: "play" as const },
                  { id: "stdin" as const, label: "Input", icon: "edit" as const },
                  { id: "compare" as const, label: "Check output", icon: "clipboardCheck" as const },
                  { id: "tutor" as const, label: "AI help", icon: "sparkles" as const },
                ].map((tab) => (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setActiveTab(tab.id)}
                    className={cn(
                      "flex shrink-0 items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2 text-xs font-semibold transition-all cursor-pointer",
                      activeTab === tab.id
                        ? "border-brand-600 text-brand-700 bg-white rounded-t-lg shadow-xs"
                        : "border-transparent text-slate-500 hover:text-slate-900",
                    )}
                  >
                    <Icon name={tab.icon} size={13} />
                    <span>{tab.label}</span>
                  </button>
                ))}
              </div>

              {isExecuting && (
                <span className="flex items-center gap-1.5 text-xs font-medium text-brand-700">
                  <Spinner size={12} /> Running…
                </span>
              )}
            </div>

            {/* Tab 1: Execution Output */}
            {activeTab === "output" && (
              <div className="p-4 sm:p-5 space-y-4">
                {!run && !isExecuting ? (
                  <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50/50 p-8 text-center">
                    <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-white shadow-sm ring-1 ring-slate-200/80 text-slate-400">
                      <Icon name="play" size={20} />
                    </span>
                    <h3 className="mt-3 text-sm font-bold text-navy-950">Ready to run</h3>
                    <p className="mt-1 text-xs text-slate-500 max-w-xs mx-auto">
                      Press Run code (or Ctrl+Enter). The output appears here.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {/* Run Status Header */}
                    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
                      <div className="flex items-center gap-2">
                        {isExecuting ? (
                          <Badge tone="amber">Executing…</Badge>
                        ) : (
                          <Badge tone={run?.outcome === "ok" ? "green" : "red"}>
                            {run?.outcome === "ok" ? "Ran successfully" : run?.outcome ?? "Finished"}
                          </Badge>
                        )}
                        {run?.exit_code != null && (
                          <span className="font-mono text-xs text-slate-500">
                            exit code {run.exit_code}
                          </span>
                        )}
                      </div>

                      {run && (run.time_ms != null || run.memory_kb != null) && (
                        <div className="flex items-center gap-2 text-xs font-medium text-slate-500">
                          {run.time_ms != null && (
                            <span className="flex items-center gap-1">
                              <Icon name="clock" size={12} /> {run.time_ms} ms
                            </span>
                          )}
                          {run.memory_kb != null && (
                            <span className="flex items-center gap-1">
                              <Icon name="layers" size={12} /> {run.memory_kb} KB
                            </span>
                          )}
                        </div>
                      )}
                    </div>

                    {/* Standard Output (stdout) */}
                    <div>
                      <p className="mb-1.5 text-xs font-bold uppercase tracking-wider text-slate-500">Standard Output (stdout):</p>
                      <pre className="max-h-56 overflow-auto rounded-xl bg-slate-950 p-3.5 font-mono text-xs text-emerald-300 shadow-inner">
                        <code>{run?.stdout || (run?.stderr ? "" : "/* No output returned */")}</code>
                      </pre>
                    </div>

                    {/* Standard Error (stderr) */}
                    {run?.stderr && (
                      <div>
                        <p className="mb-1.5 text-xs font-bold uppercase tracking-wider text-red-600">Standard Error (stderr):</p>
                        <pre className="max-h-40 overflow-auto rounded-xl bg-red-950/30 border border-red-200 p-3.5 font-mono text-xs text-red-700">
                          <code>{run.stderr}</code>
                        </pre>
                      </div>
                    )}

                    {/* Compiler Output */}
                    {run?.compile_output && (
                      <div>
                        <p className="mb-1.5 text-xs font-bold uppercase tracking-wider text-amber-600">Compiler Diagnostic:</p>
                        <pre className="max-h-40 overflow-auto rounded-xl bg-amber-950/30 border border-amber-200 p-3.5 font-mono text-xs text-amber-800">
                          <code>{run.compile_output}</code>
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Tab 2: Custom stdin */}
            {activeTab === "stdin" && (
              <div className="p-4 sm:p-5 space-y-4">
                <div>
                  <p className="text-xs font-bold uppercase tracking-wider text-navy-950">Standard Input (stdin)</p>
                  <p className="mt-0.5 text-xs text-slate-500">
                    Values supplied here are read by your code via <code>input()</code>, <code>stdin.read()</code>, or <code>cin</code>.
                  </p>
                </div>

                <Textarea
                  value={stdin}
                  onChange={(e) => setStdin(e.target.value)}
                  rows={8}
                  placeholder="Enter custom input values (separated by spaces or newlines)..."
                />

                <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-slate-100">
                  <div className="flex items-center gap-1.5">
                    <Button size="sm" variant="ghost" onClick={() => setStdin("10 20 30 40 50")}>
                      Numbers
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setStdin("hello world python")}>
                      Strings
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setStdin("")}>
                      Clear
                    </Button>
                  </div>
                  <Button
                    size="sm"
                    loading={isExecuting}
                    onClick={() => {
                      void execute({ language, source, stdin });
                      setActiveTab("output");
                    }}
                  >
                    Run with this Input
                  </Button>
                </div>
              </div>
            )}

            {/* Tab 3: Expected vs Actual Test Case Comparison */}
            {activeTab === "compare" && (
              <div className="p-4 sm:p-5 space-y-4">
                <div>
                  <p className="text-xs font-bold uppercase tracking-wider text-navy-950">Compare with an expected output</p>
                  <p className="mt-0.5 text-xs text-slate-500">
                    Specify your expected output to verify if your code passes or fails the test case.
                  </p>
                </div>

                <Textarea
                  value={expectedOutput}
                  onChange={(e) => setExpectedOutput(e.target.value)}
                  rows={4}
                  placeholder="Expected output string (e.g. '[0, 1]' or 'True')..."
                />

                {comparisonResult && (
                  <div
                    className={cn(
                      "rounded-xl border p-4 space-y-2",
                      comparisonResult.passed
                        ? "border-emerald-200 bg-emerald-50/70"
                        : "border-amber-200 bg-amber-50/70",
                    )}
                  >
                    <div className="flex items-center justify-between">
                      <span className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider">
                        <Icon
                          name={comparisonResult.passed ? "check" : "alert"}
                          size={16}
                          className={comparisonResult.passed ? "text-emerald-700" : "text-amber-700"}
                        />
                        {comparisonResult.passed ? (
                          <span className="text-emerald-800">Matches the expected output</span>
                        ) : (
                          <span className="text-amber-900">Doesn't match the expected output</span>
                        )}
                      </span>
                      <Badge tone={comparisonResult.passed ? "green" : "amber"}>
                        {comparisonResult.passed ? "100% Match" : "Diff Found"}
                      </Badge>
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-xs font-mono pt-2">
                      <div>
                        <span className="text-[10px] uppercase text-slate-500 block">Actual Output:</span>
                        <pre className="rounded bg-white p-2 border border-slate-200 text-slate-800 truncate">
                          {comparisonResult.actual}
                        </pre>
                      </div>
                      <div>
                        <span className="text-[10px] uppercase text-slate-500 block">Expected:</span>
                        <pre className="rounded bg-white p-2 border border-slate-200 text-slate-800 truncate">
                          {comparisonResult.expected}
                        </pre>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Tab 4: AI Code Tutor Guidance */}
            {activeTab === "tutor" && (
              <div className="p-4 sm:p-5 space-y-4">
                <div className="flex items-center gap-3">
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-700 ring-1 ring-brand-200">
                    <Icon name="sparkles" size={20} />
                  </span>
                  <div>
                    <h4 className="text-sm font-bold text-navy-950">24/7 AI Code Tutor</h4>
                    <p className="text-xs text-slate-500">Ask questions about your code, time complexity, or edge cases.</p>
                  </div>
                </div>

                <div className="space-y-2">
                  <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Suggested Prompts:</p>
                  {[
                    "Explain how this code works step-by-step",
                    "What is the Time and Space complexity of this solution?",
                    "How can I optimize this code for large inputs?",
                    "What edge cases might cause this code to fail?",
                  ].map((prompt, i) => (
                    <button
                      key={i}
                      type="button"
                      onClick={() => navigate(`/tutor?prompt=${encodeURIComponent(prompt)}`)}
                      className="flex w-full items-center justify-between rounded-xl border border-slate-200/90 bg-slate-50/60 p-2.5 text-xs font-medium text-slate-700 transition-colors hover:border-brand-300 hover:bg-brand-50/50 hover:text-brand-800 text-left cursor-pointer"
                    >
                      <span>{prompt}</span>
                      <Icon name="chevronRight" size={13} className="text-slate-400 shrink-0" />
                    </button>
                  ))}
                </div>

                <div className="pt-3 border-t border-slate-100 flex justify-center">
                  <Button
                    size="sm"
                    icon="sparkles"
                    onClick={() => navigate("/tutor")}
                    className="bg-brand-600 hover:bg-brand-700 text-white shadow-brand"
                  >
                    Open AI Tutor Chat
                  </Button>
                </div>
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}

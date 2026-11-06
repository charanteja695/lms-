import { useRef, useState, type DragEvent } from "react";
import { cn } from "@/core/lib/cn";
import type { McqDraft } from "@/modules/catalog/course-tests/hooks/useTestQuestions";
import {
  downloadExcelTemplate,
  downloadJsonTemplate,
  parseQuestionsFile,
  validateQuestionRow,
  type ParsedQuestionRow,
  type ParseResult,
} from "@/modules/catalog/course-tests/utils/excelQuestions";
import { Alert, Badge, Button, Icon, Modal } from "@/shared/ui";

export interface UnifiedImportQuestionsModalProps {
  existingQuestions?: string[];
  onClose: () => void;
  onImport: (
    drafts: McqDraft[],
    onProgress: (completed: number, total: number) => void
  ) => Promise<unknown>;
}

export function UnifiedImportQuestionsModal({
  existingQuestions = [],
  onClose,
  onImport,
}: UnifiedImportQuestionsModalProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [parseResult, setParseResult] = useState<ParseResult | null>(null);
  const [parseError, setParseError] = useState<string | null>(null);
  const [isParsing, setIsParsing] = useState(false);

  // Active preview tab
  const [activeTab, setActiveTab] = useState<"valid" | "invalid">("valid");

  // Inline editing state for invalid rows
  const [editingRowNumber, setEditingRowNumber] = useState<number | null>(null);
  const [editRowDraft, setEditRowDraft] = useState<{
    question: string;
    optionA: string;
    optionB: string;
    optionC: string;
    optionD: string;
    correctAnswer: string;
    marks: number | string;
    explanation: string;
  } | null>(null);

  // Import execution states
  const [isImporting, setIsImporting] = useState(false);
  const [importProgress, setImportProgress] = useState<{
    completed: number;
    total: number;
  } | null>(null);
  const [importError, setImportError] = useState<string | null>(null);

  const processFile = async (file: File) => {
    const name = file.name.toLowerCase();
    const isSupported =
      name.endsWith(".xlsx") ||
      name.endsWith(".xls") ||
      name.endsWith(".csv") ||
      name.endsWith(".json") ||
      file.type === "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" ||
      file.type === "application/vnd.ms-excel" ||
      file.type === "text/csv" ||
      file.type === "application/json";

    if (!isSupported) {
      setParseError("Please select a supported file (.xlsx, .xls, .csv, or .json).");
      setParseResult(null);
      return;
    }

    setParseError(null);
    setImportError(null);
    setIsParsing(true);
    setEditingRowNumber(null);
    setEditRowDraft(null);

    try {
      const result = await parseQuestionsFile(file, existingQuestions);
      setParseResult(result);
      if (result.validCount === 0 && result.errorCount > 0) {
        setActiveTab("invalid");
      } else {
        setActiveTab("valid");
      }
    } catch (err: unknown) {
      setParseResult(null);
      setParseError(
        err instanceof Error ? err.message : "Failed to parse questions file."
      );
    } finally {
      setIsParsing(false);
    }
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    if (e.dataTransfer.files?.[0]) {
      void processFile(e.dataTransfer.files[0]);
    }
  };

  // Start editing an invalid row inline
  const handleStartEditRow = (row: ParsedQuestionRow) => {
    setEditingRowNumber(row.rowNumber);
    setEditRowDraft({
      question: row.question,
      optionA: row.optionA,
      optionB: row.optionB,
      optionC: row.optionC,
      optionD: row.optionD,
      correctAnswer: row.correctAnswer,
      marks: row.marks,
      explanation: row.explanation,
    });
  };

  // Save inline edit and re-validate
  const handleSaveEditRow = (rowNumber: number) => {
    if (!editRowDraft || !parseResult) return;

    const validated = validateQuestionRow(
      {
        rowNumber,
        ...editRowDraft,
      },
      existingQuestions
    );

    const updatedRows = parseResult.rows.map((r) =>
      r.rowNumber === rowNumber ? validated : r
    );

    const validCount = updatedRows.filter((r) => r.status !== "error").length;
    const errorCount = updatedRows.filter((r) => r.status === "error").length;
    const warningCount = updatedRows.filter((r) => r.status === "warning").length;

    setParseResult({
      ...parseResult,
      rows: updatedRows,
      validCount,
      errorCount,
      warningCount,
    });

    setEditingRowNumber(null);
    setEditRowDraft(null);

    if (validated.status !== "error" && errorCount === 0) {
      setActiveTab("valid");
    }
  };

  // Remove an invalid row from import set
  const handleRemoveRow = (rowNumber: number) => {
    if (!parseResult) return;

    const updatedRows = parseResult.rows.filter((r) => r.rowNumber !== rowNumber);
    const validCount = updatedRows.filter((r) => r.status !== "error").length;
    const errorCount = updatedRows.filter((r) => r.status === "error").length;
    const warningCount = updatedRows.filter((r) => r.status === "warning").length;

    setParseResult({
      ...parseResult,
      totalRows: updatedRows.length,
      rows: updatedRows,
      validCount,
      errorCount,
      warningCount,
    });

    if (editingRowNumber === rowNumber) {
      setEditingRowNumber(null);
      setEditRowDraft(null);
    }

    if (errorCount === 0) {
      setActiveTab("valid");
    }
  };

  const validRows = parseResult?.rows.filter((r) => r.status !== "error") || [];
  const invalidRows = parseResult?.rows.filter((r) => r.status === "error") || [];

  const handleConfirmImport = async () => {
    if (!parseResult) return;
    const validDrafts = validRows
      .filter((r) => r.draft)
      .map((r) => r.draft as McqDraft);

    if (!validDrafts.length) {
      setImportError("There are no valid questions to import.");
      return;
    }

    setIsImporting(true);
    setImportError(null);
    setImportProgress({ completed: 0, total: validDrafts.length });

    try {
      await onImport(validDrafts, (completed, total) => {
        setImportProgress({ completed, total });
      });
      onClose();
    } catch (err: unknown) {
      setImportError(
        err instanceof Error
          ? err.message
          : "Failed to import questions. Please check your data and retry."
      );
      setIsImporting(false);
    }
  };

  return (
    <Modal open onClose={onClose} title="Import Questions" size="xl">
      <div className="space-y-5">
        {/* Top Template Download Bar */}
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <div>
            <h5 className="text-xs font-bold text-slate-800">Need a template?</h5>
            <p className="text-[11px] text-slate-500 mt-0.5">
              Download a sample template with required columns and example questions.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              icon="fileSpreadsheet"
              onClick={downloadExcelTemplate}
              className="text-xs font-semibold"
            >
              Excel Template (.xlsx)
            </Button>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              icon="fileText"
              onClick={downloadJsonTemplate}
              className="text-xs font-semibold"
            >
              JSON Template (.json)
            </Button>
          </div>
        </div>

        {/* File Dropzone */}
        {!parseResult && (
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={cn(
              "flex flex-col items-center justify-center rounded-2xl border-2 border-dashed p-8 text-center cursor-pointer transition-colors",
              dragging
                ? "border-[#2563EB] bg-blue-50/50"
                : "border-slate-300 bg-white hover:border-slate-400 hover:bg-slate-50/50"
            )}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".xlsx,.xls,.csv,.json,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel,text/csv,application/json"
              className="hidden"
              onChange={(e) => {
                if (e.target.files?.[0]) void processFile(e.target.files[0]);
              }}
            />
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-50 text-[#2563EB] mb-3">
              <Icon name="upload" size={24} />
            </div>
            <p className="text-sm font-bold text-slate-800">
              Drop your question file here, or <span className="text-[#2563EB]">browse</span>
            </p>
            <p className="text-xs text-slate-500 mt-1">
              Supports Excel (.xlsx, .xls), CSV (.csv), and JSON (.json) up to 5 MB
            </p>
          </div>
        )}

        {isParsing && (
          <div className="flex flex-col items-center justify-center py-10">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-[#2563EB] border-t-transparent mb-3" />
            <p className="text-xs font-semibold text-slate-600">Reading and validating questions...</p>
          </div>
        )}

        {parseError && <Alert tone="error">{parseError}</Alert>}
        {importError && <Alert tone="error">{importError}</Alert>}

        {/* Parse Preview & Validation Screen */}
        {parseResult && (
          <div className="space-y-4">
            {/* Header with File Info & Stats */}
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white p-4">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50 text-[#2563EB]">
                  <Icon name="fileSpreadsheet" size={20} />
                </div>
                <div>
                  <h4 className="text-xs font-bold text-slate-900">{parseResult.fileName}</h4>
                  <p className="text-[11px] text-slate-400">
                    {(parseResult.fileSize / 1024).toFixed(1)} KB · {parseResult.totalRows} questions in file
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => {
                    setParseResult(null);
                    setParseError(null);
                  }}
                >
                  Change file
                </Button>
              </div>
            </div>

            {/* Tabs: Valid vs Invalid */}
            <div className="flex items-center gap-2 border-b border-slate-200 pb-2">
              <button
                type="button"
                onClick={() => setActiveTab("valid")}
                className={cn(
                  "inline-flex items-center gap-2 px-3.5 py-1.5 rounded-xl text-xs font-bold cursor-pointer transition-colors",
                  activeTab === "valid"
                    ? "bg-[#2563EB] text-white shadow-2xs"
                    : "text-slate-600 hover:bg-slate-100"
                )}
              >
                <Icon name="checkCircle" size={14} />
                <span>Valid Questions ({validRows.length})</span>
              </button>

              <button
                type="button"
                onClick={() => setActiveTab("invalid")}
                className={cn(
                  "inline-flex items-center gap-2 px-3.5 py-1.5 rounded-xl text-xs font-bold cursor-pointer transition-colors",
                  activeTab === "invalid"
                    ? "bg-rose-600 text-white shadow-2xs"
                    : invalidRows.length > 0
                    ? "text-rose-700 bg-rose-50 hover:bg-rose-100"
                    : "text-slate-500 hover:bg-slate-100"
                )}
              >
                <Icon name="alertCircle" size={14} />
                <span>Invalid Questions ({invalidRows.length})</span>
              </button>
            </div>

            {/* TAB 1: Valid Questions List */}
            {activeTab === "valid" && (
              <div className="max-h-72 overflow-y-auto rounded-2xl border border-slate-200 bg-white divide-y divide-slate-100">
                {validRows.length === 0 ? (
                  <div className="p-8 text-center text-xs text-slate-500">
                    No valid questions found in this file. Please fix errors under the "Invalid Questions" tab.
                  </div>
                ) : (
                  validRows.map((r, idx) => (
                    <div key={r.rowNumber} className="p-3.5 hover:bg-slate-50/60 transition-colors">
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-start gap-2.5">
                          <span className="flex h-5 w-5 items-center justify-center rounded-md bg-emerald-50 text-[10px] font-bold text-emerald-700 shrink-0 mt-0.5">
                            {idx + 1}
                          </span>
                          <div>
                            <p className="text-xs font-semibold text-slate-900 leading-snug">{r.question}</p>
                            <div className="flex flex-wrap items-center gap-2 mt-1.5 text-[11px] text-slate-500">
                              <span className="font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded">
                                Correct: Option {r.correctOptionId?.toUpperCase()} ({r.correctAnswer})
                              </span>
                              <span>·</span>
                              <span>{r.marks} {r.marks === 1 ? "mark" : "marks"}</span>
                              {r.warnings.length > 0 && (
                                <Badge tone="amber">{r.warnings[0]}</Badge>
                              )}
                            </div>
                          </div>
                        </div>

                        <Badge tone="green">Ready</Badge>
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}

            {/* TAB 2: Invalid Questions with Row-specific error reasons & inline editor */}
            {activeTab === "invalid" && (
              <div className="max-h-80 overflow-y-auto rounded-2xl border border-slate-200 bg-white divide-y divide-slate-100">
                {invalidRows.length === 0 ? (
                  <div className="p-8 text-center text-xs font-semibold text-emerald-700 bg-emerald-50/50">
                    All questions are valid! No errors found.
                  </div>
                ) : (
                  invalidRows.map((r) => {
                    const isEditing = editingRowNumber === r.rowNumber;

                    return (
                      <div key={r.rowNumber} className="p-4 bg-rose-50/30">
                        {isEditing && editRowDraft ? (
                          /* Inline Editor Form */
                          <div className="space-y-3 rounded-xl border border-rose-300 bg-white p-3.5 shadow-2xs">
                            <div className="flex items-center justify-between">
                              <span className="text-xs font-bold text-slate-800">
                                Editing Row #{r.rowNumber}
                              </span>
                              <span className="text-[11px] text-slate-400">Fix required fields</span>
                            </div>

                            <div>
                              <label className="block text-[11px] font-bold text-slate-700 mb-1">Question</label>
                              <input
                                type="text"
                                value={editRowDraft.question}
                                onChange={(e) =>
                                  setEditRowDraft({ ...editRowDraft, question: e.target.value })
                                }
                                className="w-full rounded-lg border border-slate-300 px-2.5 py-1.5 text-xs text-slate-800"
                              />
                            </div>

                            <div className="grid grid-cols-2 gap-2">
                              <div>
                                <label className="block text-[11px] font-bold text-slate-700 mb-1">Option A</label>
                                <input
                                  type="text"
                                  value={editRowDraft.optionA}
                                  onChange={(e) =>
                                    setEditRowDraft({ ...editRowDraft, optionA: e.target.value })
                                  }
                                  className="w-full rounded-lg border border-slate-300 px-2.5 py-1.5 text-xs text-slate-800"
                                />
                              </div>
                              <div>
                                <label className="block text-[11px] font-bold text-slate-700 mb-1">Option B</label>
                                <input
                                  type="text"
                                  value={editRowDraft.optionB}
                                  onChange={(e) =>
                                    setEditRowDraft({ ...editRowDraft, optionB: e.target.value })
                                  }
                                  className="w-full rounded-lg border border-slate-300 px-2.5 py-1.5 text-xs text-slate-800"
                                />
                              </div>
                              <div>
                                <label className="block text-[11px] font-bold text-slate-700 mb-1">Option C</label>
                                <input
                                  type="text"
                                  value={editRowDraft.optionC}
                                  onChange={(e) =>
                                    setEditRowDraft({ ...editRowDraft, optionC: e.target.value })
                                  }
                                  className="w-full rounded-lg border border-slate-300 px-2.5 py-1.5 text-xs text-slate-800"
                                />
                              </div>
                              <div>
                                <label className="block text-[11px] font-bold text-slate-700 mb-1">Option D</label>
                                <input
                                  type="text"
                                  value={editRowDraft.optionD}
                                  onChange={(e) =>
                                    setEditRowDraft({ ...editRowDraft, optionD: e.target.value })
                                  }
                                  className="w-full rounded-lg border border-slate-300 px-2.5 py-1.5 text-xs text-slate-800"
                                />
                              </div>
                            </div>

                            <div className="grid grid-cols-2 gap-2">
                              <div>
                                <label className="block text-[11px] font-bold text-slate-700 mb-1">
                                  Correct Answer (A, B, C, or D)
                                </label>
                                <input
                                  type="text"
                                  value={editRowDraft.correctAnswer}
                                  onChange={(e) =>
                                    setEditRowDraft({ ...editRowDraft, correctAnswer: e.target.value })
                                  }
                                  className="w-full rounded-lg border border-slate-300 px-2.5 py-1.5 text-xs text-slate-800"
                                />
                              </div>
                              <div>
                                <label className="block text-[11px] font-bold text-slate-700 mb-1">Marks</label>
                                <input
                                  type="number"
                                  min={1}
                                  value={editRowDraft.marks}
                                  onChange={(e) =>
                                    setEditRowDraft({ ...editRowDraft, marks: Number(e.target.value) })
                                  }
                                  className="w-full rounded-lg border border-slate-300 px-2.5 py-1.5 text-xs text-slate-800"
                                />
                              </div>
                            </div>

                            <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
                              <Button
                                type="button"
                                variant="secondary"
                                size="sm"
                                onClick={() => {
                                  setEditingRowNumber(null);
                                  setEditRowDraft(null);
                                }}
                              >
                                Cancel
                              </Button>
                              <Button
                                type="button"
                                size="sm"
                                onClick={() => handleSaveEditRow(r.rowNumber)}
                                className="bg-[#2563EB] text-white"
                              >
                                Save & Re-validate
                              </Button>
                            </div>
                          </div>
                        ) : (
                          /* View Mode of Invalid Row */
                          <div className="space-y-2">
                            <div className="flex items-start justify-between gap-3">
                              <div className="flex items-center gap-2">
                                <span className="flex h-5 w-5 items-center justify-center rounded-md bg-rose-100 text-[10px] font-bold text-rose-700">
                                  Row {r.rowNumber}
                                </span>
                                <span className="text-xs font-bold text-slate-800 line-clamp-1">
                                  {r.question || "(Empty question text)"}
                                </span>
                              </div>

                              <div className="flex items-center gap-2">
                                <Button
                                  type="button"
                                  variant="secondary"
                                  size="sm"
                                  icon="edit"
                                  onClick={() => handleStartEditRow(r)}
                                  className="text-xs"
                                >
                                  Edit Row
                                </Button>
                                <button
                                  type="button"
                                  onClick={() => handleRemoveRow(r.rowNumber)}
                                  className="p-1 rounded text-slate-400 hover:text-rose-600 hover:bg-rose-50 cursor-pointer"
                                  title="Remove from import"
                                >
                                  <Icon name="trash" size={14} />
                                </button>
                              </div>
                            </div>

                            {/* Specific Error Reasons */}
                            <div className="space-y-1">
                              {r.errors.map((err, errIdx) => (
                                <div
                                  key={errIdx}
                                  className="flex items-center gap-1.5 text-[11px] font-semibold text-rose-700"
                                >
                                  <Icon name="alertCircle" size={12} className="shrink-0" />
                                  <span>{err}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })
                )}
              </div>
            )}

            {/* Import Progress Indicator */}
            {isImporting && importProgress && (
              <div className="rounded-xl border border-blue-200 bg-blue-50/70 p-3.5 space-y-2">
                <div className="flex items-center justify-between text-xs font-bold text-blue-900">
                  <span>Importing questions to test...</span>
                  <span>
                    {importProgress.completed} / {importProgress.total}
                  </span>
                </div>
                <div className="h-2 w-full rounded-full bg-blue-100 overflow-hidden">
                  <div
                    className="h-full bg-[#2563EB] transition-all duration-300"
                    style={{
                      width: `${(importProgress.completed / Math.max(importProgress.total, 1)) * 100}%`,
                    }}
                  />
                </div>
              </div>
            )}
          </div>
        )}

        {/* Modal Actions */}
        <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-200">
          <Button
            type="button"
            variant="secondary"
            onClick={onClose}
            disabled={isImporting}
          >
            Cancel
          </Button>

          {parseResult && (
            <Button
              type="button"
              disabled={validRows.length === 0 || isImporting}
              loading={isImporting}
              onClick={() => void handleConfirmImport()}
              className="bg-[#2563EB] text-white hover:bg-blue-700 font-bold"
            >
              Import {validRows.length} Valid Question{validRows.length === 1 ? "" : "s"}
            </Button>
          )}
        </div>
      </div>
    </Modal>
  );
}

import { useRef, useState, type DragEvent } from "react";

import { cn } from "@/core/lib/cn";
import type { McqDraft } from "@/modules/catalog/course-tests/hooks/useTestQuestions";
import {
  downloadExcelTemplate,
  parseExcelQuestions,
  type ParseResult,
} from "@/modules/catalog/course-tests/utils/excelQuestions";
import { Alert, Badge, Button, Icon, Modal, Spinner } from "@/shared/ui";

interface ImportExcelModalProps {
  existingQuestions?: string[];
  onClose: () => void;
  onImport: (
    drafts: McqDraft[],
    onProgress: (completed: number, total: number) => void
  ) => Promise<unknown>;
}

export function ImportExcelModal({
  existingQuestions = [],
  onClose,
  onImport,
}: ImportExcelModalProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [parseResult, setParseResult] = useState<ParseResult | null>(null);
  const [parseError, setParseError] = useState<string | null>(null);
  const [isParsing, setIsParsing] = useState(false);

  // Import execution states
  const [isImporting, setIsImporting] = useState(false);
  const [importProgress, setImportProgress] = useState<{
    completed: number;
    total: number;
  } | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [filterMode, setFilterMode] = useState<"all" | "valid" | "errors">("all");

  const processFile = async (file: File) => {
    const isExcel =
      file.name.toLowerCase().endsWith(".xlsx") ||
      file.name.toLowerCase().endsWith(".xls") ||
      file.type === "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" ||
      file.type === "application/vnd.ms-excel";

    if (!isExcel) {
      setParseError("Please select a valid Excel file (.xlsx or .xls).");
      setSelectedFile(null);
      setParseResult(null);
      return;
    }

    setSelectedFile(file);
    setParseError(null);
    setImportError(null);
    setIsParsing(true);

    try {
      const result = await parseExcelQuestions(file, existingQuestions);
      setParseResult(result);
    } catch (err: unknown) {
      setParseResult(null);
      setParseError(
        err instanceof Error ? err.message : "Failed to parse the Excel worksheet."
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

  const handleConfirmImport = async () => {
    if (!parseResult) return;
    const validDrafts = parseResult.rows
      .filter((r) => r.status !== "error" && r.draft)
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
      setIsImporting(false);
      setImportProgress(null);
      setImportError(
        err instanceof Error
          ? err.message
          : "Failed to import questions to the test. Please try again."
      );
    }
  };

  const filteredRows = parseResult?.rows.filter((row) => {
    if (filterMode === "valid") return row.status !== "error";
    if (filterMode === "errors") return row.status === "error";
    return true;
  }) || [];

  const formatFileSize = (bytes: number) => {
    if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  };

  return (
    <Modal
      open
      onClose={isImporting ? () => {} : onClose}
      size="lg"
      title="Import Questions from Excel"
      description="Upload a .xlsx or .xls file to batch import multiple-choice questions into this test."
      footer={
        <div className="flex w-full flex-wrap items-center justify-between gap-3">
          <Button
            variant="ghost"
            size="sm"
            icon="download"
            onClick={downloadExcelTemplate}
            disabled={isImporting}
            className="text-emerald-700 hover:text-emerald-800"
          >
            Download Excel Template
          </Button>
          <div className="flex items-center gap-2">
            <Button variant="secondary" onClick={onClose} disabled={isImporting}>
              Cancel
            </Button>
            <Button
              variant="primary"
              icon="upload"
              disabled={!parseResult || parseResult.validCount === 0 || isImporting}
              loading={isImporting}
              onClick={() => void handleConfirmImport()}
              className="bg-emerald-600 hover:bg-emerald-700"
            >
              {isImporting
                ? `Importing (${importProgress?.completed || 0}/${importProgress?.total || 0})...`
                : parseResult
                ? `Import ${parseResult.validCount} Question${parseResult.validCount === 1 ? "" : "s"}`
                : "Import Questions"}
            </Button>
          </div>
        </div>
      }
    >
      <div className="space-y-4">
        {/* Template Instructions Banner */}
        <div className="rounded-xl border border-emerald-200/80 bg-emerald-50/60 p-3.5 text-xs text-emerald-950">
          <div className="flex flex-wrap items-center justify-between gap-2 font-semibold">
            <div className="flex items-center gap-1.5 text-emerald-900 font-bold">
              <Icon name="fileSpreadsheet" size={16} className="text-emerald-700" />
              <span>Required Excel Columns:</span>
            </div>
            <button
              type="button"
              onClick={downloadExcelTemplate}
              className="inline-flex items-center gap-1 font-bold text-emerald-800 underline decoration-emerald-400 hover:text-emerald-950"
            >
              <Icon name="download" size={13} />
              Download pre-filled template (.xlsx)
            </button>
          </div>
          <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 sm:grid-cols-4 text-[11px] text-emerald-900/90 font-mono">
            <div>• Question <span className="text-emerald-700 font-sans font-bold">(required)</span></div>
            <div>• Option A <span className="text-emerald-700 font-sans font-bold">(required)</span></div>
            <div>• Option B <span className="text-emerald-700 font-sans font-bold">(required)</span></div>
            <div>• Correct Answer <span className="text-emerald-700 font-sans font-bold">(A/B/C/D)</span></div>
            <div>• Option C <span className="text-slate-500 font-sans">(optional)</span></div>
            <div>• Option D <span className="text-slate-500 font-sans">(optional)</span></div>
            <div>• Marks <span className="text-slate-500 font-sans">(def: 1)</span></div>
            <div>• Explanation <span className="text-slate-500 font-sans">(optional)</span></div>
          </div>
        </div>

        {/* Drag and Drop Upload Area */}
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          onClick={() => !isImporting && fileInputRef.current?.click()}
          className={cn(
            "relative flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed p-6 text-center transition-all",
            dragging
              ? "border-emerald-500 bg-emerald-50/80"
              : selectedFile
              ? "border-emerald-300 bg-emerald-50/30"
              : "border-slate-300 bg-slate-50/60 hover:border-slate-400 hover:bg-slate-100/50"
          )}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".xlsx, .xls, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/vnd.ms-excel"
            className="hidden"
            onChange={(e) => {
              if (e.target.files?.[0]) {
                void processFile(e.target.files[0]);
              }
              e.target.value = "";
            }}
          />

          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-700 shadow-sm">
            <Icon name="fileSpreadsheet" size={24} />
          </div>

          {selectedFile ? (
            <div className="mt-2 space-y-1">
              <p className="text-sm font-bold text-navy-950">{selectedFile.name}</p>
              <p className="text-xs text-slate-500">
                {formatFileSize(selectedFile.size)} · Click or drop another file to replace
              </p>
            </div>
          ) : (
            <div className="mt-2 space-y-1">
              <p className="text-sm font-bold text-navy-950">
                Drag and drop your Excel file here, or{" "}
                <span className="text-emerald-700 underline decoration-emerald-400 hover:text-emerald-800">
                  browse
                </span>
              </p>
              <p className="text-xs text-slate-500">Supports .xlsx and .xls spreadsheets</p>
            </div>
          )}
        </div>

        {/* Parsing state */}
        {isParsing && (
          <div className="flex items-center justify-center gap-2 rounded-xl bg-slate-50 p-4 text-xs font-semibold text-slate-600">
            <Spinner size={16} />
            <span>Reading and validating Excel questions...</span>
          </div>
        )}

        {/* Parse or Import Errors */}
        {parseError && <Alert tone="error">{parseError}</Alert>}
        {importError && <Alert tone="error">{importError}</Alert>}

        {/* Import Progress Bar */}
        {isImporting && importProgress && (
          <div className="space-y-1.5 rounded-xl border border-emerald-200 bg-emerald-50/60 p-4">
            <div className="flex items-center justify-between text-xs font-bold text-emerald-950">
              <span className="flex items-center gap-2">
                <Spinner size={14} />
                Importing questions into Topic Test...
              </span>
              <span>
                {importProgress.completed} of {importProgress.total} (
                {Math.round((importProgress.completed / importProgress.total) * 100)}%)
              </span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-emerald-200">
              <div
                className="h-full bg-emerald-600 transition-all duration-200"
                style={{
                  width: `${(importProgress.completed / importProgress.total) * 100}%`,
                }}
              />
            </div>
          </div>
        )}

        {/* Preview Section */}
        {parseResult && !isParsing && (
          <div className="space-y-3">
            {/* Status counts bar */}
            <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-200 bg-slate-50/70 px-3 py-2 text-xs">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-bold text-slate-700">
                  Parsed {parseResult.totalRows} question{parseResult.totalRows === 1 ? "" : "s"}:
                </span>
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 font-bold text-emerald-800">
                  <Icon name="check" size={12} /> {parseResult.validCount} valid
                </span>
                {parseResult.errorCount > 0 && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 font-bold text-red-800">
                    <Icon name="alert" size={12} /> {parseResult.errorCount} error
                    {parseResult.errorCount === 1 ? "" : "s"}
                  </span>
                )}
                {parseResult.warningCount > 0 && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 font-bold text-amber-800">
                    <Icon name="info" size={12} /> {parseResult.warningCount} duplicate warning
                    {parseResult.warningCount === 1 ? "" : "s"}
                  </span>
                )}
              </div>

              {/* Filter Tabs */}
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => setFilterMode("all")}
                  className={cn(
                    "rounded-md px-2 py-1 text-xs font-semibold transition-colors",
                    filterMode === "all"
                      ? "bg-white text-navy-950 shadow-sm"
                      : "text-slate-600 hover:text-slate-900"
                  )}
                >
                  All ({parseResult.rows.length})
                </button>
                <button
                  type="button"
                  onClick={() => setFilterMode("valid")}
                  className={cn(
                    "rounded-md px-2 py-1 text-xs font-semibold transition-colors",
                    filterMode === "valid"
                      ? "bg-white text-emerald-800 shadow-sm"
                      : "text-slate-600 hover:text-slate-900"
                  )}
                >
                  Valid ({parseResult.validCount})
                </button>
                {parseResult.errorCount > 0 && (
                  <button
                    type="button"
                    onClick={() => setFilterMode("errors")}
                    className={cn(
                      "rounded-md px-2 py-1 text-xs font-semibold transition-colors",
                      filterMode === "errors"
                        ? "bg-white text-red-700 shadow-sm"
                        : "text-slate-600 hover:text-slate-900"
                    )}
                  >
                    Errors ({parseResult.errorCount})
                  </button>
                )}
              </div>
            </div>

            {/* Questions Preview Table */}
            <div className="max-h-72 overflow-y-auto rounded-xl border border-slate-200">
              <table className="w-full border-collapse text-left text-xs">
                <thead className="sticky top-0 z-10 bg-slate-100 text-[11px] font-extrabold uppercase tracking-wider text-slate-600">
                  <tr>
                    <th className="px-3 py-2.5">Row</th>
                    <th className="px-3 py-2.5">Question & Options</th>
                    <th className="px-3 py-2.5">Correct Answer</th>
                    <th className="px-3 py-2.5">Marks</th>
                    <th className="px-3 py-2.5">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 bg-white">
                  {filteredRows.map((row) => (
                    <tr
                      key={row.rowNumber}
                      className={cn(
                        "transition-colors",
                        row.status === "error"
                          ? "bg-red-50/30 hover:bg-red-50/50"
                          : row.status === "warning"
                          ? "bg-amber-50/20 hover:bg-amber-50/40"
                          : "hover:bg-slate-50/60"
                      )}
                    >
                      <td className="px-3 py-2.5 font-mono text-slate-500 font-semibold align-top">
                        #{row.rowNumber}
                      </td>
                      <td className="px-3 py-2.5 align-top">
                        <p className="font-bold text-navy-950">{row.question || <span className="text-red-500 italic">Missing question</span>}</p>
                        <div className="mt-1 flex flex-wrap gap-1 text-[11px]">
                          {row.optionA && (
                            <span className={cn("rounded px-1.5 py-0.5", row.correctOptionId === "a" ? "bg-emerald-100 font-bold text-emerald-900 border border-emerald-300" : "bg-slate-100 text-slate-700")}>
                              <strong>A:</strong> {row.optionA}
                            </span>
                          )}
                          {row.optionB && (
                            <span className={cn("rounded px-1.5 py-0.5", row.correctOptionId === "b" ? "bg-emerald-100 font-bold text-emerald-900 border border-emerald-300" : "bg-slate-100 text-slate-700")}>
                              <strong>B:</strong> {row.optionB}
                            </span>
                          )}
                          {row.optionC && (
                            <span className={cn("rounded px-1.5 py-0.5", row.correctOptionId === "c" ? "bg-emerald-100 font-bold text-emerald-900 border border-emerald-300" : "bg-slate-100 text-slate-700")}>
                              <strong>C:</strong> {row.optionC}
                            </span>
                          )}
                          {row.optionD && (
                            <span className={cn("rounded px-1.5 py-0.5", row.correctOptionId === "d" ? "bg-emerald-100 font-bold text-emerald-900 border border-emerald-300" : "bg-slate-100 text-slate-700")}>
                              <strong>D:</strong> {row.optionD}
                            </span>
                          )}
                        </div>
                        {row.explanation && (
                          <p className="mt-1 text-[11px] text-slate-500 italic">
                            💡 {row.explanation}
                          </p>
                        )}
                        {/* Errors & Warnings inside row */}
                        {row.errors.length > 0 && (
                          <div className="mt-1.5 space-y-0.5 text-[11px] font-semibold text-red-600">
                            {row.errors.map((e, idx) => (
                              <div key={idx} className="flex items-center gap-1">
                                <Icon name="alert" size={12} /> {e}
                              </div>
                            ))}
                          </div>
                        )}
                        {row.warnings.length > 0 && (
                          <div className="mt-1 space-y-0.5 text-[11px] font-semibold text-amber-600">
                            {row.warnings.map((w, idx) => (
                              <div key={idx} className="flex items-center gap-1">
                                <Icon name="info" size={12} /> {w}
                              </div>
                            ))}
                          </div>
                        )}
                      </td>
                      <td className="px-3 py-2.5 align-top whitespace-nowrap">
                        {row.correctOptionId ? (
                          <span className="inline-flex items-center rounded-md bg-emerald-50 px-2 py-0.5 font-bold uppercase text-emerald-700 ring-1 ring-emerald-600/20">
                            Option {row.correctOptionId.toUpperCase()}
                          </span>
                        ) : (
                          <span className="inline-flex items-center rounded-md bg-red-50 px-2 py-0.5 font-bold text-red-700 ring-1 ring-red-600/20">
                            {row.correctAnswer || "None"}
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-2.5 font-bold text-slate-700 align-top whitespace-nowrap">
                        {row.marks} pt{row.marks === 1 ? "" : "s"}
                      </td>
                      <td className="px-3 py-2.5 align-top whitespace-nowrap">
                        {row.status === "valid" ? (
                          <Badge tone="green">Valid</Badge>
                        ) : row.status === "warning" ? (
                          <Badge tone="amber">Duplicate</Badge>
                        ) : (
                          <Badge tone="red">Error</Badge>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}

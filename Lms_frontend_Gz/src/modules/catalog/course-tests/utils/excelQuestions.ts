import * as XLSX from "xlsx";
import type { McqDraft } from "@/modules/catalog/course-tests/hooks/useTestQuestions";

export interface ParsedQuestionRow {
  rowNumber: number;
  question: string;
  questionType?: string;
  optionA: string;
  optionB: string;
  optionC: string;
  optionD: string;
  correctAnswer: string;
  correctOptionId: "a" | "b" | "c" | "d" | null;
  marks: number;
  explanation: string;
  status: "valid" | "error" | "warning";
  errors: string[];
  warnings: string[];
  draft: McqDraft | null;
}

export interface ParseResult {
  fileName: string;
  fileSize: number;
  totalRows: number;
  validCount: number;
  errorCount: number;
  warningCount: number;
  rows: ParsedQuestionRow[];
}

/**
 * Generates and downloads a clean, professional Excel template (.xlsx)
 * with sample questions and an instructions sheet.
 */
export function downloadExcelTemplate(): void {
  const wb = XLSX.utils.book_new();

  // 1. Questions Worksheet with sample data
  const headers = [
    "Question",
    "Option A",
    "Option B",
    "Option C",
    "Option D",
    "Correct Answer",
    "Marks",
    "Explanation",
  ];

  const sampleData = [
    [
      "What is Python?",
      "Programming language",
      "Operating system",
      "Web browser",
      "Database",
      "A",
      1,
      "Python is a high-level, interpreted programming language.",
    ],
    [
      "Which keyword defines a function in Python?",
      "function",
      "def",
      "fun",
      "define",
      "B",
      1,
      "The def keyword is used to define functions in Python.",
    ],
    [
      "Which data type stores True or False?",
      "String",
      "Integer",
      "Boolean",
      "List",
      "C",
      2,
      "Boolean data type represents truth values True or False.",
    ],
  ];

  const wsQuestions = XLSX.utils.aoa_to_sheet([headers, ...sampleData]);

  // Set column widths
  wsQuestions["!cols"] = [
    { wch: 45 }, // Question
    { wch: 25 }, // Option A
    { wch: 25 }, // Option B
    { wch: 25 }, // Option C
    { wch: 25 }, // Option D
    { wch: 16 }, // Correct Answer
    { wch: 10 }, // Marks
    { wch: 45 }, // Explanation
  ];

  XLSX.utils.book_append_sheet(wb, wsQuestions, "Questions");

  // 2. Instructions Worksheet
  const instructions = [
    ["ExamLMS - Questions Import Instructions"],
    [""],
    ["Column", "Required", "Description & Rules"],
    ["Question", "Yes", "The full question text. Cannot be empty."],
    ["Option A", "Yes", "First answer option."],
    ["Option B", "Yes", "Second answer option."],
    ["Option C", "Optional", "Third answer option (leave empty if only 2 options)."],
    ["Option D", "Optional", "Fourth answer option."],
    [
      "Correct Answer",
      "Yes",
      "The correct choice. Enter 'A', 'B', 'C', or 'D' (or the exact text of the correct option).",
    ],
    ["Marks", "Optional", "Points awarded for a correct answer. Positive number. Defaults to 1 if blank."],
    ["Explanation", "Optional", "Explanation or rationale shown to students after test completion."],
    [""],
    ["Tips:"],
    ["- Do not modify or remove the header row in the 'Questions' sheet."],
    ["- Each question must have at least 2 options (Option A and Option B)."],
    ["- Empty rows are automatically ignored."],
    ["- Supported file formats: .xlsx, .xls, .csv, and .json"],
  ];

  const wsInstructions = XLSX.utils.aoa_to_sheet(instructions);
  wsInstructions["!cols"] = [{ wch: 20 }, { wch: 12 }, { wch: 70 }];

  XLSX.utils.book_append_sheet(wb, wsInstructions, "Instructions");

  // Write and trigger download
  XLSX.writeFile(wb, "examlms_questions_template.xlsx");
}

/**
 * Generates and downloads a sample JSON template (.json)
 */
export function downloadJsonTemplate(): void {
  const sampleJson = [
    {
      question: "What is Python?",
      optionA: "Programming language",
      optionB: "Operating system",
      optionC: "Web browser",
      optionD: "Database",
      correctAnswer: "A",
      marks: 1,
      explanation: "Python is a high-level, interpreted programming language.",
    },
    {
      question: "Which keyword defines a function in Python?",
      optionA: "function",
      optionB: "def",
      optionC: "fun",
      optionD: "define",
      correctAnswer: "B",
      marks: 1,
      explanation: "The def keyword is used to define functions in Python.",
    },
    {
      question: "Which data type stores True or False?",
      optionA: "String",
      optionB: "Integer",
      optionC: "Boolean",
      optionD: "List",
      correctAnswer: "C",
      marks: 2,
      explanation: "Boolean data type represents truth values True or False.",
    },
  ];

  const blob = new Blob([JSON.stringify(sampleJson, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "examlms_questions_template.json";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/**
 * Normalizes header string to standard property key.
 */
function normalizeHeader(raw: string): string {
  const clean = raw.toLowerCase().trim().replace(/[\s_-]+/g, "");
  if (clean.includes("question") || clean === "q") return "question";
  if (clean === "optiona" || clean === "opta" || clean === "a" || clean === "option1") return "optionA";
  if (clean === "optionb" || clean === "optb" || clean === "b" || clean === "option2") return "optionB";
  if (clean === "optionc" || clean === "optc" || clean === "c" || clean === "option3") return "optionC";
  if (clean === "optiond" || clean === "optd" || clean === "d" || clean === "option4") return "optionD";
  if (clean.includes("correct") || clean === "answer" || clean === "ans") return "correctAnswer";
  if (clean.includes("mark") || clean.includes("point") || clean.includes("score")) return "marks";
  if (clean.includes("explain") || clean.includes("rationale") || clean.includes("reason")) return "explanation";
  if (clean.includes("type")) return "questionType";
  return clean;
}

/**
 * Resolves the correct option id ("a", "b", "c", or "d") from the Correct Answer value.
 */
export function resolveCorrectOption(
  rawAnswer: string,
  options: { a: string; b: string; c: string; d: string }
): "a" | "b" | "c" | "d" | null {
  const trimmed = rawAnswer.trim();
  if (!trimmed) return null;

  const lower = trimmed.toLowerCase();

  // 1. Direct letter matching: 'A', 'B', 'C', 'D' or 'Option A'
  if (lower === "a" || lower === "option a" || lower === "optiona" || lower === "1") {
    return options.a ? "a" : null;
  }
  if (lower === "b" || lower === "option b" || lower === "optionb" || lower === "2") {
    return options.b ? "b" : null;
  }
  if (lower === "c" || lower === "option c" || lower === "optionc" || lower === "3") {
    return options.c ? "c" : null;
  }
  if (lower === "d" || lower === "option d" || lower === "optiond" || lower === "4") {
    return options.d ? "d" : null;
  }

  // 2. Text matching against option values
  if (options.a && lower === options.a.trim().toLowerCase()) return "a";
  if (options.b && lower === options.b.trim().toLowerCase()) return "b";
  if (options.c && lower === options.c.trim().toLowerCase()) return "c";
  if (options.d && lower === options.d.trim().toLowerCase()) return "d";

  return null;
}

/**
 * Validates a single row (used during parsing and when editing an invalid row in preview).
 */
export function validateQuestionRow(
  input: {
    rowNumber: number;
    question: string;
    questionType?: string;
    optionA: string;
    optionB: string;
    optionC?: string;
    optionD?: string;
    correctAnswer: string;
    marks?: number | string;
    explanation?: string;
  },
  existingQuestions: string[] = []
): ParsedQuestionRow {
  const questionText = (input.question || "").trim();
  const optionA = (input.optionA || "").trim();
  const optionB = (input.optionB || "").trim();
  const optionC = (input.optionC || "").trim();
  const optionD = (input.optionD || "").trim();
  const rawCorrectAnswer = (input.correctAnswer || "").trim();
  const explanation = (input.explanation || "").trim();

  const errors: string[] = [];
  const warnings: string[] = [];

  // 1. Question validation
  if (!questionText) {
    errors.push("Question text is required.");
  }

  // 2. Options validation (at least 2 options: A and B)
  if (!optionA) {
    errors.push("Option A is required.");
  }
  if (!optionB) {
    errors.push("Option B is required.");
  }

  const optionsMap = { a: optionA, b: optionB, c: optionC, d: optionD };

  // 3. Correct answer validation
  if (!rawCorrectAnswer) {
    errors.push("Correct answer is required (e.g. 'A', 'B', 'C', or 'D').");
  }

  const correctOptionId = resolveCorrectOption(rawCorrectAnswer, optionsMap);
  if (rawCorrectAnswer && !correctOptionId) {
    errors.push(
      `Correct answer '${rawCorrectAnswer}' does not match any provided option (Option A, B, C, or D).`
    );
  }

  // 4. Marks validation
  let marks = 1;
  if (input.marks !== undefined && input.marks !== "") {
    const parsedNum = typeof input.marks === "number" ? input.marks : parseFloat(String(input.marks));
    if (isNaN(parsedNum) || parsedNum <= 0) {
      errors.push("Marks must be a positive number.");
    } else {
      marks = parsedNum;
    }
  }

  // 5. Existing duplicate checks
  if (questionText && existingQuestions.length > 0) {
    const qLower = questionText.toLowerCase();
    const matched = existingQuestions.some((q) => q.trim().toLowerCase() === qLower);
    if (matched) {
      warnings.push("This question already exists in this test.");
    }
  }

  const status: "valid" | "error" | "warning" =
    errors.length > 0 ? "error" : warnings.length > 0 ? "warning" : "valid";

  let draft: McqDraft | null = null;
  if (status !== "error" && correctOptionId) {
    const optionsList = [
      { id: "a", text: optionA },
      { id: "b", text: optionB },
      ...(optionC ? [{ id: "c", text: optionC }] : []),
      ...(optionD ? [{ id: "d", text: optionD }] : []),
    ];

    draft = {
      text: questionText,
      options: optionsList,
      correct: correctOptionId,
      explanation: explanation || "",
      marks,
    };
  }

  return {
    rowNumber: input.rowNumber,
    question: questionText,
    questionType: input.questionType || "mcq_single",
    optionA,
    optionB,
    optionC,
    optionD,
    correctAnswer: rawCorrectAnswer,
    correctOptionId,
    marks,
    explanation,
    status,
    errors,
    warnings,
    draft,
  };
}

/**
 * Parses an Excel (.xlsx/.xls) or CSV (.csv) or JSON (.json) file into structured records with validation.
 */
export async function parseQuestionsFile(
  file: File,
  existingQuestions: string[] = []
): Promise<ParseResult> {
  const fileName = file.name.toLowerCase();

  // If JSON file
  if (fileName.endsWith(".json") || file.type === "application/json") {
    return parseJsonQuestions(file, existingQuestions);
  }

  // If Excel or CSV
  const buffer = await file.arrayBuffer();
  const workbook = XLSX.read(buffer, { type: "array" });

  // Select target sheet: prefer "Questions", otherwise the first sheet
  const sheetName =
    workbook.SheetNames.find((name) => name.toLowerCase().includes("question")) ||
    workbook.SheetNames[0];

  if (!sheetName) {
    throw new Error("The file contains no valid sheets or data.");
  }

  const worksheet = workbook.Sheets[sheetName];
  if (!worksheet) {
    throw new Error(`Sheet '${sheetName}' could not be read.`);
  }

  // Read all rows as 2D array of strings
  const rawData = XLSX.utils.sheet_to_json<string[]>(worksheet, {
    header: 1,
    blankrows: false,
    defval: "",
  });

  if (!rawData.length) {
    throw new Error("The selected file is empty.");
  }

  // Locate header row (first non-empty row)
  let headerRowIndex = -1;
  let headerMap: Record<string, number> = {};

  for (let i = 0; i < rawData.length; i++) {
    const row = rawData[i];
    if (!row || !row.length) continue;

    const normalizedMap: Record<string, number> = {};
    row.forEach((col, idx) => {
      const key = normalizeHeader(String(col || ""));
      if (key) normalizedMap[key] = idx;
    });

    if (normalizedMap.question !== undefined) {
      headerRowIndex = i;
      headerMap = normalizedMap;
      break;
    }
  }

  if (headerRowIndex === -1 || headerMap.question === undefined) {
    throw new Error(
      "Missing required columns. Please ensure 'Question', 'Option A', 'Option B', and 'Correct Answer' columns exist."
    );
  }

  const parsedRows: ParsedQuestionRow[] = [];
  const seenQuestionsInFile = new Set<string>();

  for (let rowIndex = headerRowIndex + 1; rowIndex < rawData.length; rowIndex++) {
    const rawRow = rawData[rowIndex] || [];
    const fileRowNumber = rowIndex + 1; // 1-based index in file

    const getVal = (key: string): string => {
      const colIdx = headerMap[key];
      if (colIdx === undefined || colIdx >= rawRow.length) return "";
      return String(rawRow[colIdx] ?? "").trim();
    };

    const questionText = getVal("question");
    const optionA = getVal("optionA");
    const optionB = getVal("optionB");
    const optionC = getVal("optionC");
    const optionD = getVal("optionD");
    const rawCorrectAnswer = getVal("correctAnswer");
    const rawMarks = getVal("marks");
    const explanation = getVal("explanation");
    const questionType = getVal("questionType");

    // Check if the row is entirely blank
    const isRowEmpty =
      !questionText &&
      !optionA &&
      !optionB &&
      !optionC &&
      !optionD &&
      !rawCorrectAnswer;
    if (isRowEmpty) {
      continue;
    }

    const validated = validateQuestionRow(
      {
        rowNumber: fileRowNumber,
        question: questionText,
        questionType,
        optionA,
        optionB,
        optionC,
        optionD,
        correctAnswer: rawCorrectAnswer,
        marks: rawMarks,
        explanation,
      },
      existingQuestions
    );

    if (questionText) {
      const qLower = questionText.toLowerCase();
      if (seenQuestionsInFile.has(qLower)) {
        validated.warnings.push("Duplicate question detected within this file.");
        if (validated.status === "valid") validated.status = "warning";
      } else {
        seenQuestionsInFile.add(qLower);
      }
    }

    parsedRows.push(validated);
  }

  const validCount = parsedRows.filter((r) => r.status === "valid").length;
  const errorCount = parsedRows.filter((r) => r.status === "error").length;
  const warningCount = parsedRows.filter((r) => r.status === "warning").length;

  return {
    fileName: file.name,
    fileSize: file.size,
    totalRows: parsedRows.length,
    validCount: validCount + warningCount,
    errorCount,
    warningCount,
    rows: parsedRows,
  };
}

/**
 * Parses a JSON file containing questions.
 */
async function parseJsonQuestions(
  file: File,
  existingQuestions: string[] = []
): Promise<ParseResult> {
  let parsed: unknown;
  try {
    parsed = JSON.parse(await file.text());
  } catch {
    throw new Error("Invalid JSON file. Please verify the syntax and format.");
  }

  const list = Array.isArray(parsed)
    ? parsed
    : (parsed as { questions?: unknown[] })?.questions;

  if (!Array.isArray(list) || list.length === 0) {
    throw new Error(
      "The JSON file must contain an array of question objects (or an object with a 'questions' array)."
    );
  }

  const parsedRows: ParsedQuestionRow[] = [];
  const seenQuestions = new Set<string>();

  list.forEach((item: any, idx: number) => {
    const rowNumber = idx + 1;
    // Handle both Flat JSON format and Backend nested format
    let question = item.question || item.text || "";
    let questionType = item.questionType || item.question_type || "mcq_single";
    let optionA = item.optionA || "";
    let optionB = item.optionB || "";
    let optionC = item.optionC || "";
    let optionD = item.optionD || "";
    let correctAnswer = item.correctAnswer || item.answer_key?.correct || "";
    let marks = item.marks ?? item.default_marks ?? 1;
    let explanation = item.explanation || item.body?.description || "";

    // If options are in an array
    if (Array.isArray(item.options)) {
      if (typeof item.options[0] === "string") {
        optionA = item.options[0] || "";
        optionB = item.options[1] || "";
        optionC = item.options[2] || "";
        optionD = item.options[3] || "";
      } else if (typeof item.options[0] === "object") {
        optionA = item.options[0]?.text || "";
        optionB = item.options[1]?.text || "";
        optionC = item.options[2]?.text || "";
        optionD = item.options[3]?.text || "";
      }
    } else if (Array.isArray(item.body?.options)) {
      optionA = item.body.options[0]?.text || "";
      optionB = item.body.options[1]?.text || "";
      optionC = item.body.options[2]?.text || "";
      optionD = item.body.options[3]?.text || "";
    }

    const validated = validateQuestionRow(
      {
        rowNumber,
        question,
        questionType,
        optionA,
        optionB,
        optionC,
        optionD,
        correctAnswer: String(correctAnswer),
        marks,
        explanation,
      },
      existingQuestions
    );

    if (question) {
      const qLower = question.toLowerCase();
      if (seenQuestions.has(qLower)) {
        validated.warnings.push("Duplicate question detected in this file.");
        if (validated.status === "valid") validated.status = "warning";
      } else {
        seenQuestions.add(qLower);
      }
    }

    parsedRows.push(validated);
  });

  const validCount = parsedRows.filter((r) => r.status === "valid").length;
  const errorCount = parsedRows.filter((r) => r.status === "error").length;
  const warningCount = parsedRows.filter((r) => r.status === "warning").length;

  return {
    fileName: file.name,
    fileSize: file.size,
    totalRows: parsedRows.length,
    validCount: validCount + warningCount,
    errorCount,
    warningCount,
    rows: parsedRows,
  };
}

// Backwards compatibility alias
export const parseExcelQuestions = parseQuestionsFile;

import React, { useState, useEffect, useRef } from "react";
import { env } from "@/core/config/env";
import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Minimize2,
  X,
  FileText,
  RotateCw,
  AlertCircle,
  Loader2,
  BookOpen,
  CheckCircle2,
  Layers,
  Sparkles,
} from "lucide-react";
import { cn } from "@/core/lib/cn";

export interface InAppPdfViewerProps {
  isOpen: boolean;
  onClose: () => void;
  documentTitle: string;
  pdfUrl?: string;
  mediaId?: string | number | null | undefined;
  totalSlides?: number;
  chapterTitle?: string;
  courseTitle?: string;
  moduleTitle?: string;
}

// Built-in authentic high-yield academic lecture slides for curriculum preview
interface SlideContent {
  page: number;
  title: string;
  subtitle: string;
  keyPoints: string[];
  codeSnippet?: string;
  diagramTitle?: string;
  diagramSteps?: string[];
  takeaways: string;
}

const DEFAULT_SLIDES: SlideContent[] = [
  {
    page: 1,
    title: "1. Core Foundations & Environment Architecture",
    subtitle: "Runtime Execution Model, Memory Hierarchy & Interpreter Lifecycle",
    keyPoints: [
      "CPython byte-code compilation into pyc cache and evaluation in the Python Virtual Machine (PVM).",
      "Dynamic type-checking semantics coupled with strong type invariants.",
      "Garbage collection via reference counting supplemented by cyclic generational collection.",
      "The Global Interpreter Lock (GIL) and modern free-threaded PEP 703 execution models.",
    ],
    codeSnippet: `# Inspecting Bytecode Execution
import dis

def calculate_metrics(items: list[int]) -> int:
    return sum(x * 2 for x in items if x > 0)

dis.dis(calculate_metrics)`,
    diagramTitle: "Python Runtime Architecture Pipeline",
    diagramSteps: ["Source Code (.py)", "Bytecode (.pyc)", "PVM Virtual Machine", "Hardware Execution"],
    takeaways: "Understand how Python translates human-readable scripts into machine execution units.",
  },
  {
    page: 2,
    title: "2. Variable Scopes & Memory References",
    subtitle: "LEGB Rule (Local, Enclosing, Global, Built-in) & Object Identity",
    keyPoints: [
      "Every variable in Python is a reference pointer to an object on the heap.",
      "Immutable vs mutable object semantics: integers, strings, tuples vs lists, dicts, sets.",
      "Namespace resolution follows the strict LEGB resolution order.",
      "Using 'global' and 'nonlocal' keywords safely within nested lexical scopes.",
    ],
    codeSnippet: `x = [1, 2, 3]
y = x          # Shallow reference alias
y.append(4)
print(x is y)  # True: identity equality

z = list(x)    # Distinct shallow copy
print(x == z)  # True: value equality
print(x is z)  # False: unique memory address`,
    takeaways: "Avoid unexpected mutation side-effects by tracking object mutability and identity.",
  },
  {
    page: 3,
    title: "3. Advanced Data Structures & Algorithmic Complexity",
    subtitle: "Hash Tables, Dynamic Arrays, Bisect & Collections Mastery",
    keyPoints: [
      "Hash collisions handling in Python dicts via open addressing and perturbation shifts.",
      "amortized O(1) dictionary and set lookups vs O(N) linear search in unsorted lists.",
      "Utilizing collections.deque for double-ended O(1) queue and stack operations.",
      "Heapq priority queues for top-K streaming element processing.",
    ],
    codeSnippet: `from collections import defaultdict, deque
import heapq

# Frequency table with automatic default initialization
freq = defaultdict(int)
for item in ['alpha', 'beta', 'alpha', 'gamma']:
    freq[item] += 1

# O(log N) Min-heap priority queue
heap = [10, 4, 7, 2, 8]
heapq.heapify(heap)
min_item = heapq.heappop(heap) # returns 2`,
    takeaways: "Select the optimal data structure to achieve asymptotic optimality.",
  },
  {
    page: 4,
    title: "4. Control Flow, Pattern Matching & Comprehensions",
    subtitle: "Structural Pattern Matching (PEP 634) & Memory-Efficient Generators",
    keyPoints: [
      "match/case pattern matching for expressive structural deconstruction.",
      "List, dict, and set comprehensions vs generator expressions for memory optimization.",
      "Using itertools for memory-friendly cartesian products, permutations, and grouping.",
      "Loop-else constructs and clean termination assertions.",
    ],
    codeSnippet: `def parse_action(command: dict):
    match command:
        case {"type": "start", "port": int(p)} if p > 1024:
            return f"Starting server on safe port {p}"
        case {"type": "stop"}:
            return "Gracefully halting service"
        case _:
            raise ValueError("Unknown command structure")`,
    takeaways: "Leverage expressive pattern matching to reduce nested conditional boilerplate.",
  },
  {
    page: 5,
    title: "5. First-Class Functions, Closures & Decorators",
    subtitle: "Higher-Order Functions, Lexical Closures & Metadata Preservation",
    keyPoints: [
      "Functions as first-class citizens: passing functions as arguments and return values.",
      "Lexical closures retaining reference state from enclosing lexical scopes.",
      "Writing reusable decorators with functools.wraps for caching, telemetry, and validation.",
      "Parameterized decorators requiring a three-tiered nested function hierarchy.",
    ],
    codeSnippet: `from functools import wraps
import time

def timing_decorator(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        t0 = time.perf_counter()
        res = func(*args, **kwargs)
        duration = time.perf_counter() - t0
        print(f"[Telemetry] {func.__name__} completed in {duration:.4f}s")
        return res
    return wrapper`,
    takeaways: "Decorators provide clean cross-cutting separation of concerns.",
  },
  {
    page: 6,
    title: "6. Object-Oriented System Design & Protocols",
    subtitle: "Dunder Methods, Abstract Base Classes & Composition over Inheritance",
    keyPoints: [
      "Special double-underscore methods (__repr__, __eq__, __hash__, __enter__, __exit__).",
      "Using abc.ABC and @abstractmethod to enforce strict interface compliance.",
      "Python 3.8+ typing.Protocol for structural subtyping (duck-typing with static guarantees).",
      "Avoiding deep inheritance trees by composing specialized component services.",
    ],
    codeSnippet: `from typing import Protocol

class Serializable(Protocol):
    def to_json(self) -> str:
        ...

class UserProfile:
    def __init__(self, username: str):
        self.username = username
    
    def to_json(self) -> str:
        return f'{{"username": "{self.username}"}}'`,
    takeaways: "Prefer Protocols and Composition for robust enterprise decoupling.",
  },
  {
    page: 7,
    title: "7. Defensive Error Handling & Context Managers",
    subtitle: "Custom Exceptions, Contextual Chains & Resource Safeguards",
    keyPoints: [
      "Exception hierarchy branching: ValueError, KeyError, RuntimeError vs custom business errors.",
      "Exception chaining with 'raise ... from err' preserving underlying stack trace context.",
      "Guaranteed resource cleanup using context managers (with statement).",
      "Writing custom context managers using contextlib.contextmanager generator syntax.",
    ],
    codeSnippet: `class DatabaseSession:
    def __enter__(self):
        self.connection = "OPEN_TRANSACTION"
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            print("Rollback due to exception:", exc_val)
        else:
            print("Commit transaction successfully")
        return False # Propagate exception if present`,
    takeaways: "Always protect system resources with deterministic context managers.",
  },
  {
    page: 8,
    title: "8. Concurrency: AsyncIO, Threading & Multiprocessing",
    subtitle: "Event Loops, Coroutines, Non-Blocking I/O vs CPU-Bound Worker Pools",
    keyPoints: [
      "AsyncIO event loop for high-throughput cooperative non-blocking I/O.",
      "The difference between async def coroutines, Tasks, and Futures.",
      "Multiprocessing.Pool for CPU-heavy mathematical and algorithmic parallel tasks.",
      "Thread pools for legacy blocking network libraries without native asyncio support.",
    ],
    codeSnippet: `import asyncio

async def fetch_telemetry(sensor_id: int):
    await asyncio.sleep(0.1) # Simulate non-blocking network I/O
    return {"id": sensor_id, "status": "active"}

async def main():
    tasks = [fetch_telemetry(i) for i in range(5)]
    results = await asyncio.gather(*tasks)
    print(f"Aggregated {len(results)} sensors")`,
    takeaways: "Use asyncio for I/O bound concurrency and multiprocessing for CPU compute.",
  },
  {
    page: 9,
    title: "9. Modules, Packages & Virtual Environments",
    subtitle: "PyProject.toml, Wheels, Namespace Packages & Isolated Toolchains",
    keyPoints: [
      "Standard packaging workflows using modern pyproject.toml specifications.",
      "Understanding sys.path evaluation and module import caching in sys.modules.",
      "Virtual environment isolation: ensuring zero host pollution with UV and venv.",
      "Semantic versioning rules (SemVer: Major.Minor.Patch) for enterprise libraries.",
    ],
    codeSnippet: `[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "examlms-core"
version = "2.1.0"
dependencies = [
    "pydantic>=2.0.0",
    "sqlalchemy>=2.0.0"
]`,
    takeaways: "Maintain strict isolation and reproducibility across all runtime environments.",
  },
  {
    page: 10,
    title: "10. File I/O, Serialization & Stream Buffers",
    subtitle: "Chunked Binary Streaming, JSON Schemas & Memory-Mapped Files",
    keyPoints: [
      "Using chunked buffer reading (e.g. iter(lambda: f.read(8192), b'')) for large files.",
      "JSON, CSV, and Parquet serialization performance profiles.",
      "High-speed serialization with orjson vs standard library json module.",
      "Safe atomic file writing patterns with temporary files to avoid corruption.",
    ],
    codeSnippet: `from pathlib import Path
import json

data_path = Path("telemetry.json")
content = {"status": "ok", "items": [1, 2, 3]}

# Atomic write pattern
temp_path = data_path.with_suffix(".tmp")
with temp_path.open("w", encoding="utf-8") as f:
    json.dump(content, f, indent=2)
temp_path.replace(data_path)`,
    takeaways: "Protect data files against partial writes using atomic rename replacement.",
  },
  {
    page: 11,
    title: "11. Type Annotations & Static Quality Verification",
    subtitle: "Mypy, Generic Types, TypeVar, Literal & Runtime Pydantic Models",
    keyPoints: [
      "Gradual typing benefits: early bug detection and self-documenting codebases.",
      "Generic types and TypeVar for type-safe reusable collections and utilities.",
      "Union types and Optional representations (PEP 604: X | None).",
      "Pydantic V2 validation engines for automated schema coercion and serialization.",
    ],
    codeSnippet: `from typing import Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")

class APIResponse(BaseModel, Generic[T]):
    success: bool
    data: T
    timestamp: float = Field(default_factory=time.time)`,
    takeaways: "Enforce static typing for enterprise maintainability and bug prevention.",
  },
  {
    page: 12,
    title: "12. Testing Strategies: Pytest, Fixtures & Mocking",
    subtitle: "Unit, Integration & Regression Testing with Deterministic Harnesses",
    keyPoints: [
      "Structuring tests with pytest fixtures and parameterization (@pytest.mark.parametrize).",
      "Deterministic database transaction rollbacks in integration test suites.",
      "Mocking third-party HTTP and RPC calls using unittest.mock and respx.",
      "Measuring code coverage and establishing regression gates in CI pipelines.",
    ],
    codeSnippet: `import pytest

@pytest.mark.parametrize("input_val, expected", [
    (10, 20),
    (0, 0),
    (-5, -10)
])
def test_double_scalar(input_val, expected):
    assert input_val * 2 == expected`,
    takeaways: "Build reliable automated verification suites to guarantee regression resistance.",
  },
  {
    page: 13,
    title: "13. Clean Architecture & Enterprise Design Patterns",
    subtitle: "Dependency Injection, Repository Pattern & Service Boundaries",
    keyPoints: [
      "Decoupling business logic from database models via the Repository Pattern.",
      "Dependency Injection enabling rapid unit testing with mocked interfaces.",
      "Single Responsibility and Open-Closed principles in application service layers.",
      "CQRS (Command Query Responsibility Segregation) for high-scale learning systems.",
    ],
    codeSnippet: `class UserRepositoryProtocol(Protocol):
    def get_by_id(self, user_id: str) -> dict | None: ...

class UserService:
    def __init__(self, repo: UserRepositoryProtocol):
        self.repo = repo
    
    def authenticate(self, user_id: str) -> bool:
        return self.repo.get_by_id(user_id) is not None`,
    takeaways: "Keep core business rules independent of transport frameworks and databases.",
  },
  {
    page: 14,
    title: "14. Performance Profiling & Optimization Tactics",
    subtitle: "cProfile, Memory Profilers, Slots & Vectorized Computation",
    keyPoints: [
      "Profiling bottlenecks using cProfile, py-spy, and flamegraphs.",
      "Reducing memory footprint using __slots__ in data-heavy class hierarchies.",
      "Avoiding string concatenation in loops using join() and memoryview.",
      "Leveraging Cython, PyPy, or Rust extensions (PyO3) for critical hotspots.",
    ],
    codeSnippet: `class OptimizedRecord:
    __slots__ = ("id", "score", "timestamp")
    def __init__(self, id: int, score: float, timestamp: float):
        self.id = id
        self.score = score
        self.timestamp = timestamp`,
    takeaways: "Profile first before optimizing; address algorithmic complexity before micro-tweaks.",
  },
  {
    page: 15,
    title: "15. Security Hardening & Input Sanitization",
    subtitle: "OWASP Prevention, SQL Injection Defense, Secrets & Timing Attacks",
    keyPoints: [
      "Parameterized SQL queries via ORMs to eliminate SQL injection vectors.",
      "Constant-time comparison (hmac.compare_digest) to prevent timing side-channel attacks.",
      "Environment variable secret management without hardcoding keys in source repositories.",
      "CSRF, CORS, and rate-limiting enforcement on public API endpoints.",
    ],
    codeSnippet: `import hmac

def verify_token(provided: str, secret: str) -> bool:
    # Constant-time comparison immune to timing analysis
    return hmac.compare_digest(provided.encode(), secret.encode())`,
    takeaways: "Always validate untrusted student input and never trust unauthenticated payloads.",
  },
  {
    page: 16,
    title: "16. RESTful APIs, Microservices & Event Streams",
    subtitle: "FastAPI, OpenAPI Specifications, Webhooks & Asynchronous Outbox",
    keyPoints: [
      "Building high-performance async REST services with FastAPI and Pydantic.",
      "Transactional Outbox pattern for guaranteed cross-microservice event delivery.",
      "Idempotency keys on state-mutating endpoints to prevent duplicate payments or actions.",
      "Distributed tracing with OpenTelemetry across distributed system topologies.",
    ],
    codeSnippet: `from fastapi import FastAPI, Depends, Header

app = FastAPI(title="ExamLMS Assessment Service")

@app.post("/api/v1/assessments/submit")
async def submit_assessment(
    idempotency_key: str = Header(...),
    payload: dict = {}
):
    return {"status": "accepted", "idempotency_key": idempotency_key}`,
    takeaways: "Design distributed services with failure resilience and idempotency built-in.",
  },
  {
    page: 17,
    title: "17. Hands-on Laboratory Exercise & Checklist",
    subtitle: "Interactive Coding Task, Real-Time Test Verification & Rubric",
    keyPoints: [
      "Task 1: Implement an asynchronous telemetry ingestion pipeline with batch flush.",
      "Task 2: Define a Pydantic schema with custom field validators.",
      "Task 3: Wrap the repository with a context manager ensuring transaction rollback on error.",
      "Verification: All unit tests must pass with 100% green status before advancing.",
    ],
    codeSnippet: `# Laboratory Submission Checklist:
# [x] Async batching pipeline configured
# [x] Validation constraints satisfied
# [x] Context manager rollback verified
# [x] Test suite passing with 0 errors`,
    takeaways: "Hands-on implementation solidifies theoretical concepts and coding fluency.",
  },
  {
    page: 18,
    title: "18. Summary, Recommended Readings & Assessment Review",
    subtitle: "Key Takeaways, Official Documentation Links & Chapter Test Prep",
    keyPoints: [
      "Review all 17 preceding foundational topics and architectural principles.",
      "Prepare for the Chapter Assessment: 70% passing threshold required.",
      "Review official Python 3.12+ documentation and standard library release notes.",
      "Proceed to the Chapter Test when you are ready to test your knowledge.",
    ],
    codeSnippet: `print("=========================================")
print("Congratulations! All 18 slides completed.")
print("Proceed to Chapter Test with confidence.")
print("=========================================")`,
    takeaways: "You have reviewed the complete chapter lecture slides. Ready for the assessment!",
  },
];

export function InAppPdfViewer({
  isOpen,
  onClose,
  documentTitle,
  pdfUrl,
  mediaId,
  totalSlides = 18,
  chapterTitle,
  courseTitle,
  moduleTitle,
}: InAppPdfViewerProps) {
  // Navigation & Zoom State
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [pageInput, setPageInput] = useState<string>("1");
  const [zoom, setZoom] = useState<number>(100);
  const [orientation, setOrientation] = useState<"portrait" | "landscape">("landscape");
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [hasError, setHasError] = useState<boolean>(false);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);
  const scrollAreaRef = useRef<HTMLDivElement>(null);

  // Sync page input
  useEffect(() => {
    setPageInput(String(currentPage));
  }, [currentPage]);

  // Authenticated media stream fetch when mediaId is provided
  useEffect(() => {
    if (!isOpen) {
      if (blobUrl) {
        URL.revokeObjectURL(blobUrl);
        setBlobUrl(null);
      }
      return;
    }

    if (mediaId) {
      setIsLoading(true);
      setHasError(false);
      const token =
        localStorage.getItem("token") ||
        localStorage.getItem("access_token") ||
        sessionStorage.getItem("token");
      const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};
      const streamUrl = `${env.apiBaseUrl}/media/stream/${mediaId}`;

      fetch(streamUrl, { method: "GET", headers })
        .then(async (res) => {
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          const blob = await res.blob();
          const pdfBlob =
            blob.type === "application/pdf"
              ? blob
              : new Blob([blob], { type: "application/pdf" });
          const url = URL.createObjectURL(pdfBlob);
          setBlobUrl(url);
          setIsLoading(false);
        })
        .catch((err) => {
          console.warn("Failed to load PDF media stream, falling back to slides", err);
          setIsLoading(false);
        });
    } else {
      setBlobUrl(null);
      setIsLoading(false);
    }
  }, [isOpen, mediaId]);

  const effectivePdfUrl = blobUrl || pdfUrl;

  // Handle keyboard navigation
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (isFullscreen) {
          if (document.fullscreenElement) {
            document.exitFullscreen().catch(() => {});
          }
          setIsFullscreen(false);
        } else {
          onClose();
        }
      } else if (e.key === "ArrowRight" || e.key === "PageDown") {
        e.preventDefault();
        setCurrentPage((prev) => Math.min(totalSlides, prev + 1));
      } else if (e.key === "ArrowLeft" || e.key === "PageUp") {
        e.preventDefault();
        setCurrentPage((prev) => Math.max(1, prev - 1));
      } else if (e.key === "+" || e.key === "=") {
        setZoom((prev) => Math.min(200, prev + 15));
      } else if (e.key === "-") {
        setZoom((prev) => Math.max(60, prev - 15));
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, isFullscreen, totalSlides, onClose]);

  // Navigation handlers
  const handlePrevPage = () => {
    setCurrentPage((p) => Math.max(1, p - 1));
    scrollAreaRef.current?.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleNextPage = () => {
    setCurrentPage((p) => Math.min(totalSlides, p + 1));
    scrollAreaRef.current?.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handlePageInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setPageInput(e.target.value);
  };

  const handlePageInputBlurOrSubmit = () => {
    const parsed = parseInt(pageInput, 10);
    if (!isNaN(parsed) && parsed >= 1 && parsed <= totalSlides) {
      setCurrentPage(parsed);
      scrollAreaRef.current?.scrollTo({ top: 0, behavior: "smooth" });
    } else {
      setPageInput(String(currentPage));
    }
  };

  // Zoom handlers
  const handleZoomIn = () => setZoom((prev) => Math.min(200, prev + 15));
  const handleZoomOut = () => setZoom((prev) => Math.max(60, prev - 15));
  const handleFitWidth = () => {
    setZoom(100);
    setOrientation("landscape");
  };

  // Toggle Fullscreen
  const handleToggleFullscreen = () => {
    if (!containerRef.current) return;
    if (!document.fullscreenElement) {
      containerRef.current
        .requestFullscreen()
        .then(() => setIsFullscreen(true))
        .catch(() => setIsFullscreen(true));
    } else {
      document
        .exitFullscreen()
        .then(() => setIsFullscreen(false))
        .catch(() => setIsFullscreen(false));
    }
  };

  // Listen to fullscreenchange
  useEffect(() => {
    const handleFsChange = () => {
      setIsFullscreen(Boolean(document.fullscreenElement));
    };
    document.addEventListener("fullscreenchange", handleFsChange);
    return () => document.removeEventListener("fullscreenchange", handleFsChange);
  }, []);

  if (!isOpen) return null;

  const currentSlide: SlideContent = DEFAULT_SLIDES[(currentPage - 1) % DEFAULT_SLIDES.length] ?? DEFAULT_SLIDES[0]!;

  return (
    <div
      ref={containerRef}
      className={cn(
        "fixed inset-0 z-50 flex flex-col bg-slate-900 text-slate-100 antialiased select-none",
        isFullscreen ? "h-screen w-screen" : "h-full w-full"
      )}
    >
      {/* TOP TOOLBAR */}
      <header className="h-14 border-b border-slate-800 bg-slate-950 px-4 flex items-center justify-between gap-2 shrink-0 z-10 shadow-md">
        {/* Left: Back to Course & Title */}
        <div className="flex items-center gap-3 min-w-0">
          <button
            type="button"
            onClick={onClose}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold transition-colors cursor-pointer border border-slate-700 shrink-0"
            title="Return to Course Learning Room"
          >
            <ArrowLeft size={15} />
            <span className="hidden sm:inline">Back to Course</span>
          </button>

          <div className="h-5 w-px bg-slate-800 hidden sm:block shrink-0" />

          <div className="flex items-center gap-2 min-w-0">
            <div className="w-7 h-7 rounded-lg bg-blue-600/20 text-blue-400 border border-blue-500/30 flex items-center justify-center shrink-0">
              <FileText size={16} />
            </div>
            <div className="min-w-0">
              <h2 className="text-xs font-bold text-white truncate max-w-[160px] sm:max-w-xs md:max-w-md">
                {documentTitle || "Course Reference Slides.pdf"}
              </h2>
              <span className="text-[10px] text-slate-400 hidden md:block truncate">
                {chapterTitle || courseTitle || "Interactive Lecture Material"} · {totalSlides} Pages
              </span>
            </div>
          </div>
        </div>

        {/* Center: Page Navigation (Page X of Y) */}
        <div className="flex items-center gap-1.5 bg-slate-900/90 border border-slate-800 px-2 py-1 rounded-lg">
          <button
            type="button"
            disabled={currentPage <= 1}
            onClick={handlePrevPage}
            className="p-1 rounded text-slate-300 hover:text-white hover:bg-slate-800 disabled:opacity-40 disabled:hover:bg-transparent cursor-pointer transition-colors"
            title="Previous Page (Left Arrow)"
          >
            <ChevronLeft size={16} />
          </button>

          <div className="flex items-center gap-1 text-xs text-slate-300 font-mono">
            <span>Page</span>
            <input
              type="text"
              value={pageInput}
              onChange={handlePageInputChange}
              onBlur={handlePageInputBlurOrSubmit}
              onKeyDown={(e) => e.key === "Enter" && handlePageInputBlurOrSubmit()}
              className="w-8 text-center bg-slate-800 border border-slate-700 rounded text-xs font-bold text-white focus:outline-none focus:border-blue-500 px-0.5 py-0.5"
            />
            <span className="text-slate-400">/ {totalSlides}</span>
          </div>

          <button
            type="button"
            disabled={currentPage >= totalSlides}
            onClick={handleNextPage}
            className="p-1 rounded text-slate-300 hover:text-white hover:bg-slate-800 disabled:opacity-40 disabled:hover:bg-transparent cursor-pointer transition-colors"
            title="Next Page (Right Arrow)"
          >
            <ChevronRight size={16} />
          </button>
        </div>

        {/* Right: Zoom, Orientation, Fullscreen & Close */}
        <div className="flex items-center gap-1.5">
          {/* Zoom Controls */}
          <div className="hidden sm:flex items-center gap-1 bg-slate-900/90 border border-slate-800 px-1.5 py-0.5 rounded-lg text-xs">
            <button
              type="button"
              disabled={zoom <= 60}
              onClick={handleZoomOut}
              className="p-1 text-slate-300 hover:text-white disabled:opacity-40 cursor-pointer"
              title="Zoom Out (-)"
            >
              <ZoomOut size={14} />
            </button>
            <span className="font-mono text-[11px] text-slate-300 w-10 text-center font-bold">{zoom}%</span>
            <button
              type="button"
              disabled={zoom >= 200}
              onClick={handleZoomIn}
              className="p-1 text-slate-300 hover:text-white disabled:opacity-40 cursor-pointer"
              title="Zoom In (+)"
            >
              <ZoomIn size={14} />
            </button>
            <div className="w-px h-3.5 bg-slate-800 mx-0.5" />
            <button
              type="button"
              onClick={handleFitWidth}
              className="px-1.5 py-0.5 text-[11px] font-semibold text-slate-300 hover:text-white cursor-pointer rounded hover:bg-slate-800"
              title="Fit to Width"
            >
              Fit
            </button>
          </div>

          {/* Orientation Toggle */}
          <button
            type="button"
            onClick={() => setOrientation((o) => (o === "landscape" ? "portrait" : "landscape"))}
            className="p-1.5 rounded-lg text-slate-300 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer border border-slate-800 hidden md:flex items-center gap-1 text-[11px]"
            title={`Current: ${orientation}. Click to toggle orientation.`}
          >
            <RotateCw size={14} />
            <span className="capitalize">{orientation}</span>
          </button>

          {/* Fullscreen Toggle */}
          <button
            type="button"
            onClick={handleToggleFullscreen}
            className="p-1.5 rounded-lg text-slate-300 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer border border-slate-800"
            title={isFullscreen ? "Exit Fullscreen" : "Enter Fullscreen"}
          >
            {isFullscreen ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
          </button>

          {/* Close Button */}
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/30 transition-colors cursor-pointer ml-1"
            title="Close Viewer"
          >
            <X size={16} />
          </button>
        </div>
      </header>

      {/* MAIN VIEWPORT */}
      <main
        ref={scrollAreaRef}
        className="flex-1 overflow-auto bg-slate-900/95 p-4 sm:p-8 flex items-center justify-center relative"
      >
        {/* Loading Overlay */}
        {isLoading && (
          <div className="absolute inset-0 bg-slate-900/80 backdrop-blur-xs flex flex-col items-center justify-center z-20 space-y-3">
            <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
            <p className="text-xs text-slate-300 font-semibold tracking-wide">Loading PDF Lecture Slides...</p>
          </div>
        )}

        {/* Error Fallback */}
        {hasError && (
          <div className="max-w-md w-full bg-slate-800 border border-slate-700 rounded-2xl p-6 text-center space-y-4 shadow-xl">
            <div className="w-12 h-12 rounded-full bg-red-500/20 text-red-400 mx-auto flex items-center justify-center">
              <AlertCircle size={24} />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white">Document Display Notice</h3>
              <p className="text-xs text-slate-400 mt-1">
                The embedded PDF preview could not be rendered directly. You can retry loading or open the document externally.
              </p>
            </div>
            <div className="flex items-center justify-center gap-3 pt-2">
              <button
                type="button"
                onClick={() => setHasError(false)}
                className="px-4 py-2 rounded-xl bg-blue-600 text-xs font-bold text-white hover:bg-blue-700 cursor-pointer"
              >
                Retry Loading
              </button>
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 rounded-xl bg-slate-700 text-xs font-bold text-slate-200 hover:bg-slate-600 cursor-pointer"
              >
                Back to Course
              </button>
            </div>
          </div>
        )}

        {/* Embedded Native PDF Viewer if external valid URL or media stream provided */}
        {!hasError && effectivePdfUrl ? (
          <div
            style={{
              transform: `scale(${zoom / 100})`,
              transformOrigin: "center top",
              transition: "transform 0.15s ease-out",
            }}
            className={cn(
              "w-full max-w-5xl bg-white rounded-xl shadow-2xl overflow-hidden border border-slate-700 min-h-[640px]",
              orientation === "landscape" ? "aspect-16/10" : "aspect-1/1.414"
            )}
          >
            <iframe
              src={`${effectivePdfUrl}#toolbar=0&navpanes=0&page=${currentPage}&zoom=${zoom}`}
              title={documentTitle}
              className="w-full h-full border-0 min-h-[640px]"
              onError={() => setHasError(true)}
            />
          </div>
        ) : (
          /* HIGH-FIDELITY LECTURE SLIDE PAGE CANVAS */
          !hasError && (
            <div
              style={{
                transform: `scale(${zoom / 100})`,
                transformOrigin: "center top",
                transition: "transform 0.15s ease-out",
              }}
              className={cn(
                "bg-white text-slate-900 rounded-2xl shadow-2xl overflow-hidden border border-slate-200 flex flex-col justify-between transition-all duration-200",
                orientation === "landscape"
                  ? "w-full max-w-4xl min-h-[540px] aspect-16/10"
                  : "w-full max-w-2xl min-h-[720px] aspect-1/1.414"
              )}
            >
              {/* SLIDE HEADER */}
              <div className="px-8 py-5 border-b border-slate-100 bg-gradient-to-r from-slate-50 via-white to-slate-50 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-blue-600 text-white font-bold text-xs flex items-center justify-center shadow-xs">
                    LMS
                  </div>
                  <div>
                    <span className="text-[10px] font-bold uppercase tracking-wider text-blue-600 block">
                      {courseTitle || "Official Curriculum Reference"}
                    </span>
                    <h3 className="text-xs font-bold text-slate-800">
                      {moduleTitle || "Mastery Modules"} · {chapterTitle || "Lecture Slides"}
                    </h3>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-mono font-bold text-slate-400 bg-slate-100 px-2.5 py-1 rounded-md border border-slate-200">
                    Slide {currentPage} of {totalSlides}
                  </span>
                </div>
              </div>

              {/* SLIDE BODY */}
              <div className="p-8 sm:p-10 flex-1 flex flex-col justify-center space-y-6">
                <div>
                  <h1 className="text-xl sm:text-2xl font-extrabold text-slate-950 tracking-tight">
                    {currentSlide.title}
                  </h1>
                  <p className="text-xs sm:text-sm font-medium text-blue-700 mt-1">{currentSlide.subtitle}</p>
                </div>

                {/* Key Concepts Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-3 bg-slate-50/80 p-5 rounded-xl border border-slate-200/80">
                    <b className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                      <Sparkles size={14} className="text-blue-600" />
                      Core Learning Points
                    </b>
                    <ul className="space-y-2 text-xs text-slate-600 leading-relaxed">
                      {currentSlide.keyPoints.map((pt, idx) => (
                        <li key={idx} className="flex items-start gap-2">
                          <CheckCircle2 size={13} className="text-emerald-600 shrink-0 mt-0.5" />
                          <span>{pt}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  {/* Code snippet or Architecture pipeline */}
                  {currentSlide.codeSnippet ? (
                    <div className="bg-slate-950 text-slate-200 p-4 rounded-xl border border-slate-800 font-mono text-[11px] leading-relaxed overflow-x-auto flex flex-col justify-between">
                      <div className="flex items-center justify-between pb-2 border-b border-slate-800 text-[10px] text-slate-400">
                        <span>Terminal / Source Example</span>
                        <span className="text-blue-400">Python 3.12+</span>
                      </div>
                      <pre className="py-2.5 overflow-x-auto text-emerald-300 font-mono text-[11px]">
                        <code>{currentSlide.codeSnippet}</code>
                      </pre>
                      <div className="text-[10px] text-slate-500 pt-1 border-t border-slate-900">
                        Interactive executable code block
                      </div>
                    </div>
                  ) : (
                    <div className="bg-blue-50/60 border border-blue-200/60 p-5 rounded-xl flex flex-col justify-between">
                      <b className="text-xs font-bold text-blue-900 flex items-center gap-1.5">
                        <Layers size={14} className="text-blue-700" />
                        Key Architectural Concepts
                      </b>
                      <p className="text-xs text-blue-800/90 leading-relaxed">
                        Mastery of this topic prepares students for both the chapter quiz and practical system
                        implementation during lab sessions.
                      </p>
                      <span className="text-[10px] font-semibold text-blue-700">ExamLMS Verified Curriculum</span>
                    </div>
                  )}
                </div>

                {/* Pipeline visualizer if steps exist */}
                {currentSlide.diagramSteps && (
                  <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 flex flex-wrap items-center justify-between gap-2">
                    <span className="text-[11px] font-bold text-slate-700">{currentSlide.diagramTitle}:</span>
                    <div className="flex items-center gap-2 text-xs">
                      {currentSlide.diagramSteps.map((step, idx) => (
                        <React.Fragment key={idx}>
                          <span className="px-2.5 py-1 rounded bg-white border border-slate-300 text-slate-800 font-bold text-[11px] shadow-2xs">
                            {step}
                          </span>
                          {idx < currentSlide.diagramSteps!.length - 1 && (
                            <span className="text-blue-600 font-bold">→</span>
                          )}
                        </React.Fragment>
                      ))}
                    </div>
                  </div>
                )}

                {/* Takeaway footer highlight */}
                <div className="p-3.5 rounded-xl bg-blue-50/50 border border-blue-100 flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-blue-100 text-blue-700 flex items-center justify-center shrink-0">
                    <BookOpen size={16} />
                  </div>
                  <p className="text-xs text-slate-700 font-medium">
                    <b>Key Takeaway:</b> {currentSlide.takeaways}
                  </p>
                </div>
              </div>

              {/* SLIDE FOOTER */}
              <div className="px-8 py-3.5 border-t border-slate-100 bg-slate-50 flex items-center justify-between text-[11px] text-slate-500">
                <span>ExamLMS Interactive Lecture Series</span>
                <span>Confidential & Educational Material · Not for Distribution</span>
                <span className="font-mono font-bold text-slate-700">Page {currentPage} / {totalSlides}</span>
              </div>
            </div>
          )
        )}
      </main>

      {/* BOTTOM ACTION BAR */}
      <footer className="h-12 border-t border-slate-800 bg-slate-950 px-4 flex items-center justify-between text-xs text-slate-400 shrink-0">
        <div className="flex items-center gap-2">
          <span className="inline-block w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-[11px] text-slate-300">In-App Document Reader Active</span>
        </div>

        <div className="flex items-center gap-3">
          <span className="hidden sm:inline text-[11px] text-slate-400">
            Use <kbd className="px-1 py-0.5 bg-slate-800 rounded text-slate-300 font-mono text-[10px]">←</kbd> and{" "}
            <kbd className="px-1 py-0.5 bg-slate-800 rounded text-slate-300 font-mono text-[10px]">→</kbd> to turn pages
          </span>
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1 rounded bg-slate-800 hover:bg-slate-700 text-white font-semibold text-xs cursor-pointer border border-slate-700"
          >
            Return to Course
          </button>
        </div>
      </footer>
    </div>
  );
}

import { Component, type ErrorInfo, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, RefreshCw, ArrowLeft } from "lucide-react";

interface Props {
  children: ReactNode;
  fallbackTitle?: string;
  returnUrl?: string;
  courseId?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class AssessmentErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("[AssessmentErrorBoundary] Caught error:", error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      const returnUrl =
        this.props.returnUrl ||
        (this.props.courseId ? `/courses/${this.props.courseId}/learn` : "/courses/my");
      return (
        <div className="max-w-2xl mx-auto my-12 p-8 bg-white border border-rose-200 rounded-2xl shadow-card text-center space-y-4">
          <div className="w-14 h-14 bg-rose-50 text-rose-600 rounded-2xl flex items-center justify-center mx-auto ring-1 ring-rose-200">
            <AlertTriangle className="w-7 h-7" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-slate-900">
              {this.props.fallbackTitle || "Assessment Could Not Be Rendered"}
            </h2>
            <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto leading-relaxed">
              An unexpected error occurred while loading this assessment component. You can retry or return to your course.
            </p>
            {this.state.error?.message && (
              <p className="text-[11px] font-mono text-rose-700 bg-rose-50 p-2.5 rounded-xl border border-rose-200 mt-3 max-w-md mx-auto overflow-x-auto text-left">
                {this.state.error.message}
              </p>
            )}
          </div>
          <div className="pt-2 flex items-center justify-center gap-3">
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl border border-slate-300 text-xs font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer shadow-2xs transition-colors"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Reload Page
            </button>
            <Link
              to={returnUrl}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#00663C] text-xs font-bold text-white hover:bg-[#00522F] cursor-pointer shadow-xs transition-colors"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              Back to Course
            </Link>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

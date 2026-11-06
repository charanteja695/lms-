import { Component, ErrorInfo, ReactNode } from "react";
import { Icon, Button } from "@/shared/ui";

interface Props {
  children: ReactNode;
  onReset?: () => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
  copied: boolean;
  showDetails: boolean;
}

export class JobFormErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
    errorInfo: null,
    copied: false,
    showDetails: false,
  };

  public static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("[JobFormErrorBoundary] Uncaught job form error:", error, errorInfo);
    this.setState({ errorInfo });
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
    if (this.props.onReset) {
      this.props.onReset();
    }
  };

  private copyDetails = () => {
    const { error, errorInfo } = this.state;
    const report = [
      `Job Form Error: ${error?.name || "Error"} - ${error?.message || "Unknown error"}`,
      `Location: ${window.location.href}`,
      `Timestamp: ${new Date().toISOString()}`,
      `User Agent: ${navigator.userAgent}`,
      `Stack Trace:`,
      error?.stack || "No stack trace available",
      `Component Stack:`,
      errorInfo?.componentStack || "No component stack available",
    ].join("\n\n");

    navigator.clipboard.writeText(report).then(() => {
      this.setState({ copied: true });
      setTimeout(() => this.setState({ copied: false }), 2000);
    });
  };

  public render() {
    if (this.state.hasError) {
      const { error, errorInfo, copied, showDetails } = this.state;
      return (
        <div className="min-h-[500px] flex items-center justify-center p-6 bg-slate-50">
          <div className="w-full max-w-lg rounded-2xl border border-rose-200 bg-white p-6 shadow-sm space-y-4">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-xl bg-rose-50 text-rose-600 flex items-center justify-center border border-rose-100">
                <Icon name="alert-triangle" className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-900">Job Form Encountered an Error</h3>
                <p className="text-xs text-slate-500">
                  We could not render this step properly. Your work has been preserved in draft if saved.
                </p>
              </div>
            </div>

            <div className="p-3 rounded-xl bg-rose-50/70 border border-rose-100 text-xs text-rose-900 font-mono break-words">
              {error?.message || "Unknown rendering exception"}
            </div>

            <div className="flex items-center gap-2 pt-1">
              <Button
                variant="primary"
                size="sm"
                onClick={this.handleReset}
                className="text-xs font-semibold bg-emerald-600 hover:bg-emerald-700"
              >
                Try Again
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => (window.location.href = "/jobs/employer")}
                className="text-xs font-semibold border-slate-300"
              >
                Back to Jobs
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={this.copyDetails}
                className="text-xs font-semibold border-slate-300 ml-auto gap-1"
              >
                <Icon name={copied ? "check" : "copy"} className="h-3.5 w-3.5" />
                {copied ? "Copied" : "Copy details"}
              </Button>
            </div>

            <div className="border-t border-slate-100 pt-2">
              <button
                type="button"
                onClick={() => this.setState({ showDetails: !showDetails })}
                className="text-xs text-slate-500 hover:text-slate-800 font-medium flex items-center gap-1"
              >
                <span>{showDetails ? "Hide" : "Show"} technical details</span>
                <Icon name={showDetails ? "chevron-up" : "chevron-down"} className="h-3 w-3" />
              </button>

              {showDetails && (
                <div className="mt-2 p-3 rounded-lg bg-slate-900 text-slate-200 text-[11px] font-mono overflow-auto max-h-56 space-y-2">
                  <div>
                    <span className="text-slate-400">Error:</span> {error?.name}: {error?.message}
                  </div>
                  {error?.stack && (
                    <div>
                      <span className="text-slate-400">Stack:</span>
                      <pre className="whitespace-pre-wrap">{error.stack}</pre>
                    </div>
                  )}
                  {errorInfo?.componentStack && (
                    <div>
                      <span className="text-slate-400">Component Stack:</span>
                      <pre className="whitespace-pre-wrap">{errorInfo.componentStack}</pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

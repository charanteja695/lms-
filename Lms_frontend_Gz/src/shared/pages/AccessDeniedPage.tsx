import { useNavigate } from "react-router-dom";
import { Button, Icon } from "@/shared/ui";
import { usePermissions } from "@/modules/user-management/common/permissions/usePermissions";

export function AccessDeniedPage({
  title = "Access Denied (HTTP 403)",
  message = "You do not have permission to access this page or resource.",
}: {
  title?: string;
  message?: string;
}) {
  const navigate = useNavigate();
  const { permissions } = usePermissions();
  const isStudent = permissions.role === "student";
  const homePath = isStudent ? "/courses/my" : "/";

  const roleLabel = permissions.role
    ? permissions.role.replace("_", " ").toUpperCase()
    : "UNKNOWN";

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center px-4 py-12 text-center" data-testid="access-denied-page">
      <div className="relative mb-6">
        <div className="absolute inset-0 -m-3 rounded-full bg-red-100/60" aria-hidden="true" />
        <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl bg-white text-red-600 shadow-md ring-1 ring-red-200">
          <Icon name="shield" size={32} />
        </div>
      </div>

      <div className="inline-flex items-center gap-1.5 rounded-full bg-red-50 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-red-700 ring-1 ring-red-200/80 mb-3">
        <span>Current Role: {roleLabel}</span>
      </div>

      <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
        {title}
      </h1>

      <p className="mt-2 max-w-md text-sm text-slate-600 leading-relaxed">
        {message}
      </p>

      <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
        <Button
          variant="secondary"
          onClick={() => window.history.back()}
          className="px-4 py-2 text-sm font-medium"
        >
          ← Go Back
        </Button>
        <Button
          variant="primary"
          onClick={() => navigate(homePath, { replace: true })}
          className="px-5 py-2 text-sm font-medium bg-brand-600 hover:bg-brand-700 text-white"
        >
          {isStudent ? "Return to My Courses" : "Return to Dashboard"}
        </Button>
      </div>
    </div>
  );
}

import { Link } from "react-router-dom";

import type { ImportResult } from "@/modules/user-management/users/types";
import { Alert, Button, Card, DataTable } from "@/shared/ui";

export function ImportReport({ result, message, onViewUsers }: { result: ImportResult; message: string | null; onViewUsers: () => void }) {
  const tone = result.errors.length === 0 ? "success" : result.created > 0 || result.valid_rows > 0 ? "warning" : "error";
  return (
    <Card title={result.dry_run ? "Check result" : "Import result"} className="mt-6" actions={!result.dry_run && result.created > 0 && <Button variant="secondary" onClick={onViewUsers}>View users</Button>}>
      <div className="space-y-4">
        {message && <Alert tone={tone}>{message}</Alert>}
        <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {[
            ["Rows", result.total_rows],
            ["Valid", result.valid_rows],
            ["Invalid", result.invalid_rows],
            ["Created", result.created],
          ].map(([label, value]) => (
            <div key={label} className="rounded-lg bg-slate-50 p-3">
              <dt className="text-xs uppercase tracking-wide text-slate-500">{label}</dt>
              <dd className="text-2xl font-semibold text-slate-900">{value}</dd>
            </div>
          ))}
        </dl>
        {result.errors.length > 0 && (
          <div className="overflow-hidden rounded-lg border border-slate-200">
            <DataTable
              columns={[
                { key: "row", header: "Row", className: "w-16", render: (error) => error.row },
                { key: "column", header: "Column", render: (error) => error.column ?? "—" },
                { key: "message", header: "Problem", render: (error) => error.message },
              ]}
              rows={result.errors}
              rowKey={(error) => `${error.row}-${error.column}-${error.code}`}
            />
          </div>
        )}
        {result.created_users.some((user) => user.temporary_password) && (
          <div className="overflow-hidden rounded-lg border border-amber-200 bg-amber-50 p-4">
            <p className="text-sm font-medium text-amber-900">Temporary passwords (shown only once)</p>
            <p className="mb-3 text-xs text-amber-800">These people have no email address. Share their sign-in details securely.</p>
            <ul className="space-y-1 font-mono text-sm text-amber-900">
              {result.created_users
                .filter((user) => user.temporary_password)
                .map((user) => (
                  <li key={user.user_id}>
                    {user.username} · {user.temporary_password}
                  </li>
                ))}
            </ul>
          </div>
        )}
        {result.created_users.length > 0 && (
          <p className="text-sm text-slate-600">
            Created: {result.created_users.slice(0, 5).map((user, index) => (
              <span key={user.user_id}>
                {index > 0 && ", "}
                <Link className="text-brand-700 hover:underline" to={`/users/${user.user_id}`}>{user.username}</Link>
              </span>
            ))}
            {result.created_users.length > 5 && ` and ${result.created_users.length - 5} more`}
          </p>
        )}
      </div>
    </Card>
  );
}

import { useConfirmAction } from "@/core/hooks/useConfirmAction";
import { useNotify } from "@/core/hooks/useNotify";
import { describeDevice, formatDateTime, formatRelative } from "@/core/lib/format";
import { useEndSessionMutation, useListSessionsQuery } from "@/modules/user-management/auth/api/authApi";
import { useSignOut } from "@/modules/user-management/auth/hooks/useAuth";
import { Badge, Button, Card, ConfirmDialog, Icon, PageLoader } from "@/shared/ui";

export function SessionsCard() {
  const { data: sessions, isLoading } = useListSessionsQuery();
  const [endSession] = useEndSessionMutation();
  const { signOut } = useSignOut();
  const notify = useNotify();
  const confirm = useConfirmAction();

  return (
    <Card
      title="Signed-in devices"
      description="Sign out devices you don't recognise."
      actions={
        <Button
          variant="secondary"
          size="sm"
          onClick={() =>
            confirm.ask(
              { title: "Sign out everywhere?", description: "You will be signed out on all devices, including this one.", confirmLabel: "Sign out everywhere" },
              () => signOut(true),
            )
          }
        >
          Sign out everywhere
        </Button>
      }
      bodyClassName="p-0"
    >
      {isLoading ? (
        <PageLoader />
      ) : (
        <ul className="divide-y divide-slate-100">
          {sessions?.map((session) => (
            <li key={session.session_id} className="flex flex-wrap items-center gap-4 px-5 py-4">
              <div className="rounded-lg bg-slate-100 p-2 text-slate-500">
                <Icon name={/Android|iPhone|iPad/.test(session.user_agent ?? "") ? "smartphone" : "monitor"} />
              </div>
              <div className="mr-auto min-w-0">
                <p className="flex items-center gap-2 text-sm font-medium text-slate-900">
                  {describeDevice(session.user_agent)}
                  {session.is_current && <Badge tone="green">This device</Badge>}
                </p>
                <p className="text-xs text-slate-500">
                  {session.ip_address ?? "Unknown IP"} · Active {formatRelative(session.last_active_time)} · Signed in {formatDateTime(session.created_time)}
                </p>
              </div>
              {!session.is_current && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() =>
                    confirm.ask(
                      { title: "Sign out this device?", description: describeDevice(session.user_agent), confirmLabel: "Sign out" },
                      async () => {
                        try {
                          await endSession(session.session_id).unwrap();
                          notify.success("Device signed out");
                        } catch (error) {
                          notify.apiError(error);
                        }
                      },
                    )
                  }
                >
                  Sign out
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
      <ConfirmDialog {...confirm.dialogProps} />
    </Card>
  );
}

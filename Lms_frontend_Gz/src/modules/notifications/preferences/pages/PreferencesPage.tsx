import { useNotify } from "@/core/hooks/useNotify";
import { NotificationsTabs } from "@/modules/notifications/common/components/NotificationsTabs";
import { useGetPreferencesQuery, useUpdatePreferencesMutation } from "@/modules/notifications/preferences/api/preferencesApi";
import { Card, Checkbox, PageHeader, PageLoader } from "@/shared/ui";

/** Each toggle saves straight away; a category the server marks not editable is always emailed. */
export function PreferencesPage() {
  const notify = useNotify();
  const { data: prefs = [], isLoading } = useGetPreferencesQuery();
  const [update, { isLoading: saving }] = useUpdatePreferencesMutation();

  if (isLoading) return <PageLoader />;

  return (
    <>
      <PageHeader title="Notifications" description="Everything appears in your inbox here. Choose what is also emailed to you." />
      <NotificationsTabs />
      <Card>
        <ul className="divide-y divide-slate-100">
          {prefs.map((p) => (
            <li key={p.category} className="py-3 first:pt-0 last:pb-0">
              <Checkbox
                label={p.label}
                description={p.email_editable ? undefined : "Always emailed — these are important account notices."}
                checked={p.email_enabled}
                disabled={!p.email_editable || saving}
                onChange={(e) => void update([{ category: p.category, email_enabled: e.target.checked }]).unwrap().then(() => notify.success("Preferences saved"), notify.apiError)}
              />
            </li>
          ))}
        </ul>
      </Card>
    </>
  );
}

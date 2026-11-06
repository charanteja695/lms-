import { useInstitutionName } from "@/modules/user-management/common/hooks/useInstitutionName";

/**
 * A proper component (not an inline render callback) so the id->name lookup can call hooks
 * safely per table row. Plain text, not a link: not every viewer here (e.g. a subscriptions or
 * learning admin) has the "institutions" section to open the institution's own page.
 */
export function InstitutionNameCell({ organizationId }: { organizationId: string }) {
  const { name, isFetching } = useInstitutionName(organizationId);
  if (isFetching && !name) return <span className="text-slate-400">Loading…</span>;
  return <span className="text-slate-900">{name ?? organizationId}</span>;
}

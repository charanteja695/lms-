import { useGetDirectoryEntryQuery } from "@/modules/user-management/common/api/directoryApi";

/** Any organisation's name for platform staff, through the names-only directory. */
export function OrganizationNameCell({ organizationId }: { organizationId: string }) {
  const { data, isFetching } = useGetDirectoryEntryQuery(organizationId, { skip: !organizationId });
  if (isFetching && !data) return <span className="text-slate-400">Loading…</span>;
  return <span className="text-slate-900">{data?.name ?? organizationId}</span>;
}

import { useUserName } from "@/modules/user-management/common/hooks/useUserName";

/** See InstitutionNameCell.tsx for why this is a real component and plain text, not a link. */
export function UserNameCell({ userId }: { userId: string }) {
  const { name, isFetching } = useUserName(userId);
  if (isFetching && !name) return <span className="text-slate-400">Loading…</span>;
  return <span className="text-slate-900">{name ?? userId}</span>;
}

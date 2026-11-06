import { useUserName } from "@/modules/user-management/common/hooks/useUserName";

export function RequesterNameCell({ userId }: { userId: string }) {
  const { name, isFetching } = useUserName(userId);
  if (isFetching && !name) return <span className="text-slate-400">Loading…</span>;
  return <span className="text-slate-900 font-medium">{name ?? `User ${userId}`}</span>;
}

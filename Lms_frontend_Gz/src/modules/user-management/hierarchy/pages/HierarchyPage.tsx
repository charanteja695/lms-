import { useGetHierarchyQuery, type InstitutionNode } from "@/modules/user-management/hierarchy/api/hierarchyApi";
import { Count, TreeNode } from "@/modules/user-management/hierarchy/components/TreeNode";
import { Button, EmptyState, PageHeader, PageLoader, StatTile } from "@/shared/ui";

const plural = (n: number, word: string) => `${n.toLocaleString()} ${word}${n === 1 ? "" : "s"}`;

function Institution({ node }: { node: InstitutionNode }) {
  const counts = (
    <span className="hidden flex-wrap gap-1.5 sm:flex">
      <Count value={node.staff} label="staff" />
      <Count value={node.students} label={node.students === 1 ? "student" : "students"} />
    </span>
  );
  const detail = [node.code, node.city, node.departments ? `${node.departments} department${node.departments === 1 ? "" : "s"}` : null, node.status !== "active" ? node.status : null]
    .filter(Boolean)
    .join(" · ");
  return (
    <TreeNode icon="building" tone="soft" role="Institute" title={node.name} detail={detail} to={`/institutions/${node.organization_id}`} extra={counts}>
      {node.heads.length === 0 ? (
        <li className="rounded-xl border border-dashed border-accent-200 bg-accent-50/40 px-4 py-2.5 text-sm text-accent-700">No institute head yet. Add one from the institute.</li>
      ) : (
        node.heads.map((head) => (
          <TreeNode key={head.user_id} icon="user" tone="brand" role="Institute head" title={head.full_name} to={`/users/${head.user_id}`}>
            <TreeNode
              icon="users"
              tone="accent"
              role="Staff and students"
              title={`${node.staff.toLocaleString()} staff · ${plural(node.students, "student")}`}
              to={`/users?organization_id=${node.organization_id}&organization_label=${encodeURIComponent(node.name)}`}
            />
          </TreeNode>
        ))
      )}
    </TreeNode>
  );
}

/** Who sits under whom: super admin -> admins -> institutes -> head -> staff and students. */
export function HierarchyPage() {
  const { data, isLoading, isError, refetch } = useGetHierarchyQuery();
  if (isLoading) return <PageLoader />;
  if (isError || !data) {
    return <EmptyState icon="alert" title="Could not load the organisation" action={<Button variant="secondary" onClick={() => void refetch()}>Try again</Button>} />;
  }

  const branches = data.admins.map((branch) =>
    branch.admin ? (
      <TreeNode
        key={branch.admin.user_id}
        icon="shield"
        tone="navy"
        role="Admin"
        title={branch.admin.full_name}
        detail={`${branch.institutions.length} institute${branch.institutions.length === 1 ? "" : "s"}`}
        to={`/admins/${branch.admin.user_id}`}
      >
        {branch.institutions.length === 0 ? (
          <li className="rounded-xl border border-dashed border-slate-200 px-4 py-2.5 text-sm text-slate-500">No institutes assigned yet.</li>
        ) : (
          branch.institutions.map((node) => <Institution key={node.organization_id} node={node} />)
        )}
      </TreeNode>
    ) : (
      branch.institutions.map((node) => <Institution key={node.organization_id} node={node} />)
    ),
  );

  return (
    <>
      <PageHeader title="Organisation" description="Who looks after whom: admins, their institutes, each institute's head, staff and students." />
      <div className="mb-8 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatTile icon="shield" label="Admins" value={data.totals.admins} />
        <StatTile icon="building" label="Institutes" value={data.totals.institutions} />
        <StatTile icon="users" label="Staff" value={data.totals.staff} />
        <StatTile icon="graduation" label="Students" value={data.totals.students} />
      </div>
      <ul className="space-y-4">
        {data.super_admins.length > 0 ? (
          <TreeNode icon="key" tone="navy" role="Super admin" title={data.super_admins.length === 1 ? data.super_admins[0]!.full_name : plural(data.super_admins.length, "super admin")} detail="Runs the platform: courses, tests, jobs, billing and AI">
            {branches}
          </TreeNode>
        ) : (
          branches
        )}
      </ul>
    </>
  );
}

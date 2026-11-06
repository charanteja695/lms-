import type { ItemKind } from "@/modules/career/common/types";
import { ItemKindCard } from "@/modules/career/profile/components/ItemKindCard";
import { ProfileHeaderCard } from "@/modules/career/profile/components/ProfileHeaderCard";
import type { CareerProfile } from "@/modules/career/profile/types";

/** Verified kinds first (what the platform vouches for), then what the student declared. */
const ORDER: ItemKind[] = ["certificate", "skill_score", "course", "education", "experience", "project", "skill", "achievement"];

export function ProfileView({ data, editable }: { data: CareerProfile; editable: boolean }) {
  const byKind = (kind: ItemKind) => data.items.filter((item) => item.kind === kind).sort((a, b) => a.position - b.position);
  return (
    <div className="space-y-4">
      <ProfileHeaderCard key={data.profile.revision} data={data} editable={editable} />
      <div className="grid gap-4 lg:grid-cols-2">
        {ORDER.map((kind) => (
          <ItemKindCard key={kind} kind={kind} items={byKind(kind)} editable={editable} />
        ))}
      </div>
    </div>
  );
}

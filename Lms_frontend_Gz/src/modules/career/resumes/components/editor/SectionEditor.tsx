import { Link } from "react-router-dom";

import { cn } from "@/core/lib/cn";
import { SECTION_TITLES } from "@/modules/career/common/labels";
import { SECTION_KIND } from "@/modules/career/common/types";
import { itemSummary } from "@/modules/career/profile/components/itemSummary";
import type { ProfileItem } from "@/modules/career/profile/types";
import { BulletsEditor } from "@/modules/career/resumes/components/editor/BulletsEditor";
import type { DraftSection } from "@/modules/career/resumes/types";
import { Badge, Button, Checkbox, Icon } from "@/shared/ui";

/** One section row: drag to reorder, a show/hide switch, and (opened) which profile entries it includes and their wording. */
export function SectionEditor({ resumeId, section, profileItems, open, focusItemId, onOpen, onChange, onMove, dragProps }: {
  resumeId: string;
  section: DraftSection;
  profileItems: ProfileItem[];
  open: boolean;
  focusItemId: string | null;
  onOpen: () => void;
  onChange: (section: DraftSection) => void;
  onMove: (delta: number) => void;
  dragProps: React.HTMLAttributes<HTMLDivElement>;
}) {
  const candidates = profileItems.filter((item) => item.kind === SECTION_KIND[section.key] && item.active);
  const included = new Map(section.items.map((ref) => [ref.item_id, ref]));
  const ordered = [...section.items.filter((ref) => candidates.some((c) => c.item_id === ref.item_id)), ...candidates.filter((c) => !included.has(c.item_id)).map((c) => ({ item_id: c.item_id, bullets: null }))];
  const title = section.title || SECTION_TITLES[section.key];
  const toggle = (itemId: string) =>
    onChange({ ...section, items: included.has(itemId) ? section.items.filter((ref) => ref.item_id !== itemId) : [...section.items, { item_id: itemId, bullets: null }] });

  return (
    <div {...dragProps} className={cn("rounded-xl transition-colors", open ? "bg-slate-50 ring-1 ring-brand-200" : "hover:bg-slate-50")}>
      <div className="flex items-center gap-1.5 px-1.5 py-1">
        <span className="flex h-9 w-6 cursor-grab items-center justify-center text-slate-400" aria-hidden="true"><Icon name="menu" size={14} /></span>
        <button type="button" onClick={onOpen} aria-expanded={open} className="flex min-h-[44px] min-w-0 flex-1 flex-col justify-center text-left">
          <span className={cn("truncate text-sm font-bold", section.visible ? "text-navy-950" : "text-slate-500")}>{title}</span>
          <span className="text-xs text-slate-500">{section.visible ? `${section.items.length} of ${candidates.length} included` : "Hidden on this resume"}</span>
        </button>
        <span className="sr-only">Move</span>
        <Button variant="ghost" size="icon" className="h-8 w-8" aria-label={`Move ${title} up`} onClick={() => onMove(-1)}><Icon name="arrowUp" size={13} /></Button>
        <Button variant="ghost" size="icon" className="h-8 w-8" aria-label={`Move ${title} down`} onClick={() => onMove(1)}><Icon name="arrowDown" size={13} /></Button>
        <button
          type="button"
          role="switch"
          aria-checked={section.visible}
          aria-label={`Show ${title}`}
          onClick={() => onChange({ ...section, visible: !section.visible })}
          className={cn("flex h-6 w-11 shrink-0 items-center rounded-full p-0.5 transition-colors", section.visible ? "justify-end bg-brand-600" : "justify-start bg-slate-300")}
        >
          <span className="h-5 w-5 rounded-full bg-white shadow" />
        </button>
      </div>
      {open && (
        <ul className="space-y-1 px-3 pb-3">
          {ordered.length === 0 && <li className="py-2 text-[13px] text-slate-500">Nothing for this section yet. Add entries on your <Link className="font-semibold text-brand-700 underline" to="/career/profile">skill profile</Link>.</li>}
          {ordered.map((ref) => {
            const item = candidates.find((c) => c.item_id === ref.item_id)!;
            const on = included.has(ref.item_id);
            return (
              <li key={ref.item_id} className={cn("rounded-lg bg-white px-2.5 py-1.5 ring-1", focusItemId === ref.item_id ? "ring-accent-400" : "ring-slate-200/70")}>
                <div className="flex items-center gap-2">
                  <Checkbox label={itemSummary(item).heading || "(untitled)"} checked={on} onChange={() => toggle(ref.item_id)} />
                  {item.verified && <Badge tone="green">Verified</Badge>}
                </div>
                {on && !item.verified && item.kind !== "skill" && (
                  <BulletsEditor
                    resumeId={resumeId}
                    startOpen={focusItemId === ref.item_id}
                    context={itemSummary(item).heading}
                    profileBullets={Array.isArray(item.data.bullets) ? (item.data.bullets as string[]) : []}
                    override={included.get(ref.item_id)?.bullets ?? null}
                    onChange={(bullets) => onChange({ ...section, items: section.items.map((r) => (r.item_id === ref.item_id ? { ...r, bullets } : r)) })}
                  />
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

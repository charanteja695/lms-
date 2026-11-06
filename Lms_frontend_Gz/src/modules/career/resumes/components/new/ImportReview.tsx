import { KIND_LABELS } from "@/modules/career/common/labels";
import type { ImportResult } from "@/modules/career/profile/types";
import { Alert, Button, Checkbox, Icon } from "@/shared/ui";

/** What was read from the uploaded resume, grouped by kind with contact details and toggle options. */
export function ImportReview({
  result,
  chosen,
  onToggle,
  onSelectAll,
  onDeselectAll,
}: {
  result: ImportResult;
  chosen: Set<number>;
  onToggle: (index: number) => void;
  onSelectAll: () => void;
  onDeselectAll: () => void;
}) {
  const groups = new Map<string, number[]>();
  result.items.forEach((item, index) => {
    groups.set(item.kind, [...(groups.get(item.kind) ?? []), index]);
  });

  const profile = result.profile;
  const hasContactInfo = Boolean(profile.phone || profile.location || profile.headline || profile.summary);

  return (
    <div className="space-y-4">
      {/* Overview notice */}
      <div className="flex items-start gap-2.5 rounded-xl border border-blue-200/80 bg-blue-50/50 p-3.5 text-xs text-blue-900">
        <Icon name="info" size={16} className="shrink-0 text-blue-600 mt-0.5" />
        <div className="space-y-1">
          <p className="font-semibold text-blue-950">{result.message}</p>
          <p className="text-blue-800 leading-relaxed">
            Select the entries you want to include in your profile and resume. You can edit any details in the editor at any time.
          </p>
        </div>
      </div>

      {/* Extracted Contact Details summary if any */}
      {hasContactInfo && (
        <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-3.5">
          <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">Detected Contact Details</h4>
          <div className="flex flex-wrap gap-2 text-xs text-slate-700">
            {profile.headline && (
              <span className="inline-flex items-center gap-1 rounded-md bg-white border border-slate-200 px-2 py-1">
                <strong>Role:</strong> {profile.headline}
              </span>
            )}
            {profile.phone && (
              <span className="inline-flex items-center gap-1 rounded-md bg-white border border-slate-200 px-2 py-1">
                <Icon name="smartphone" size={12} className="text-slate-400" />
                {profile.phone}
              </span>
            )}
            {profile.location && (
              <span className="inline-flex items-center gap-1 rounded-md bg-white border border-slate-200 px-2 py-1">
                <Icon name="map" size={12} className="text-slate-400" />
                {profile.location}
              </span>
            )}
          </div>
        </div>
      )}

      {/* Items Count and Select/Deselect Actions */}
      {result.items.length > 0 ? (
        <div className="space-y-3">
          <div className="flex items-center justify-between text-xs">
            <span className="font-medium text-slate-600">
              Selected <strong>{chosen.size}</strong> of {result.items.length} items
            </span>
            <div className="flex gap-2">
              <Button variant="link" size="sm" onClick={onSelectAll} className="text-xs font-semibold text-brand-600">
                Select all
              </Button>
              <span className="text-slate-300">·</span>
              <Button variant="link" size="sm" onClick={onDeselectAll} className="text-xs font-semibold text-slate-500">
                Deselect all
              </Button>
            </div>
          </div>

          {/* Grouped Items List */}
          {[...groups.entries()].map(([kind, indexes]) => (
            <section key={kind} className="rounded-xl border border-slate-200/90 overflow-hidden bg-white shadow-2xs">
              <div className="flex items-center justify-between bg-slate-50/80 px-4 py-2 border-b border-slate-100">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-600">
                  {KIND_LABELS[kind as keyof typeof KIND_LABELS] ?? kind}
                </h3>
                <span className="text-[11px] font-semibold text-slate-400">
                  {indexes.length} {indexes.length === 1 ? "entry" : "entries"}
                </span>
              </div>
              <ul className="divide-y divide-slate-100">
                {indexes.map((index) => (
                  <li key={index} className="px-4 py-2 hover:bg-slate-50/40 transition-colors">
                    <Checkbox
                      label={result.items[index]!.label || "(untitled entry)"}
                      checked={chosen.has(index)}
                      onChange={() => onToggle(index)}
                    />
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      ) : (
        <Alert tone="info" title="No structured entries found">
          We extracted your document but didn't identify structured entries for your experience or skills. You can still create your resume draft and fill them in manually.
        </Alert>
      )}

      {result.skipped > 0 && (
        <p className="text-xs text-slate-400">
          Note: {result.skipped} {result.skipped === 1 ? "entry was" : "entries were"} skipped due to missing required fields.
        </p>
      )}
    </div>
  );
}

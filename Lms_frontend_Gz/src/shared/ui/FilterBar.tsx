import { useState, type ReactNode } from "react";

import { cn } from "@/core/lib/cn";
import { Button } from "./Button";
import { SearchInput } from "./SearchInput";

/**
 * Standard list toolbar: search + primary filters, and a "More filters" panel.
 * Controls apply immediately (each change is one request); nothing is fetched while typing.
 * On a phone only the search shows; the filters fold behind one "Filters" button so the results stay on screen.
 */
export function FilterBar({ search, onSearch, searchPlaceholder, primary, more, activeCount, onReset }: {
  search: string;
  onSearch: (value: string) => void;
  searchPlaceholder?: string;
  primary?: ReactNode;
  more?: ReactNode;
  activeCount: number;
  onReset: () => void;
}) {
  const [showMore, setShowMore] = useState(false);
  const [openOnPhone, setOpenOnPhone] = useState(false);
  const hasFilters = Boolean(primary || more);

  return (
    <div className="space-y-3 border-b border-slate-100 p-4">
      <div className="flex flex-wrap items-center gap-2 sm:gap-3">
        <SearchInput value={search} onChange={onSearch} placeholder={searchPlaceholder} className="min-w-0 flex-1 sm:w-72 sm:flex-none" />
        {hasFilters && (
          <Button variant="secondary" icon="filter" className="sm:hidden" aria-expanded={openOnPhone} onClick={() => setOpenOnPhone((v) => !v)}>
            {activeCount > 0 ? `Filters (${activeCount})` : "Filters"}
          </Button>
        )}
        <div className={cn("w-full flex-col gap-3 sm:contents", openOnPhone ? "flex" : "hidden")}>
          {primary}
          {more && (
            <Button variant="secondary" icon="filter" className="hidden sm:inline-flex" onClick={() => setShowMore((value) => !value)} aria-expanded={showMore}>
              More filters
            </Button>
          )}
          {more && <div className="grid gap-3 sm:hidden">{more}</div>}
          {activeCount > 0 && <Button variant="ghost" onClick={onReset}>Clear ({activeCount})</Button>}
        </div>
      </div>
      {more && showMore && <div className="hidden gap-3 rounded-lg bg-slate-50 p-4 sm:grid sm:grid-cols-2 lg:grid-cols-4">{more}</div>}
    </div>
  );
}

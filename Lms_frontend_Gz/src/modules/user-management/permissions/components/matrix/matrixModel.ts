import type { MatrixPage } from "@/modules/user-management/permissions/api/permissionAdminApi";

export interface PageGroup {
  title: string;
  pages: MatrixPage[];
}

/** The pages ``role`` may be given anything on, grouped by module in catalog order, filtered by a search. */
export function groupPages(pages: MatrixPage[], role: string, search: string): PageGroup[] {
  const q = search.trim().toLowerCase();
  const groups = new Map<string, MatrixPage[]>();
  for (const page of pages) {
    if (!page.holders.includes(role)) continue;
    if (q && !`${page.group} ${page.label} ${page.description}`.toLowerCase().includes(q)) continue;
    groups.set(page.group, [...(groups.get(page.group) ?? []), page]);
  }
  return [...groups].map(([title, items]) => ({ title, pages: items }));
}

/** The cell for a page's View: without it, the page's other actions do not count (the server applies the same rule). */
export const viewKey = (page: MatrixPage) => `${page.key}.view`;

export const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;

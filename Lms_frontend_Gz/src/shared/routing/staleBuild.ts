/**
 * After a new release, a tab still running the previous one may ask for a page file that no longer exists (each
 * build names its files by content). The fix is to load the new version: reload once. A short guard stops a reload loop
 * if the file is missing for some other reason (the error page is shown instead).
 */
const KEY = "lms.reloadedForNewVersion";
const GUARD_MS = 30_000;

export function isStaleBuildError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error ?? "");
  return /Failed to fetch dynamically imported module|Importing a module script failed|error loading dynamically imported module|Loading chunk .* failed/i.test(message);
}

/** Reload to the new version, unless we just did (returns false then, so the caller shows an error instead). */
export function reloadForNewVersion(): boolean {
  try {
    const last = Number(window.sessionStorage.getItem(KEY) ?? 0);
    if (Date.now() - last < GUARD_MS) return false;
    window.sessionStorage.setItem(KEY, String(Date.now()));
  } catch {
    /* storage unavailable: still reload once */
  }
  window.location.reload();
  return true;
}

/** A `from`/return link taken from the address bar: only a path inside this app is followed. */
export function safeInternalPath(value: string | null | undefined): string | undefined {
  return value && value.startsWith("/") && !value.startsWith("//") && !value.includes("\\") ? value : undefined;
}

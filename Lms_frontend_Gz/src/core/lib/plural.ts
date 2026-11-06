/** "1 question", "3 questions"; a missing count reads as "?". */
export function plural(count: number | null | undefined, one: string, many = `${one}s`): string {
  if (count == null) return `? ${many}`;
  return `${count.toLocaleString()} ${count === 1 ? one : many}`;
}

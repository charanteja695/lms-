/** A short client-side id for an option/item within a question body (1-20 letters/digits/-/_ per the API). Never shown to a student. */
export function newOptionId(): string {
  return Math.random().toString(36).slice(2, 8);
}

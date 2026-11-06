import { useGetInstitutionQuery } from "@/modules/user-management/institutions/api/institutionsApi";

/**
 * Several other services (subscription-service, learning-service, ...) return only an
 * `organization_id` on their own records, never a name — each keeps just a local id-only cache
 * of the institutions it references. This is the shared, narrow, read-only exception to
 * "modules don't reach into each other's internals" (see src/modules/README.md rule 5): any
 * module may resolve an institution id to its display name this way, but never write through it.
 */
export function useInstitutionName(organizationId: string) {
  const { data, isFetching } = useGetInstitutionQuery(organizationId, { skip: !organizationId });
  return { name: data?.name, code: data?.code, isFetching };
}

import { useSearchDirectoryQuery } from "@/modules/user-management/common/api/directoryApi";
import type { OrganizationType } from "@/modules/user-management/common/types";
import type { OptionsHook } from "@/shared/ui";

function directoryOptions(type: OrganizationType): OptionsHook {
  return (search, enabled) => {
    const { data, isFetching } = useSearchDirectoryQuery({ type, search_text: search.length >= 2 ? search : undefined, per_page: 20 }, { skip: !enabled });
    return { isFetching, options: (data?.items ?? []).map((o) => ({ value: o.organization_id, label: o.name, description: `${o.code} · ${o.city}` })) };
  };
}

/** Pickers over every organisation, for platform staff (see directoryApi). */
export const useAnyInstitutionOptions = directoryOptions("institution");
export const useAnyEmployerOptions = directoryOptions("employer");

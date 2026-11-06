import type { IsoDateTime } from "@/core/api/types";
import type { LanguageKind } from "@/modules/code-execution/common/types";

/** What every signed-in user gets: enough to render the editor and switch language. */
export interface Language {
  code: string;
  name: string;
  version: string;
  kind: LanguageKind;
  file_name: string;
  editor_mode: string;
  starter_template: string;
}

/** super_admin only: the engine configuration behind a language. */
export interface LanguageAdmin extends Language {
  engine_language_id: number | null;
  compiler_options: string | null;
  local_command: string[] | null;
  time_multiplier: number;
  memory_multiplier: number;
  enabled: boolean;
  sort_order: number;
  updated_at: IsoDateTime;
}

export interface LanguageCreateBody {
  code: string;
  name: string;
  version: string;
  kind?: LanguageKind;
  file_name: string;
  editor_mode: string;
  starter_template?: string | null;
  engine_language_id?: number | null;
  compiler_options?: string | null;
  time_multiplier?: number;
  memory_multiplier?: number;
  enabled?: boolean;
  sort_order?: number;
}

export interface LanguageUpdateBody {
  name?: string;
  version?: string;
  kind?: LanguageKind;
  file_name?: string;
  editor_mode?: string;
  starter_template?: string | null;
  engine_language_id?: number | null;
  compiler_options?: string | null;
  time_multiplier?: number;
  memory_multiplier?: number;
  enabled?: boolean;
  sort_order?: number;
}

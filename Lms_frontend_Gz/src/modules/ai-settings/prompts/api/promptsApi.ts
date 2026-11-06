import { baseApi } from "@/core/api/baseApi";
import type { ListResult, PageContext, PageParams } from "@/core/api/types";
import type { Capability, Prompt, PromptVersion } from "@/modules/ai-settings/common/types";

export interface PromptCreateBody {
  key: string;
  capability: Capability;
  owner_service: string;
  description: string;
}

export interface VersionCreateBody {
  template: string;
  variables: string[];
  allowed_tools: string[];
  model_params: Record<string, unknown>;
}

/** The prompt registry: every AI instruction the platform sends, versioned; a second person activates a version. */
export const promptsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listPrompts: build.query<ListResult<Prompt>, PageParams>({
      query: (params) => ({ url: "/prompts", params }),
      transformResponse: (r: { prompts: Prompt[]; page_context: PageContext }) => ({ items: r.prompts, pageContext: r.page_context }),
      providesTags: ["AiPrompts"],
    }),
    getPrompt: build.query<{ prompt: Prompt; versions: PromptVersion[] }, string>({
      query: (key) => `/prompts/${encodeURIComponent(key)}`,
      providesTags: (_r, _e, key) => [{ type: "AiPrompts", id: key }],
    }),
    createPrompt: build.mutation<Prompt, PromptCreateBody>({
      query: (body) => ({ url: "/prompts", method: "POST", body }),
      transformResponse: (r: { prompt: Prompt }) => r.prompt,
      invalidatesTags: ["AiPrompts"],
    }),
    createPromptVersion: build.mutation<PromptVersion, { key: string; body: VersionCreateBody }>({
      query: ({ key, body }) => ({ url: `/prompts/${encodeURIComponent(key)}/versions`, method: "POST", body }),
      transformResponse: (r: { version: PromptVersion }) => r.version,
      invalidatesTags: (_r, _e, { key }) => [{ type: "AiPrompts", id: key }],
    }),
    changeVersionStatus: build.mutation<PromptVersion, { key: string; version: number; action: "activate" | "retire" }>({
      query: ({ key, version, action }) => ({ url: `/prompts/${encodeURIComponent(key)}/versions/${version}/${action}`, method: "POST" }),
      transformResponse: (r: { version: PromptVersion }) => r.version,
      invalidatesTags: (_r, _e, { key }) => [{ type: "AiPrompts", id: key }],
    }),
  }),
});

export const { useListPromptsQuery, useGetPromptQuery, useCreatePromptMutation, useCreatePromptVersionMutation, useChangeVersionStatusMutation } = promptsApi;

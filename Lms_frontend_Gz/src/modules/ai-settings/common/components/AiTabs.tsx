import { useAiRights } from "@/modules/ai-settings/common/hooks/useAiRights";
import { SectionTabs } from "@/shared/ui";

/** The AI manager's four areas; someone who only sees their own usage gets no tabs (SectionTabs hides a single tab). */
export function AiTabs() {
  const { isManager } = useAiRights();
  return (
    <SectionTabs
      tabs={[
        { to: "/ai", label: "Usage & limits", icon: "chart" },
        { to: "/ai/models", label: "Models", icon: "layers", show: isManager },
        { to: "/ai/prompts", label: "Prompts", icon: "fileText", show: isManager },
        { to: "/ai/logs", label: "Request log", icon: "clock", show: isManager },
      ]}
    />
  );
}

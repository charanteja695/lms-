# AI settings module

> Status: **Done** · Backend: `lms-backend/ai-gateway` · Gated by the `ai_gateway` section and the `ai_settings` menu entry.

Who sees what comes from the server's permission list (`common/hooks/useAiRights.ts`), and ai-gateway re-checks every call:
- **`ai.manage`** (AI managers): every area below, for any organisation.
- **`ai.usage.own`** (institution head and staff by default): their own institution's usage page, read-only.

Sections (see [src/modules/README.md](../README.md) for the layout rules):

- `usage/`: an organisation's usage this month (requests, tokens, spend) against its limits, as progress bars that turn the
  logo orange near the limit and red at it. AI managers pick any institution and set the monthly limits or switch AI off.
- `models/`: the fallback order of providers for chat and for search. Reorder, add or remove, then save.
- `prompts/`: the prompt registry. Each prompt's versions, newest first. A new version starts as a draft, with its
  `{{placeholders}}` read from the text. Another AI manager puts it in use (the screen says so on your own drafts).
- `logs/`: every AI request with outcome, tokens and cost; open one to see what was sent and answered (personal data
  is removed before anything is stored).

Money is US cents from ai-gateway (providers bill in dollars), shown as US$ (`common/money.ts`).

**Backend changes made for this module:**
- ai-gateway: `GET /prompts/{key}` now returns `versions[]`.
- user-management: the `ai_settings` menu entry and `ai_gateway` section.

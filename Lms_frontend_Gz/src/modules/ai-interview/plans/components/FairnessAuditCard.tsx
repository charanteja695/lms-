import { useGetPlanAuditQuery } from "@/modules/ai-interview/plans/api/plansApi";
import { Alert, Badge, Card, DescriptionList, Spinner } from "@/shared/ui";

const pct = (v: unknown) => (typeof v === "number" ? `${(v * 100).toFixed(0)}%` : "—");

/** The screening plan's fairness audit: outcomes per institution (small groups skipped); a group under 80% of the best advance rate is flagged. */
export function FairnessAuditCard({ planId }: { planId: string }) {
  const { data: audit, isLoading } = useGetPlanAuditQuery(planId);
  if (isLoading) return <Card title="Fairness audit"><Spinner /></Card>;
  if (!audit) return null;
  const impact = audit.adverse_impact ?? {};
  const flagged = new Set(impact.flagged_groups ?? []);

  return (
    <Card title="Fairness audit" description={audit.note}>
      <DescriptionList
        items={[
          { label: "Interviews", value: String(audit.interviews ?? 0) },
          { label: "Evaluated", value: String(audit.evaluated ?? 0) },
          { label: "Reviewed by a person", value: String(audit.reviewed ?? 0) },
          { label: "Overridden", value: pct(audit.override_rate) },
          { label: "Unverifiable quotes", value: pct(audit.invalid_quote_rate) },
          { label: "Average score", value: typeof audit.average_score === "number" ? audit.average_score.toFixed(2) : "—" },
        ]}
      />
      {flagged.size > 0 && <Alert tone="warning" className="mt-3" title="Possible adverse impact">{impact.rule}</Alert>}
      {(impact.groups ?? []).length > 0 && (
        <ul className="mt-3 divide-y divide-slate-100 text-sm">
          {(impact.groups ?? []).map((g, i) => {
            const name = String(g.group);
            return (
              <li key={i} className="flex justify-between py-1.5">
                <span>{name} {flagged.has(name) && <Badge tone="red">Flagged</Badge>}{g.compared === false && <span className="ml-1 text-xs text-slate-400">(too few to compare)</span>}</span>
                <span className="text-slate-600">{pct(g.advance_rate)} advanced · {String(g.candidates)} candidates</span>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}

import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useNotify } from "@/core/hooks/useNotify";
import { OrgFilter } from "@/modules/billing/common/components/OrgFilter";
import { inr } from "@/modules/billing/common/format";
import { useBillingRights } from "@/modules/billing/common/hooks/useBillingRights";
import { useListActivePricesQuery } from "@/modules/billing/prices/api/pricesApi";
import { useCreateQuoteMutation } from "@/modules/billing/quotes/api/quotesApi";
import { Button, Card, EmptyState, Field, Input, PageHeader, Select } from "@/shared/ui";

interface Line { course_id: string; seats: string; term_days: string }
const blank: Line = { course_id: "", seats: "50", term_days: "365" };

/** Only priced courses can be quoted; the server works out pro-rating, discount and GST. */
export function QuoteCreatePage() {
  const navigate = useNavigate();
  const notify = useNotify();
  const { isManager } = useBillingRights();
  const { data: prices = [] } = useListActivePricesQuery("course_seat");
  const [create, { isLoading }] = useCreateQuoteMutation();
  const [org, setOrg] = useState({ id: "", label: "" });
  const [lines, setLines] = useState<Line[]>([blank]);
  const setLine = (i: number, patch: Partial<Line>) => setLines(lines.map((l, j) => (j === i ? { ...l, ...patch } : l)));
  const options = prices.map((p) => ({ value: p.code, label: `${p.name} — ${inr(p.unit_amount)} per seat per year` }));
  const valid = lines.every((l) => l.course_id && Number(l.seats) >= 1 && Number(l.term_days) >= 1) && (!isManager || Boolean(org.id));

  const submit = () =>
    void create({ organization_id: isManager ? org.id : undefined, lines: lines.map((l) => ({ course_id: l.course_id, seats: Number(l.seats), term_days: Number(l.term_days) })) })
      .unwrap()
      .then((q) => { notify.success("Quote ready"); navigate(`/billing/quotes/${q.quote_id}`); }, notify.apiError);

  return (
    <>
      <PageHeader title={isManager ? "New quote" : "Ask for a quote"} backTo="/billing/quotes" backLabel="Quotes" />
      {prices.length === 0 ? (
        <EmptyState icon="layers" title="No courses are priced yet" description="Ask the platform team to add a price for the course you want." />
      ) : (
        <Card>
          <div className="space-y-4">
            {isManager && <OrgFilter required value={org.id} label={org.label} onChange={(id, label) => setOrg({ id, label })} />}
            {lines.map((l, i) => (
              <div key={i} className="grid items-end gap-3 sm:grid-cols-[1fr_8rem_8rem_auto]">
                <Field label="Course" required>{(p) => <Select {...p} value={l.course_id} placeholder="Choose a course" options={options} onChange={(e) => setLine(i, { course_id: e.target.value })} />}</Field>
                <Field label="Seats" required>{(p) => <Input {...p} type="number" min={1} value={l.seats} onChange={(e) => setLine(i, { seats: e.target.value })} />}</Field>
                <Field label="Days" required>{(p) => <Input {...p} type="number" min={1} max={1095} value={l.term_days} onChange={(e) => setLine(i, { term_days: e.target.value })} />}</Field>
                <Button variant="ghost" icon="trash" aria-label="Remove course" disabled={lines.length === 1} onClick={() => setLines(lines.filter((_, j) => j !== i))} />
              </div>
            ))}
            <div className="flex justify-between">
              <Button variant="secondary" icon="plus" disabled={lines.length >= 20} onClick={() => setLines([...lines, blank])}>Add a course</Button>
              <Button loading={isLoading} disabled={!valid} onClick={submit}>Get quote</Button>
            </div>
          </div>
        </Card>
      )}
    </>
  );
}

import { Link } from "react-router-dom";

import { formatDate } from "@/core/lib/format";
import { inr } from "@/modules/billing/common/format";
import { useGetCourseQuery } from "@/modules/catalog/courses/api/coursesApi";
import type { CourseAccess, StoreOffer } from "@/modules/store/types";
import { Badge, Button, Icon } from "@/shared/ui";

/** One course on sale: what it is, what it costs (incl. GST), how long access lasts, and whether they already have it. */
export function OfferCard({ offer, access, canPay, busy, onBuy }: { offer: StoreOffer; access?: CourseAccess; canPay: boolean; busy: boolean; onBuy: () => void }) {
  const { data: course } = useGetCourseQuery(offer.course_id);
  const active = access?.status === "active";

  return (
    <article className="flex flex-col overflow-hidden rounded-2xl bg-white shadow-card ring-1 ring-slate-200/60 transition hover:-translate-y-0.5 hover:shadow-lift">
      <div
        className="relative flex h-32 flex-col justify-end gap-1 bg-brand-700 p-4 text-white"
        style={{ backgroundImage: "radial-gradient(rgb(255 255 255 / 0.14) 1.5px, transparent 1.5px)", backgroundSize: "18px 18px" }}
      >
        <span className="absolute left-3 top-3">
          {active ? <Badge tone="green">Yours until {formatDate(access.ends_at)}</Badge> : access ? <Badge tone="amber">Access ended</Badge> : null}
        </span>
        <h2 className="line-clamp-2 text-lg font-extrabold leading-snug">{course?.title ?? offer.name}</h2>
      </div>
      <div className="flex flex-1 flex-col gap-3 p-4">
        {course?.summary && <p className="line-clamp-3 text-sm text-slate-600">{course.summary}</p>}
        <div className="flex items-end justify-between gap-2">
          <div>
            <p className="text-2xl font-extrabold tabular-nums text-navy-950">{inr(offer.total)}</p>
            <p className="text-xs text-slate-500">incl. {inr(offer.gst)} GST</p>
          </div>
          <p className="inline-flex items-center gap-1 text-xs font-semibold text-slate-600">
            <Icon name="clock" size={14} />
            {offer.valid_days} days of access
          </p>
        </div>
        <div className="mt-auto flex gap-2">
          {active && (
            <Link to="/my-learning" className="flex h-11 flex-1 items-center justify-center rounded-xl bg-slate-100 text-sm font-bold text-navy-950 hover:bg-slate-200">
              Open
            </Link>
          )}
          <Button className="h-11 flex-1" variant={active ? "secondary" : "primary"} loading={busy} disabled={!canPay} onClick={onBuy}>
            {active ? `Extend ${offer.valid_days} days` : access ? "Buy again" : "Buy now"}
          </Button>
        </div>
      </div>
    </article>
  );
}

import { Badge } from "@/shared/ui";

interface Entry {
  item_id: string;
  verified?: boolean;
  heading: string;
  subheading?: string | null;
  dates?: string | null;
  bullets?: string[];
}

interface Snapshot {
  personal?: { name?: string; headline?: string | null; email?: string | null; phone?: string | null; location?: string | null };
  summary?: string | null;
  sections?: { key: string; title: string; entries: Entry[] }[];
}

/** The resume exactly as the candidate sent it (career-service's document, frozen at apply time). Verified entries are marked. */
export function ResumeSnapshot({ resume }: { resume: Record<string, unknown> }) {
  const doc = resume as Snapshot;
  const personal = doc.personal ?? {};
  return (
    <div className="space-y-3 text-sm text-slate-800">
      <div>
        <p className="text-base font-semibold text-slate-900">{personal.name}</p>
        {personal.headline && <p className="text-slate-600">{personal.headline}</p>}
        <p className="text-xs text-slate-500">{[personal.email, personal.phone, personal.location].filter(Boolean).join(" · ")}</p>
      </div>
      {doc.summary && <p className="whitespace-pre-wrap">{doc.summary}</p>}
      {(doc.sections ?? []).map((section) => (
        <section key={section.key}>
          <p className="mb-1 border-b border-slate-100 text-xs font-semibold uppercase tracking-wide text-slate-500">{section.title}</p>
          {section.key === "skills" ? (
            <p className="text-slate-800">{section.entries.map((entry) => entry.heading).join(" · ")}</p>
          ) : (
          <ul className="space-y-2">
            {section.entries.map((entry) => (
              <li key={entry.item_id}>
                <p className="font-medium">
                  {entry.heading}
                  {entry.subheading && <span className="font-normal text-slate-600"> — {entry.subheading}</span>}
                  {entry.verified && <Badge tone="green" className="ml-2">Verified</Badge>}
                  {entry.dates && <span className="ml-2 text-xs font-normal text-slate-500">{entry.dates}</span>}
                </p>
                {entry.bullets && entry.bullets.length > 0 && <ul className="list-disc pl-5 text-slate-700">{entry.bullets.map((b, i) => <li key={i}>{b}</li>)}</ul>}
              </li>
            ))}
          </ul>
          )}
        </section>
      ))}
    </div>
  );
}

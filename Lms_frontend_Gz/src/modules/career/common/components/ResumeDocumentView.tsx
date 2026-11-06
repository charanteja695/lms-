import type { ResumeDocument } from "@/modules/career/common/types";
import { Badge } from "@/shared/ui";

/** A plain, ATS-shaped rendering of a resume document — the same structure the PDF prints. */
export function ResumeDocumentView({ document, showVerified = true }: { document: ResumeDocument; showVerified?: boolean }) {
  const { personal } = document;
  const contact = [personal.email, personal.phone, personal.location].filter(Boolean).join(" · ");
  return (
    <article className="space-y-4 rounded-lg border border-slate-200 bg-white p-6 text-sm text-slate-800 [overflow-wrap:anywhere]">
      <header className="border-b border-slate-200 pb-3">
        <h2 className="text-xl font-semibold text-slate-900">{personal.name}</h2>
        {personal.headline && <p className="text-slate-600">{personal.headline}</p>}
        {contact && <p className="mt-1 text-xs text-slate-500">{contact}</p>}
        {personal.links.length > 0 && (
          <p className="mt-1 flex flex-wrap gap-x-3 text-xs">
            {personal.links.map((link) => (
              <a key={link.url} href={link.url} target="_blank" rel="noopener noreferrer" className="text-brand-700 hover:underline">
                {link.label}
              </a>
            ))}
          </p>
        )}
      </header>
      {document.summary && <p className="whitespace-pre-wrap">{document.summary}</p>}
      {document.sections.map((section) => (
        <section key={section.key}>
          <h3 className="mb-2 border-b border-slate-100 pb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">{section.title}</h3>
          {section.key === "skills" ? (
            // one line, the way the PDF prints it and parsers expect it
            <p className="text-slate-800">{section.entries.map((entry) => entry.heading).join(" · ")}</p>
          ) : (
          <ul className="space-y-3">
            {section.entries.map((entry) => (
              <li key={entry.item_id}>
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <p className="font-medium text-slate-900">
                    {entry.heading}
                    {entry.subheading && <span className="font-normal text-slate-600"> — {entry.subheading}</span>}
                    {showVerified && entry.verified && <Badge tone="green" className="ml-2">Verified</Badge>}
                  </p>
                  {(entry.dates || entry.location) && <span className="text-xs text-slate-500">{[entry.location, entry.dates].filter(Boolean).join(" · ")}</span>}
                </div>
                {entry.bullets.length > 0 && (
                  <ul className="mt-1 list-disc space-y-0.5 pl-5 text-slate-700">
                    {entry.bullets.map((bullet, index) => <li key={index}>{bullet}</li>)}
                  </ul>
                )}
              </li>
            ))}
          </ul>
          )}
        </section>
      ))}
    </article>
  );
}

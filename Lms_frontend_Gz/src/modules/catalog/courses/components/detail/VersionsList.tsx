import { useNavigate } from "react-router-dom";

import { formatDate } from "@/core/lib/format";
import { ContentStatusBadge } from "@/modules/catalog/common/components/ContentStatusBadge";
import type { Course } from "@/modules/catalog/courses/types";
import { Button, Card, EmptyState, Icon } from "@/shared/ui";

export function VersionsList({ course }: { course: Course }) {
  const navigate = useNavigate();
  const sorted = [...course.versions].sort((a, b) => b.version_number - a.version_number);

  return (
    <Card
      title="Curriculum Versions"
      description="Each version maintains its own complete tree of modules, topics, lessons and pass mark rules."
    >
      {sorted.length === 0 ? (
        <EmptyState
          icon="layers"
          title="No versions yet"
          description="Draft or published curriculum versions will appear here."
        />
      ) : (
        <div className="space-y-3">
          {sorted.map((version) => (
            <div
              key={version.version_id}
              onClick={() => navigate(`/courses/${course.course_id}/manage?step=2`)}
              className="group flex flex-wrap items-center justify-between gap-4 rounded-xl border border-slate-200/80 bg-white p-4 shadow-card transition-all duration-150 hover:border-brand-300 hover:shadow-lift cursor-pointer"
            >
              <div className="flex items-center gap-3.5">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-navy-950 font-bold text-white shadow-sm">
                  v{version.version_number}
                </span>

                <div>
                  <div className="flex items-center gap-2">
                    <p className="font-bold text-navy-950 group-hover:text-brand-700 transition-colors">
                      Version {version.version_number}
                    </p>
                    <ContentStatusBadge status={version.status} />
                  </div>

                  <p className="mt-0.5 text-xs text-slate-500">
                    {version.published_at ? (
                      <span>Published on {formatDate(version.published_at.slice(0, 10))}</span>
                    ) : (
                      <span>Version {version.version_number} · In progress</span>
                    )}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                <Button
                  size="sm"
                  variant="secondary"
                  icon="layers"
                  onClick={() => navigate(`/courses/${course.course_id}/manage?step=2`)}
                  className="group-hover:border-brand-300 group-hover:bg-brand-50/50 group-hover:text-brand-700 font-medium"
                >
                  Manage Modules
                  <Icon name="chevronRight" size={14} className="ml-1" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

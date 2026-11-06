import { cn } from "@/core/lib/cn";
import { TopicBlock } from "@/modules/catalog/builder/components/TopicBlock";
import type { CurriculumActions } from "@/modules/catalog/builder/hooks/useCurriculumActions";
import type { CourseTest } from "@/modules/catalog/builder/hooks/useCourseTests";
import type { ModuleDetail } from "@/modules/catalog/courses/curriculumTypes";
import { Badge, Button, Icon, Menu } from "@/shared/ui";

export interface OpenState {
  modules: Record<string, boolean>;
  topics: Record<string, boolean>;
}

const formatDuration = (seconds: number): string | null => {
  if (!seconds) return null;
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes} min${minutes === 1 ? "" : "s"}`;
};

/** A module card: displays module stats (duration, lessons, status), quick upload video/pdf/topic actions, and its topic contents. */
export function ModuleSection({
  module,
  number,
  count,
  open,
  highlightTopic,
  editable,
  actions,
  topicTest,
  testPath,
  onToggleModule,
  onToggleTopic,
}: {
  module: ModuleDetail;
  number: number;
  count: number;
  open: OpenState;
  highlightTopic: string | null;
  editable: boolean;
  actions: CurriculumActions;
  topicTest: (topicId: string) => CourseTest | undefined;
  testPath: (topicId: string) => string;
  onToggleModule: () => void;
  onToggleTopic: (topicId: string) => void;
}) {
  const expanded = Boolean(open.modules[module.module_id]);
  const lessons = module.topics.reduce((total, topic) => total + topic.items.length, 0);
  const videoCount = module.topics.reduce(
    (total, topic) => total + topic.items.filter((i) => i.item_type === "video").length,
    0
  );
  const pdfCount = module.topics.reduce(
    (total, topic) => total + topic.items.filter((i) => i.item_type === "pdf").length,
    0
  );
  const totalVideoSeconds = module.topics.reduce(
    (total, topic) =>
      total +
      topic.items.reduce(
        (sum, item) =>
          sum + (item.item_type === "video" && item.duration_seconds ? item.duration_seconds : 0),
        0
      ),
    0
  );
  const formattedDuration = formatDuration(totalVideoSeconds);

  const ready =
    module.topics.length > 0 &&
    module.topics.every(
      (topic) => topic.items.length > 0 && topicTest(topic.topic_id)?.composition?.valid
    );

  return (
    <section className="overflow-hidden rounded-2xl bg-white shadow-card ring-1 ring-slate-200/60">
      {/* Module Header Bar */}
      <div className="flex items-center gap-3 px-4 py-3.5">
        <button
          type="button"
          onClick={onToggleModule}
          aria-expanded={expanded}
          className="flex min-h-11 min-w-0 flex-1 items-center gap-3 text-left"
        >
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-600">
            <Icon
              name="chevronRight"
              size={17}
              className={cn("transition-transform", expanded && "rotate-90")}
            />
          </span>
          <span className="min-w-0">
            <span className="block text-[11px] font-extrabold tracking-[0.1em] text-brand-700">
              MODULE {number}
            </span>
            <span className="block truncate text-[17px] font-bold text-navy-950">
              {module.title}
            </span>
          </span>
        </button>

        <span className="hidden text-xs text-slate-500 lg:inline">
          {module.topics.length} {module.topics.length === 1 ? "topic" : "topics"} · {lessons}{" "}
          {lessons === 1 ? "lesson" : "lessons"}
          {formattedDuration ? ` · ${formattedDuration} video` : ""}
          {pdfCount > 0 ? ` · ${pdfCount} doc${pdfCount === 1 ? "" : "s"}` : ""}
        </span>

        <Badge tone={ready ? "green" : "amber"}>{ready ? "Ready" : "Needs work"}</Badge>

        {editable && (
          <Menu
            trigger={
              <Button variant="ghost" size="icon" aria-label={`More for ${module.title}`}>
                <Icon name="more" size={18} />
              </Button>
            }
            items={[
              {
                label: "Upload Video",
                icon: "video",
                onSelect: () => actions.uploadToModule(module, "video", number),
              },
              {
                label: "Upload PDF / Material",
                icon: "fileText",
                onSelect: () => actions.uploadToModule(module, "pdf", number),
              },
              { label: "Rename", icon: "edit", onSelect: () => actions.renameModule(module) },
              {
                label: "Move up",
                icon: "arrowUp",
                hidden: number === 1,
                onSelect: () => actions.moveModule(module, -1),
              },
              {
                label: "Move down",
                icon: "arrowDown",
                hidden: number === count,
                onSelect: () => actions.moveModule(module, 1),
              },
              {
                label: "Delete",
                icon: "trash",
                tone: "danger",
                onSelect: () => actions.deleteModule(module),
              },
            ]}
          />
        )}
      </div>

      {expanded && (
        <div className="space-y-3 px-4 pb-4">
          {/* Module Action Bar for Instructor / Admin */}
          {editable && (
            <div className="flex flex-wrap items-center justify-between gap-2.5 rounded-2xl border border-slate-200/90 bg-slate-50/80 p-2.5">
              <div className="flex items-center gap-2 pl-1">
                <span className="text-xs font-bold uppercase tracking-wider text-navy-950">
                  Module Actions:
                </span>
                <span className="text-xs text-slate-500">
                  {videoCount} {videoCount === 1 ? "video" : "videos"}
                  {formattedDuration ? ` (${formattedDuration})` : ""} · {pdfCount}{" "}
                  {pdfCount === 1 ? "material" : "materials"}
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  icon="plus"
                  onClick={() => actions.addTopic(module)}
                >
                  Add Topic
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  icon="video"
                  onClick={() => actions.uploadToModule(module, "video", number)}
                >
                  Upload Video
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  icon="fileText"
                  onClick={() => actions.uploadToModule(module, "pdf", number)}
                >
                  Upload PDF / Learning Material
                </Button>
              </div>
            </div>
          )}

          {/* Empty state when module has 0 topics */}
          {module.topics.length === 0 && (
            <div className="rounded-2xl border-2 border-dashed border-slate-200/90 bg-slate-50/50 p-6 text-center">
              <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-50 text-brand-700 mb-2">
                <Icon name="video" size={22} />
              </span>
              <p className="text-sm font-bold text-navy-950">No content in this module yet</p>
              <p className="mx-auto mt-1 mb-4 max-w-md text-xs text-slate-500">
                You can upload a video lesson directly to this module, or add a topic to structure
                your lessons.
              </p>
              {editable && (
                <div className="flex flex-wrap items-center justify-center gap-2">
                  <Button
                    variant="primary"
                    size="sm"
                    icon="video"
                    onClick={() => actions.uploadToModule(module, "video", number)}
                  >
                    Upload Video
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    icon="plus"
                    onClick={() => actions.addTopic(module)}
                  >
                    Add Topic
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    icon="fileText"
                    onClick={() => actions.uploadToModule(module, "pdf", number)}
                  >
                    Upload PDF / Learning Material
                  </Button>
                </div>
              )}
            </div>
          )}

          {/* Module Topics List */}
          {module.topics.map((topic, index) => (
            <TopicBlock
              key={topic.topic_id}
              module={module}
              topic={topic}
              code={`${number}.${index + 1}`}
              test={topicTest(topic.topic_id)}
              testPath={testPath(topic.topic_id)}
              index={index}
              count={module.topics.length}
              open={Boolean(open.topics[topic.topic_id])}
              highlighted={highlightTopic === topic.topic_id}
              editable={editable}
              actions={actions}
              onToggle={() => onToggleTopic(topic.topic_id)}
            />
          ))}

          {/* Bottom actions if topics are present */}
          {editable && module.topics.length > 0 && (
            <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-slate-100">
              <Button
                variant="ghost"
                size="sm"
                icon="plus"
                onClick={() => actions.addTopic(module)}
              >
                Add Topic
              </Button>
              <Button
                variant="ghost"
                size="sm"
                icon="video"
                onClick={() => actions.uploadToModule(module, "video", number)}
              >
                Upload Video
              </Button>
              <Button
                variant="ghost"
                size="sm"
                icon="fileText"
                onClick={() => actions.uploadToModule(module, "pdf", number)}
              >
                Upload PDF / Learning Material
              </Button>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

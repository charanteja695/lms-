import { cn } from "@/core/lib/cn";
import { LessonRow } from "@/modules/catalog/builder/components/LessonRow";
import { TestGate } from "@/modules/catalog/builder/components/TestGate";
import type { CurriculumActions } from "@/modules/catalog/builder/hooks/useCurriculumActions";
import type { CourseTest } from "@/modules/catalog/builder/hooks/useCourseTests";
import type { ModuleDetail, TopicDetail } from "@/modules/catalog/courses/curriculumTypes";
import { Badge, Button, Icon, Menu } from "@/shared/ui";

/** One topic: its lessons in order, then the test that closes it. */
export function TopicBlock({ module, topic, code, test, testPath, index, count, open, highlighted, editable, actions, onToggle }: {
  module: ModuleDetail;
  topic: TopicDetail;
  code: string;
  test: CourseTest | undefined;
  testPath: string;
  index: number;
  count: number;
  open: boolean;
  highlighted: boolean;
  editable: boolean;
  actions: CurriculumActions;
  onToggle: () => void;
}) {
  const ready = Boolean(test?.composition?.valid);
  const label = `Module ${code.split(".")[0]} · Topic ${code} ${topic.title}`;

  return (
    <div id={`topic-${topic.topic_id}`} className={cn("scroll-mt-28 rounded-2xl transition-shadow", highlighted ? "bg-amber-50 ring-2 ring-amber-400" : "bg-slate-50/80")}>
      <div className="flex items-center gap-2 px-2.5 py-2">
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={open}
          className="flex min-h-11 min-w-0 flex-1 items-center gap-2.5 rounded-xl px-1.5 text-left hover:bg-white/70"
        >
          <Icon name="chevronRight" size={16} className={cn("shrink-0 text-slate-500 transition-transform", open && "rotate-90")} />
          <span className="w-8 shrink-0 text-xs font-extrabold text-slate-500">{code}</span>
          <span className="truncate text-[15px] font-bold text-navy-950">{topic.title}</span>
        </button>
        <span className="hidden text-xs text-slate-500 sm:inline">{topic.items.length} {topic.items.length === 1 ? "lesson" : "lessons"}</span>
        <Badge tone={ready ? "green" : "amber"}>{ready ? "Test ready" : "Test incomplete"}</Badge>
        {editable && (
          <Menu
            trigger={
              <Button variant="ghost" size="icon" aria-label={`More for ${topic.title}`}>
                <Icon name="more" size={18} />
              </Button>
            }
            items={[
              { label: "Rename", icon: "edit", onSelect: () => actions.renameTopic(module, topic) },
              { label: "Move up", icon: "arrowUp", hidden: index === 0, onSelect: () => actions.moveTopic(module, topic, -1) },
              { label: "Move down", icon: "arrowDown", hidden: index === count - 1, onSelect: () => actions.moveTopic(module, topic, 1) },
              { label: "Delete", icon: "trash", tone: "danger", onSelect: () => actions.deleteTopic(module, topic) },
            ]}
          />
        )}
      </div>

      {open && (
        <div className="ml-6 space-y-2 border-l-2 border-slate-200 pb-3 pl-4 pr-3 sm:ml-12">
          {topic.items.length === 0 ? (
            <p className="px-2.5 py-2 text-sm text-slate-500">No lessons yet. Add a video or a PDF.</p>
          ) : (
            <ul className="space-y-0.5">
              {topic.items.map((item, i) => (
                <LessonRow
                  key={item.topic_item_id}
                  item={item}
                  index={i}
                  count={topic.items.length}
                  editable={editable}
                  onRename={() => actions.renameLesson(module, topic, item)}
                  onDelete={() => actions.deleteLesson(module, topic, item)}
                  onMove={(step) => actions.moveLesson(module, topic, item, step)}
                />
              ))}
            </ul>
          )}
          {editable && (
            <div className="flex flex-wrap gap-2 px-2.5">
              <Button size="sm" variant="secondary" icon="video" onClick={() => actions.upload(module, topic, "video", label)}>Add video</Button>
              <Button size="sm" variant="secondary" icon="fileText" onClick={() => actions.upload(module, topic, "pdf", label)}>Add PDF</Button>
            </div>
          )}
          <TestGate test={test} to={testPath} label="Topic test" needMcq={5} needPrograms={1} editable={editable} />
        </div>
      )}
    </div>
  );
}

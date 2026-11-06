import { useState } from "react";
import { Link } from "react-router-dom";

import { useNotify } from "@/core/hooks/useNotify";
import { useRemoveCourseFromPathMutation, useReorderPathCoursesMutation } from "@/modules/catalog/learning-paths/api/learningPathsApi";
import { AddCourseDialog } from "@/modules/catalog/learning-paths/components/detail/AddCourseDialog";
import type { LearningPath } from "@/modules/catalog/learning-paths/types";
import { Button, Card, EmptyState, Icon } from "@/shared/ui";

export function LearningPathItemsCard({ path, editable }: { path: LearningPath; editable: boolean }) {
  const notify = useNotify();
  const [adding, setAdding] = useState(false);
  const [removeCourse] = useRemoveCourseFromPathMutation();
  const [reorder] = useReorderPathCoursesMutation();
  const items = [...path.items].sort((a, b) => a.position - b.position);

  const move = async (index: number, direction: "up" | "down") => {
    const next = [...items];
    const swapWith = direction === "up" ? index - 1 : index + 1;
    [next[index], next[swapWith]] = [next[swapWith]!, next[index]!];
    try {
      await reorder({ id: path.learning_path_id, orderedIds: next.map((item) => item.course_id) }).unwrap();
    } catch (error) {
      notify.apiError(error);
    }
  };

  return (
    <Card title="Courses" description="The order learners follow them in." actions={editable && <Button size="sm" icon="plus" onClick={() => setAdding(true)}>Course</Button>}>
      {items.length === 0 ? (
        <EmptyState icon="graduation" title="No courses yet" description={editable ? "Add the first course to this path." : undefined} />
      ) : (
        <ul className="divide-y divide-slate-100">
          {items.map((item, index) => (
            <li key={item.course_id} className="flex items-center gap-3 py-3">
              <span className="w-6 text-center text-sm font-medium text-slate-400">{index + 1}</span>
              <div className="min-w-0 flex-1">
                <Link to={`/courses/${item.course_id}`} className="block truncate font-medium text-slate-900 hover:text-brand-700">
                  {item.title}
                </Link>
                <p className="truncate text-xs text-slate-500">{item.slug}</p>
              </div>
              {editable && (
                <div className="flex items-center gap-1">
                  <Button variant="ghost" size="icon" aria-label="Move up" disabled={index === 0} onClick={() => void move(index, "up")}>
                    <Icon name="arrowUp" size={14} />
                  </Button>
                  <Button variant="ghost" size="icon" aria-label="Move down" disabled={index === items.length - 1} onClick={() => void move(index, "down")}>
                    <Icon name="arrowDown" size={14} />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={`Remove ${item.title}`}
                    onClick={async () => {
                      try {
                        await removeCourse({ id: path.learning_path_id, courseId: item.course_id }).unwrap();
                        notify.success("Course removed");
                      } catch (error) {
                        notify.apiError(error);
                      }
                    }}
                  >
                    <Icon name="trash" size={14} />
                  </Button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
      {adding && <AddCourseDialog open={adding} onClose={() => setAdding(false)} learningPathId={path.learning_path_id} />}
    </Card>
  );
}

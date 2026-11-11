import { useState, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  useGetCourseQuery,
  useGetVersionQuery,
} from "@/modules/catalog/courses/api/coursesApi";
import {
  useCreateTopicMutation,
  useUpdateTopicMutation,
  useDeleteTopicMutation,
  useCreateItemMutation,
  useReorderTopicsMutation,
} from "@/modules/catalog/courses/api/curriculumApi";
import { AddChapterModal } from "@/modules/catalog/courses/components/modals/AddChapterModal";
import { AdminVideoPreviewModal } from "@/modules/catalog/courses/components/modals/AdminVideoPreviewModal";
import { AdminPdfPreviewModal } from "@/modules/catalog/courses/components/modals/AdminPdfPreviewModal";
import { ConfirmModal } from "@/modules/catalog/courses/components/common/ConfirmModal";
import { CoursePageHeader } from "@/modules/catalog/courses/components/common/CoursePageHeader";
import { Icon, PageLoader } from "@/shared/ui";
import { useNotify } from "@/core/hooks/useNotify";
import { usePermissions } from "@/modules/user-management/common/permissions/usePermissions";
import { useEffect } from "react";
import type { TopicDetail } from "@/modules/catalog/courses/curriculumTypes";

export function ModuleChaptersPage() {
  const { permissions } = usePermissions();
  const isSuperAdminOrAdmin = permissions.role === "super_admin" || permissions.role === "admin";
  const { courseId, moduleId } = useParams<{ courseId: string; moduleId: string }>();
  const navigate = useNavigate();
  const notify = useNotify();

  // If a student tries to open module chapters management, redirect immediately to learning page
  useEffect(() => {
    if (permissions.role === "student" && courseId) {
      navigate(`/courses/${courseId}/learn`, { replace: true });
    }
  }, [permissions.role, courseId, navigate]);

  const [isAddChapterOpen, setIsAddChapterOpen] = useState(false);
  const [editingChapter, setEditingChapter] = useState<TopicDetail | null>(null);
  const [deletingChapter, setDeletingChapter] = useState<TopicDetail | null>(null);
  const [videoPreviewTarget, setVideoPreviewTarget] = useState<{
    chapterTitle: string;
    itemTitle?: string;
    mediaId?: string | number | null;
  } | null>(null);
  const [pdfPreviewTarget, setPdfPreviewTarget] = useState<{
    chapterTitle: string;
    itemTitle?: string;
    mediaId?: string | number | null;
  } | null>(null);

  // Fetch Course
  const {
    data: course,
    isLoading: isCourseLoading,
    isError: isCourseError,
  } = useGetCourseQuery(courseId ?? "", {
    skip: !courseId,
    refetchOnMountOrArgChange: true,
  });

  const versionId = course?.versions?.[course.versions.length - 1]?.version_id;

  // Fetch full curriculum version
  const {
    data: versionDetail,
    isLoading: isVersionLoading,
    refetch: refetchVersion,
  } = useGetVersionQuery(
    { courseId: courseId ?? "", versionId: versionId ?? "" },
    { skip: !courseId || !versionId, refetchOnMountOrArgChange: true }
  );

  const [createTopic] = useCreateTopicMutation();
  const [updateTopic] = useUpdateTopicMutation();
  const [deleteTopic] = useDeleteTopicMutation();
  const [createItem] = useCreateItemMutation();
  const [reorderTopics] = useReorderTopicsMutation();
  const [draggedChapterIndex, setDraggedChapterIndex] = useState<number | null>(null);

  const handleDropChapter = async (dropIndex: number) => {
    if (draggedChapterIndex === null || draggedChapterIndex === dropIndex) return;
    const reordered = [...chapters];
    const [moved] = reordered.splice(draggedChapterIndex, 1);
    if (!moved) return;
    reordered.splice(dropIndex, 0, moved);
    setDraggedChapterIndex(null);

    if (courseId && versionId && moduleId) {
      try {
        await reorderTopics({
          courseId,
          versionId,
          moduleId,
          orderedIds: reordered.map((c) => c.topic_id),
        }).unwrap();
        notify.success("Chapter order saved");
      } catch (err: any) {
        notify.apiError(err);
      }
    }
  };

  const currentModule = useMemo(() => {
    if (!versionDetail?.modules) return null;
    return versionDetail.modules.find((m) => m.module_id === moduleId) || null;
  }, [versionDetail?.modules, moduleId]);

  const chapters = useMemo(() => {
    if (!currentModule?.topics) return [];
    return [...currentModule.topics].sort((a, b) => a.position - b.position);
  }, [currentModule?.topics]);

  if (isCourseLoading || isVersionLoading) {
    return <PageLoader label="Loading chapters..." />;
  }

  if (isCourseError || !course || !currentModule) {
    return (
      <div className="flex flex-col items-center justify-center p-16 text-center max-w-md mx-auto">
        <div className="w-12 h-12 rounded-full bg-rose-100 text-rose-600 flex items-center justify-center mb-4">
          <Icon name="alertCircle" size={24} />
        </div>
        <h3 className="text-base font-bold text-slate-900 mb-1">Module not found</h3>
        <p className="text-xs text-slate-500 mb-5">The requested module could not be found or loaded.</p>
        <button
          type="button"
          onClick={() => navigate(courseId ? `/courses/${courseId}` : "/courses")}
          className="px-4 py-2 rounded-xl bg-[#00663C] text-xs font-bold text-white hover:bg-[#00522F] cursor-pointer"
        >
          Back to Course Hub
        </button>
      </div>
    );
  }

  const handleSaveChapter = async (data: {
    title: string;
    position: number;
    description: string;
    objectives: string[];
    materials: Array<{ type: "video" | "pdf" | "note"; name: string; size?: string }>;
  }) => {
    if (!courseId || !versionId || !moduleId) return;
    try {
      if (editingChapter) {
        await updateTopic({
          courseId,
          versionId,
          moduleId,
          topicId: editingChapter.topic_id,
          body: { title: data.title },
        }).unwrap();
        notify.success("Chapter updated");
      } else {
        const res = await createTopic({
          courseId,
          versionId,
          moduleId,
          body: { title: data.title, pass_mark: 70 },
        }).unwrap();

        // Create initial material items if uploaded
        if (data.materials && data.materials.length > 0 && res.topic?.topic_id) {
          for (const mat of data.materials) {
            await createItem({
              courseId,
              versionId,
              moduleId,
              topicId: res.topic.topic_id,
              body: {
                item_type: mat.type === "video" ? "video" : mat.type === "pdf" ? "pdf" : "notes",
                title: mat.name,
                media_id: (mat as any).media_id || undefined,
              },
            }).unwrap();
          }
        }
        notify.success("Chapter created");
      }
      refetchVersion();
      setEditingChapter(null);
    } catch (err: any) {
      notify.apiError(err);
    }
  };

  const handleDeleteChapter = async () => {
    if (!courseId || !versionId || !moduleId || !deletingChapter) return;
    try {
      await deleteTopic({
        courseId,
        versionId,
        moduleId,
        topicId: deletingChapter.topic_id,
      }).unwrap();
      notify.success("Chapter deleted");
      setDeletingChapter(null);
      refetchVersion();
    } catch (err: any) {
      notify.apiError(err);
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6 pb-12">
      {/* 1. Universal Breadcrumbs & Back Header */}
      <CoursePageHeader
        breadcrumbs={[
          { label: "Courses", href: "/courses" },
          { label: course.title, href: `/courses/${courseId}` },
          { label: currentModule.title, href: `/courses/${courseId}?tab=modules` },
          { label: "Chapters", current: true },
        ]}
        title={`${currentModule.title} · Chapters`}
        description="Step 3 of 5: Upload videos, PDFs, and notes to your chapters, then proceed to approve questions."
        backHref={`/courses/${courseId}`}
        actions={
          <div className="flex items-center gap-2.5">
            {chapters.length > 0 && (
              <button
                type="button"
                onClick={() => navigate(`/courses/${courseId}/questions/review?step=4`)}
                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl border border-slate-300 bg-white text-xs font-bold text-slate-700 hover:bg-slate-50 cursor-pointer shadow-2xs"
              >
                <span>Continue to Step 4 (Approve questions)</span>
                <Icon name="arrow-right" size={14} />
              </button>
            )}
            {isSuperAdminOrAdmin && (
              <button
                type="button"
                onClick={() => {
                  setEditingChapter(null);
                  setIsAddChapterOpen(true);
                }}
                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-[#00663C] text-xs font-bold text-white hover:bg-[#00522F] cursor-pointer shadow-xs"
              >
                <Icon name="plus" size={15} /> Add chapter
              </button>
            )}
          </div>
        }
      />

      {/* Chapters Card */}
      <div className="rounded-2xl border border-slate-200 bg-white shadow-2xs overflow-hidden">
        <div className="flex items-center justify-between p-5 border-b border-slate-100 bg-slate-50/50">
          <div>
            <h3 className="text-sm font-bold text-[#0A1530]">Chapters</h3>
            <p className="text-xs text-slate-500 font-medium mt-0.5">
              Each chapter can include video, PDF, notes, and an AI-generated exam test.
            </p>
          </div>
          <span className="rounded-full bg-emerald-50 text-[#00663C] px-2.5 py-0.5 text-xs font-bold">
            {chapters.length} {chapters.length === 1 ? "chapter" : "chapters"} total
          </span>
        </div>

        {chapters.length === 0 ? (
          <div className="p-16 text-center">
            <Icon name="fileText" size={32} className="mx-auto text-slate-300 mb-2" />
            <h4 className="text-sm font-bold text-slate-800">No chapters yet</h4>
            <p className="text-xs text-slate-500 mt-1 mb-4">
              Add your first chapter to upload learning materials and generate questions.
            </p>
            {isSuperAdminOrAdmin && (
              <button
                type="button"
                onClick={() => setIsAddChapterOpen(true)}
                className="px-4 py-2 rounded-xl bg-[#00663C] text-xs font-bold text-white hover:bg-[#00522F] cursor-pointer shadow-xs"
              >
                Add chapter
              </button>
            )}
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {chapters.map((ch, idx) => {
              const items = ch.items ?? [];
              const videoItem = items.find((i) => i.item_type === "video");
              const pdfItem = items.find((i) => i.item_type === "pdf");
              const hasVideo = Boolean(videoItem);
              const hasPdf = Boolean(pdfItem);
              const hasNotes = items.some((i) => i.item_type === "notes");
              const hasMaterials = items.length > 0;
              const hasTest = Boolean(ch.topic_test_id);

              return (
                <div
                  key={ch.topic_id}
                  draggable
                  onDragStart={() => setDraggedChapterIndex(idx)}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={() => handleDropChapter(idx)}
                  className="flex items-center gap-4 p-4 hover:bg-slate-50/70 transition-colors cursor-move"
                >
                  <button
                    type="button"
                    className="text-slate-300 hover:text-slate-600 cursor-grab p-1"
                    title="Drag to reorder"
                  >
                    <Icon name="menu" size={16} />
                  </button>

                  <span className="w-7 h-7 rounded-lg bg-slate-100 border border-slate-200 text-slate-700 text-xs font-bold flex items-center justify-center shrink-0">
                    {idx + 1}
                  </span>

                  <div className="min-w-0 flex-1">
                    <h4 className="text-sm font-bold text-[#0A1530] truncate">{ch.title}</h4>
                    <div className="flex flex-wrap items-center gap-3 mt-1 text-xs text-slate-400 font-medium">
                      {hasVideo && (
                        <span className="inline-flex items-center gap-1.5 text-slate-600">
                          <span className="inline-flex items-center gap-1">
                            <Icon name="play" size={13} className="text-[#00663C]" /> Video
                          </span>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setVideoPreviewTarget({
                                chapterTitle: ch.title,
                                itemTitle: videoItem?.title || "Chapter Video",
                                mediaId: videoItem?.media_id,
                              });
                            }}
                            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-emerald-50 text-[#00663C] hover:bg-[#00663C] hover:text-white border border-emerald-200/80 font-bold text-[11px] transition-all cursor-pointer shadow-2xs"
                            title="Preview uploaded video"
                          >
                            <Icon name="play" size={10} className="fill-current" />
                            <span>Preview</span>
                          </button>
                        </span>
                      )}
                      {hasPdf && (
                        <span className="inline-flex items-center gap-1.5 text-slate-600">
                          <span className="inline-flex items-center gap-1">
                            <Icon name="fileText" size={13} className="text-[#00663C]" /> PDF
                          </span>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setPdfPreviewTarget({
                                chapterTitle: ch.title,
                                itemTitle: pdfItem?.title || "Chapter PDF",
                                mediaId: pdfItem?.media_id,
                              });
                            }}
                            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-blue-50 text-[#2563EB] hover:bg-[#2563EB] hover:text-white border border-blue-200/80 font-bold text-[11px] transition-all cursor-pointer shadow-2xs"
                            title="View uploaded PDF"
                          >
                            <Icon name="fileText" size={10} />
                            <span>View PDF</span>
                          </button>
                        </span>
                      )}
                      {hasNotes && (
                        <span className="inline-flex items-center gap-1 text-slate-600">
                          <Icon name="edit" size={13} className="text-[#00663C]" /> Notes
                        </span>
                      )}
                      {!hasMaterials && (
                        <span className="text-slate-400 text-[11px] italic">
                          No materials uploaded yet
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Real Status Chip based on actual data */}
                  <div className="shrink-0 hidden sm:block">
                    {hasTest ? (
                      <span className="rounded-full bg-[#E7F3EC] text-[#00663C] px-3 py-1 text-xs font-bold">
                        Test linked
                      </span>
                    ) : hasMaterials ? (
                      <span className="rounded-full bg-indigo-50 text-indigo-700 px-3 py-1 text-xs font-bold">
                        Ready for AI generator
                      </span>
                    ) : (
                      <span className="rounded-full bg-slate-100 text-slate-500 border border-slate-200 px-3 py-1 text-xs font-semibold">
                        Add PDF or notes
                      </span>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      type="button"
                      onClick={() =>
                        navigate(
                          `/courses/${courseId}/modules/${moduleId}/chapters/${ch.topic_id}/questions`
                        )
                      }
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#2563EB] text-xs font-bold text-white hover:bg-blue-700 cursor-pointer shadow-xs"
                    >
                      <Icon name="clipboardCheck" size={13} /> Chapter Test ({ch.topic_test_id ? "Linked" : "Manage"})
                    </button>

                    <button
                      type="button"
                      onClick={() =>
                        navigate(
                          `/courses/${courseId}/modules/${moduleId}/chapters/${ch.topic_id}/ai-generate`
                        )
                      }
                      className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-slate-200 bg-white text-xs font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer shadow-2xs"
                    >
                      <Icon name="sparkles" size={13} className="text-indigo-600" /> AI Generator
                    </button>

                    <button
                      type="button"
                      onClick={() => {
                        setEditingChapter(ch);
                        setIsAddChapterOpen(true);
                      }}
                      className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 cursor-pointer"
                      title="Edit chapter"
                    >
                      <Icon name="edit" size={15} />
                    </button>
                    <button
                      type="button"
                      onClick={() => setDeletingChapter(ch)}
                      className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 cursor-pointer"
                      title="Delete chapter"
                    >
                      <Icon name="trash" size={15} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Add / Edit Chapter Modal */}
      <AddChapterModal
        courseId={courseId}
        moduleId={moduleId}
        isOpen={isAddChapterOpen}
        onClose={() => {
          setIsAddChapterOpen(false);
          setEditingChapter(null);
        }}
        onSubmit={handleSaveChapter}
        initialData={
          editingChapter
            ? {
                title: editingChapter.title,
                position: editingChapter.position,
                description: editingChapter.description || "",
              }
            : null
        }
        moduleTitle={currentModule.title}
        defaultPosition={chapters.length + 1}
      />

      {/* Confirm Delete Chapter Modal */}
      {deletingChapter && (
        <ConfirmModal
          isOpen={Boolean(deletingChapter)}
          title="Delete chapter"
          description={`Are you sure you want to delete "${deletingChapter.title}"? All learning materials and test questions in this chapter will be permanently removed.`}
          confirmLabel="Delete"
          tone="danger"
          onConfirm={handleDeleteChapter}
          onClose={() => setDeletingChapter(null)}
        />
      )}

      {/* Video Preview Modal */}
      {videoPreviewTarget && (
        <AdminVideoPreviewModal
          isOpen={Boolean(videoPreviewTarget)}
          onClose={() => setVideoPreviewTarget(null)}
          chapterTitle={videoPreviewTarget.chapterTitle}
          itemTitle={videoPreviewTarget.itemTitle}
          mediaId={videoPreviewTarget.mediaId}
        />
      )}

      {/* PDF Preview Modal */}
      {pdfPreviewTarget && (
        <AdminPdfPreviewModal
          isOpen={Boolean(pdfPreviewTarget)}
          onClose={() => setPdfPreviewTarget(null)}
          chapterTitle={pdfPreviewTarget.chapterTitle}
          itemTitle={pdfPreviewTarget.itemTitle}
          mediaId={pdfPreviewTarget.mediaId}
        />
      )}
    </div>
  );
}

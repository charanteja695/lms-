import type { IntegrityWarning } from "@/modules/assessments/attempts/hooks/proctoring/useProctorBrowserEvents";
import { Button, Icon, Modal } from "@/shared/ui";

const COPY: Record<IntegrityWarning["kind"], { title: string; text: string }> = {
  left_test: {
    title: "You left the test",
    text: "Switching tabs, opening another window or leaving full screen is not allowed during this test. Each time is recorded and shared with your reviewer.",
  },
  copy_paste: {
    title: "Copy and paste are turned off",
    text: "Copying, cutting and pasting are blocked during this test. The attempt was recorded.",
  },
};

/** Tells the student, in the moment, that a rule was broken; closing it puts the test back in full screen. */
export function IntegrityWarningDialog({ warning, onResume }: { warning: IntegrityWarning | null; onResume: () => void }) {
  if (!warning) return null;
  const copy = COPY[warning.kind];
  return (
    <Modal
      open
      onClose={onResume}
      size="sm"
      title={
        <span className="flex items-center gap-2 text-red-700">
          <Icon name="alert" size={20} />
          {copy.title}
        </span>
      }
      footer={
        <Button className="w-full" onClick={onResume}>
          Return to the test
        </Button>
      }
    >
      <p className="text-sm text-slate-700">{copy.text}</p>
      <p className="mt-3 rounded-xl bg-red-50 px-3 py-2 text-sm font-semibold text-red-800">
        Warnings so far: {warning.count}
      </p>
    </Modal>
  );
}

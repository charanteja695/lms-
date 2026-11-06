import { useNavigate } from "react-router-dom";

import { tutorAttachmentStorage } from "@/core/lib/storage";
import { useCan } from "@/modules/user-management/common/permissions/useCan";
import { Button } from "@/shared/ui";

/** Opens the AI tutor with this code attached (up to 8,000 characters), for students who may use the tutor. */
export function AskTutorButton({ code, language, title }: { code: string; language: string; title: string }) {
  const navigate = useNavigate();
  const { holds } = useCan();
  if (!holds("tutor.chat")) return null;
  return (
    <Button
      variant="ghost"
      icon="helpCircle"
      disabled={!code.trim()}
      onClick={() => {
        tutorAttachmentStorage.write({ code, language, title });
        navigate("/tutor");
      }}
    >
      Ask the AI tutor
    </Button>
  );
}

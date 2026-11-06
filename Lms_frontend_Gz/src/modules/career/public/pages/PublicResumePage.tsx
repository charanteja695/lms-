import { useParams } from "react-router-dom";

import { env } from "@/core/config/env";
import { ResumeDocumentView } from "@/modules/career/common/components/ResumeDocumentView";
import { useGetPublicResumeQuery } from "@/modules/career/public/api/publicResumeApi";
import { Alert, Button, PageLoader } from "@/shared/ui";

/** A shared resume link, no sign-in. Unknown, revoked and expired links all answer the same "not found". */
export function PublicResumePage() {
  const { token = "" } = useParams();
  const { data, isLoading, isError } = useGetPublicResumeQuery(token, { skip: !token });

  if (isLoading) return <PageLoader />;
  if (isError || !data) return <Alert tone="error" title="This resume link isn't available">It may have expired or been turned off by its owner.</Alert>;

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button icon="download" onClick={() => window.open(`${env.apiBaseUrl}/public/resumes/${encodeURIComponent(token)}/pdf`, "_blank", "noopener,noreferrer")}>
          Download PDF
        </Button>
      </div>
      <ResumeDocumentView document={data.document} />
      <p className="text-center text-xs text-slate-400">Entries marked Verified were issued by {env.appName}.</p>
    </div>
  );
}

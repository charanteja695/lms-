import { useMemo } from "react";

import { formatDate } from "@/core/lib/format";
import { CertificateStatusBadge, PdfStatusBadge } from "@/modules/certificates/common/components/StatusBadges";
import type { Certificate } from "@/modules/certificates/issued/types";
import type { Column } from "@/shared/ui";

export function useCertificateColumns(showStudent: boolean) {
  return useMemo<Column<Certificate>[]>(
    () => [
      ...(showStudent ? [{ key: "student", header: "Student", render: (item: Certificate) => item.student_name ?? `#${item.student_user_id}` }] : []),
      { key: "course", header: "Course", render: (item) => item.course_title ?? `#${item.course_id}` },
      { key: "grade", header: "Grade", hideOnMobile: true, render: (item) => item.grade ?? "—" },
      { key: "score", header: "Score", hideOnMobile: true, render: (item) => `${item.score_percent.toFixed(1)}%` },
      { key: "status", header: "Status", render: (item) => <CertificateStatusBadge status={item.status} /> },
      { key: "pdf", header: "", hideOnMobile: true, render: (item) => (item.pdf_status === "ready" ? null : <PdfStatusBadge status={item.pdf_status} />) },
      { key: "issued", header: "Issued", hideOnMobile: true, render: (item) => formatDate(item.issued_at) },
    ],
    [showStudent],
  );
}

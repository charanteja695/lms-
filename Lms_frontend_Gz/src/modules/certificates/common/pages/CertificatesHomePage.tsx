import { Navigate } from "react-router-dom";

import { useCan } from "@/modules/user-management/common/permissions/useCan";

/**
 * The "certificates" section covers two audiences that 403 on each other's lists: students, institution
 * staff and exam managers read issued certificates; content authors/reviewers write templates. One nav
 * item points here and this sends each person to the list they can open.
 */
export function CertificatesHomePage() {
  const { can, holds } = useCan();
  const readsCertificates = holds("certificates.own") || holds("certificates.students") || can("exams.manage");
  return <Navigate to={readsCertificates ? "/certificates/issued" : "/certificates/templates"} replace />;
}

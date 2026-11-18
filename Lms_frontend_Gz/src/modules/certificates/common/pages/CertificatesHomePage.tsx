import { Navigate } from "react-router-dom";
import { useAuth } from "@/modules/user-management/auth/hooks/useAuth";
import { useCan } from "@/modules/user-management/common/permissions/useCan";

/**
 * The "certificates" section covers two audiences:
 * - Students and staff view issued certificates or courses/certificates.
 * - Content authors/reviewers write templates.
 */
export function CertificatesHomePage() {
  const { role } = useAuth();
  const { can, holds } = useCan();

  if (role === "student") {
    return <Navigate to="/courses/my" replace />;
  }

  const readsCertificates = holds("certificates.own") || holds("certificates.students") || can("exams.manage");
  return <Navigate to={readsCertificates ? "/certificates/issued" : "/certificates/templates"} replace />;
}

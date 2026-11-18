import { useAuth } from "@/modules/user-management/auth/hooks/useAuth";
import { AdminDashboardView } from "../components/AdminDashboardView";
import { StudentDashboardView } from "../components/StudentDashboardView";
import { InstitutionDashboardView } from "../components/InstitutionDashboardView";

export function DashboardPage() {
  const { user } = useAuth();

  if (!user) return null;

  if (user.role === "student") {
    return <StudentDashboardView />;
  }

  if (user.role === "institution_head" || (user as any).organization_type === "institution") {
    return <InstitutionDashboardView />;
  }

  return <AdminDashboardView />;
}

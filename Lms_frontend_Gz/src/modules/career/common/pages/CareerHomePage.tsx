import { Navigate } from "react-router-dom";
import { useAuth } from "@/modules/user-management/auth/hooks/useAuth";
import { useCan } from "@/modules/user-management/common/permissions/useCan";
import { CareerPlacementsPage } from "./CareerPlacementsPage";

export function CareerHomePage() {
  const { user } = useAuth();
  const { holds } = useCan();

  if (user?.role === "student") {
    return <CareerPlacementsPage />;
  }

  return <Navigate to={holds("career.profile") ? "/career/profile" : "/career/students"} replace />;
}

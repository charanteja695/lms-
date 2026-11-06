import { useNavigate, useParams } from "react-router-dom";

import { useGetStudentCareerProfileQuery } from "@/modules/career/profile/api/profileApi";
import { ProfileView } from "@/modules/career/profile/components/ProfileView";
import { Button, EmptyState, type IconName, PageHeader, PageLoader } from "@/shared/ui";

interface ApiErrorData {
  status?: string;
  code?: string;
  message?: string;
  details?: unknown[];
}

export function StudentProfilePage() {
  const { userId = "" } = useParams();
  const navigate = useNavigate();
  const { data, isLoading, isError, error } = useGetStudentCareerProfileQuery(userId, { skip: !userId });

  if (isLoading) return <PageLoader />;

  if (isError || !data) {
    let title = "Profile not available";
    let description = "The requested student profile could not be loaded.";
    let icon: IconName = "alert";

    if (error && "status" in error) {
      const errData = error.data as ApiErrorData | undefined;
      const code = errData?.code;
      const serverMsg = errData?.message;

      if (error.status === 404 || code === "STUDENT_NOT_FOUND") {
        title = "Student profile not found";
        description = serverMsg || "No career profile was found for this student. The student may not have set up their profile yet.";
        icon = "search";
      } else if (error.status === 403) {
        icon = "shield";
        if (code === "DIFFERENT_INSTITUTION") {
          title = "Different institution";
          description = serverMsg || "This student belongs to a different institution and cannot be accessed with your current account permissions.";
        } else {
          title = "Access restricted";
          description = serverMsg || "You do not have permission to view this student's profile.";
        }
      } else if (error.status === "FETCH_ERROR") {
        title = "Connection error";
        description = "Unable to connect to the server. Please check your network connection and try again.";
      } else if (typeof error.status === "number" && error.status >= 500) {
        title = "Service unavailable";
        description = "The career profile service is temporarily unavailable. Please try again later.";
      } else if (serverMsg) {
        description = serverMsg;
      }
    }

    return (
      <>
        <PageHeader title="Student profile" description="Skill profile (read only)" backTo="/career/students" backLabel="Student profiles" />
        <EmptyState
          icon={icon}
          title={title}
          description={description}
          action={
            <Button variant="secondary" onClick={() => navigate("/career/students")}>
              Back to student profiles
            </Button>
          }
        />
      </>
    );
  }

  return (
    <>
      <PageHeader title={data.personal.name} description="Skill profile (read only)" backTo="/career/students" backLabel="Student profiles" />
      <ProfileView data={data} editable={false} />
    </>
  );
}

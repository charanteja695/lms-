import { useNavigate } from "react-router-dom";

import { useGetMyCareerProfileQuery } from "@/modules/career/profile/api/profileApi";
import { ProfileView } from "@/modules/career/profile/components/ProfileView";
import { Button, EmptyState, PageHeader, PageLoader } from "@/shared/ui";

export function MyProfilePage() {
  const navigate = useNavigate();
  const { data, isLoading, isError, refetch } = useGetMyCareerProfileQuery();

  return (
    <>
      <PageHeader
        title="Skill profile"
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="secondary" icon="briefcase" onClick={() => navigate("/jobs/board")}>
              Explore Jobs
            </Button>
            <Button variant="secondary" icon="video" onClick={() => navigate("/interviews/practice")}>
              Practice Interview
            </Button>
            <Button icon="fileText" onClick={() => navigate("/career/resumes")}>
              My Resumes
            </Button>
          </div>
        }
      />
      {isLoading ? (
        <PageLoader />
      ) : isError || !data ? (
        <EmptyState icon="alert" title="Could not load your profile" action={<Button variant="secondary" onClick={() => void refetch()}>Try again</Button>} />
      ) : (
        <ProfileView data={data} editable />
      )}
    </>
  );
}

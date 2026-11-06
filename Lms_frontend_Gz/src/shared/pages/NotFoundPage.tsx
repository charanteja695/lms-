import { Button, EmptyState } from "@/shared/ui";

export function NotFoundPage() {
  return (
    <EmptyState
      icon="search"
      title="Page not found"
      description="The page you requested does not exist."
      action={<Button onClick={() => window.history.back()}>Go back</Button>}
    />
  );
}

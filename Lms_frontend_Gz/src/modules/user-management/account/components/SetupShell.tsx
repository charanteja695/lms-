import { useSignOut } from "@/modules/user-management/auth/hooks/useAuth";
import { Button } from "@/shared/ui";

export function SetupShell({ children }: { children: React.ReactNode }) {
  const { signOut, isSigningOut } = useSignOut();
  return (
    <div className="flex min-h-screen items-start justify-center bg-slate-50 px-4 py-12">
      <div className="w-full max-w-2xl space-y-6">
        {children}
        <div className="text-center">
          <Button variant="link" onClick={() => void signOut()} loading={isSigningOut}>
            Sign out
          </Button>
        </div>
      </div>
    </div>
  );
}
